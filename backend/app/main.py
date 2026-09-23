from __future__ import annotations

import io
import os
import re
import uuid
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Annotated

import fitz
import numpy as np
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer

load_dotenv(Path(__file__).parents[1] / ".env")

RETRIEVAL_THRESHOLD = 0.22
STOP_WORDS = {
    "a", "an", "and", "are", "about", "be", "does", "for", "how", "in", "is", "me", "of",
    "on", "or", "tell", "the", "this", "to", "what", "where", "which", "who", "with", "you",
}

from app.database import init_database, load_chunks, load_documents, save_document

app = FastAPI(title="DocuLens API", version="0.1.0")
configured_origins = os.getenv("FRONTEND_ORIGINS") or os.getenv("FRONTEND_ORIGIN") or "http://localhost:5173,http://127.0.0.1:5173"
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in configured_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@dataclass
class Chunk:
    id: str
    document_id: str
    filename: str
    text: str
    page: int | None
    embedding: list[float] | None = None


@dataclass
class Document:
    id: str
    filename: str
    file_type: str
    size_bytes: int
    chunks: list[Chunk]


init_database()


class QuestionRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    document_ids: list[str] | None = None


class CompareRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    document_ids: list[str] = Field(min_length=2, max_length=2)


class Source(BaseModel):
    filename: str
    page: int | None
    excerpt: str
    score: float


class AnswerResponse(BaseModel):
    answer: str
    confidence: str
    sources: list[Source]
    grounded: bool


def split_text(text: str, chunk_size: int = 850, overlap: int = 120) -> list[str]:
    words = text.split()
    step = max(1, chunk_size - overlap)
    return [" ".join(words[start : start + chunk_size]) for start in range(0, len(words), step) if words[start : start + chunk_size]]


def extract_pages(filename: str, content: bytes) -> list[tuple[str, int | None]]:
    suffix = filename.lower().rsplit(".", 1)[-1]
    if suffix == "txt":
        return [(content.decode("utf-8", errors="replace"), None)]
    if suffix != "pdf":
        raise HTTPException(status_code=400, detail="Only PDF and TXT files are supported.")
    pdf = fitz.open(stream=content, filetype="pdf")
    return [(page.get_text("text"), number) for number, page in enumerate(pdf, start=1)]


@lru_cache(maxsize=1)
def embedding_model() -> SentenceTransformer:
    return SentenceTransformer(os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"))


def embed_texts(texts: list[str]) -> list[list[float]]:
    vectors = embedding_model().encode(texts, normalize_embeddings=True)
    return np.asarray(vectors, dtype="float32").tolist()


def lexical_search(question: str, chunks: list[Chunk], limit: int = 5) -> list[tuple[Chunk, float]]:
    query_words = meaningful_words(question)
    scored = []
    for chunk in chunks:
        chunk_words = set(chunk.text.lower().split())
        overlap = len(query_words & chunk_words) / max(1, len(query_words))
        scored.append((chunk, overlap))
    return sorted(scored, key=lambda item: item[1], reverse=True)[:limit]


def meaningful_words(text: str) -> set[str]:
    words = set(re.findall(r"[a-z0-9]+", text.lower()))
    return words - STOP_WORDS


def source_from_match(match: tuple[Chunk, float]) -> Source:
    chunk, score = match
    return Source(filename=chunk.filename, page=chunk.page, excerpt=chunk.text[:420], score=round(score, 3))


def generate_answer(question: str, matches: list[tuple[Chunk, float]]) -> str:
    if not matches or matches[0][1] < RETRIEVAL_THRESHOLD:
        return "I couldn't find information about that in the uploaded documents."
    context = "\n\n".join(f"SOURCE {index} ({chunk.filename}, page {chunk.page or 'n/a'}): {chunk.text}" for index, (chunk, _) in enumerate(matches, 1))
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "Relevant evidence was found, but a GROQ_API_KEY is required to generate the final answer."
    response = Groq(api_key=api_key).chat.completions.create(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        temperature=0,
        messages=[
            {"role": "system", "content": "Answer only from the supplied sources. If the answer is not supported, say so clearly. Cite source numbers in the answer."},
            {"role": "user", "content": f"SOURCES:\n{context}\n\nQUESTION: {question}"},
        ],
    )
    return response.choices[0].message.content or "I couldn't generate an answer."


def search_documents(question: str, document_ids: list[str] | None = None) -> list[tuple[Chunk, float]]:
    rows = load_chunks(document_ids)
    chunks = [Chunk(id=row.id, document_id=row.document_id, filename=row.filename, text=row.text, page=row.page, embedding=row.embedding) for row in rows]
    if not chunks:
        return []
    query_embedding = embed_texts([question])[0]
    semantic_matches = []
    query_words = meaningful_words(question)
    for chunk in chunks:
        if chunk.embedding:
            semantic_score = float(np.dot(query_embedding, np.asarray(chunk.embedding, dtype="float32")))
            chunk_words = meaningful_words(chunk.text)
            lexical_boost = min(0.08, 0.08 * len(query_words & chunk_words) / max(1, len(query_words)))
            semantic_matches.append((chunk, semantic_score + lexical_boost))
    return sorted(semantic_matches, key=lambda item: item[1], reverse=True)[:5] if semantic_matches else lexical_search(question, chunks)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "doculens-api"}


@app.get("/api/documents")
def list_documents() -> list[dict[str, object]]:
    return load_documents()


@app.post("/api/documents/upload")
async def upload_documents(files: Annotated[list[UploadFile], File(...)]) -> list[dict[str, object]]:
    uploaded = []
    for file in files:
        content = await file.read()
        pages = extract_pages(file.filename or "document.txt", content)
        chunks: list[Chunk] = []
        for text, page in pages:
            chunks.extend(Chunk(id=str(uuid.uuid4()), document_id="", filename=file.filename or "document.txt", text=chunk, page=page) for chunk in split_text(text))
        document_id = str(uuid.uuid4())
        for chunk in chunks:
            chunk.document_id = document_id
        document = Document(document_id, file.filename or "document.txt", file.content_type or "text/plain", len(content), chunks)
        if chunks:
            embeddings = embed_texts([chunk.text for chunk in chunks])
            for chunk, embedding in zip(chunks, embeddings):
                chunk.embedding = embedding
        save_document(document)
        uploaded.append({"id": document_id, "filename": document.filename, "chunks": len(chunks)})
    return uploaded


@app.post("/api/ask", response_model=AnswerResponse)
def ask_question(request: QuestionRequest) -> AnswerResponse:
    matches = search_documents(request.question, request.document_ids)
    relevant_matches = [match for match in matches if match[1] >= RETRIEVAL_THRESHOLD]
    if not relevant_matches:
        return AnswerResponse(answer=generate_answer(request.question, matches), confidence="low", sources=[], grounded=False)
    confidence = "high" if relevant_matches[0][1] >= 0.4 else "medium"
    return AnswerResponse(answer=generate_answer(request.question, relevant_matches), confidence=confidence, sources=[source_from_match(match) for match in relevant_matches], grounded=True)


@app.post("/api/compare", response_model=AnswerResponse)
def compare_documents(request: CompareRequest) -> AnswerResponse:
    matches = search_documents(request.question, request.document_ids)
    relevant_matches = [match for match in matches if match[1] >= RETRIEVAL_THRESHOLD]
    answer = generate_answer(request.question, relevant_matches)
    return AnswerResponse(answer=answer, confidence="medium" if relevant_matches else "low", sources=[source_from_match(match) for match in relevant_matches], grounded=bool(relevant_matches))
