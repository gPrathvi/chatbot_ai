# DocuLens

DocuLens is a focused document intelligence workspace. A user uploads PDF or TXT files, asks questions about their contents, and receives answers grounded in retrieved passages with source metadata. The interface also includes a comparison mode for asking what changed or differs across two documents.

## Architecture

```mermaid
flowchart TD
    U[User] --> UI[React + Vite frontend]
    UI -->|PDF/TXT upload| API[FastAPI backend]
    API --> P[PyMuPDF parser]
    P --> C[Chunking with page metadata]
    C --> E[Local Sentence Transformer embeddings]
    E --> DB[(Hosted PostgreSQL database)]
    API --> FS[Supabase Storage]
    U -->|Question| UI
    UI --> API
    API --> R[Vector retrieval]
    R --> DB
    R --> G{Evidence strong enough?}
    G -->|No| N[Insufficient evidence response]
    G -->|Yes| L[Groq Llama model]
    L --> A[Answer + confidence + citations]
    N --> UI
    A --> UI
    UI -->|Comparison mode| API
```

## Technology choices

- **React + Vite + JavaScript:** a lightweight frontend with a polished workspace UI and no TypeScript overhead.
- **FastAPI:** a small, typed Python API that is well suited to file processing and GenAI workflows.
- **Hosted PostgreSQL:** stores document metadata, chunks, embeddings, pages, and source relationships persistently. Embeddings are stored as JSON, so no database extension is required.
- **Sentence Transformers `all-MiniLM-L6-v2`:** creates embeddings locally without an embedding API bill.
- **Groq Llama:** generates concise answers from retrieved evidence.
- **PyMuPDF:** extracts text from PDF files while preserving page numbers for citations.
- **Supabase Storage:** stores original uploads separately from searchable text.

## Features

### Required

- Upload one or more PDF or TXT documents.
- Extract and chunk document text.
- Create embeddings and search relevant content.
- Ask questions using retrieved context.
- Show source filenames, excerpts, and page numbers for PDF content.
- Decline to answer when relevant evidence is not found.

### Additional features

1. **Evidence confidence:** each answer exposes a confidence level based on retrieval strength and displays supporting excerpts.
2. **Document comparison:** users can compare two selected documents and ask about changes, differences, or common information.

## Hallucination handling

DocuLens uses several safeguards:

1. Questions are matched against uploaded content before the LLM is called.
2. Low-overlap or low-similarity results produce an explicit insufficient-evidence response.
3. The LLM prompt instructs it to use only supplied sources and avoid outside knowledge.
4. Temperature is set to zero for more consistent answers.
5. Every grounded answer keeps the retrieved source metadata visible in the UI.

The confidence label is an evidence indicator, not a guarantee of factual truth.

## Run locally

### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8000
```

Set these values in `backend/.env`:

```text
GROQ_API_KEY=your_groq_key
GROQ_MODEL=openai/gpt-oss-20b
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE
FRONTEND_ORIGIN=http://localhost:5173
```

`DATABASE_URL` is required. The backend does not use SQLite, in-memory storage, or browser local storage. Use the hosted PostgreSQL connection string from Supabase, preferably its Session Pooler connection string. The database tables are created automatically when the backend starts.

### Frontend

```powershell
cd frontend
npm install
- `GET /health`
- `GET /api/documents`
- `POST /api/documents/upload`
- `POST /api/ask`
- `POST /api/compare`

## Known limitations

- DOCX, CSV, and Excel are not included in the MVP.
- Original file storage needs a configured Supabase Storage integration; the current local API focuses on extraction and indexing.
- Comparison mode shares the retrieval pipeline but needs the database and LLM configuration for real generated comparison output.
- OCR for scanned PDFs is not included.
- Authentication and per-user workspaces are outside the assignment scope.

## AI tools used

ChatGPT/Copilot assistance was used for architecture discussion, implementation drafting, debugging, UI iteration, and documentation review. All generated code was checked against the local build and Python compilation checks.

## Estimated time log

| Activity | Estimate |
| --- | ---: |
| Requirements and architecture | 30 minutes |
| Frontend workspace | 2 hours |
| FastAPI ingestion and retrieval | 2 hours |
| Database integration | 1 hour |
| Testing and debugging | 1.5 hours |
| README and demo preparation | 1 hour |

Total planned time: approximately 8 hours.
