import { useEffect, useState } from 'react'
import { ArrowUpRight, Check, FileText, Files, FolderOpen, GitCompareArrows, LoaderCircle, MessageSquareText, Plus, Search, ShieldCheck, Sparkles, UploadCloud } from 'lucide-react'
import './workspace.css'

function App() {
  const [activeView, setActiveView] = useState('ask')
  const [documents, setDocuments] = useState([])
  const [selectedDocumentIds, setSelectedDocumentIds] = useState([])
  const [question, setQuestion] = useState('')
  const [askedQuestion, setAskedQuestion] = useState('')
  const [answerData, setAnswerData] = useState(null)
  const [isAsking, setIsAsking] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')

  const apiUrl = import.meta.env.VITE_API_URL || `http://${window.location.hostname}:8000`

  async function refreshDocuments() {
    const response = await fetch(`${apiUrl}/api/documents`)
    if (!response.ok) throw new Error('Could not load documents from the database.')
    const savedDocuments = await response.json()
    setDocuments(savedDocuments.map((document, index) => ({ ...document, name: document.filename, meta: `${document.chunks} searchable chunks`, tone: ['coral', 'teal', 'yellow'][index % 3] })))
  }

  function toggleDocument(documentId) {
    setSelectedDocumentIds((current) => current.includes(documentId) ? current.filter((id) => id !== documentId) : [...current, documentId])
  }

  useEffect(() => {
    refreshDocuments().catch((requestError) => setError(requestError.message))
  }, [])

  async function handleFiles(event) {
    const selectedFiles = Array.from(event.target.files || [])
    if (!selectedFiles.length) return
    const formData = new FormData()
    selectedFiles.forEach((file) => formData.append('files', file))
    setUploading(true)
    setError('')
    try {
      const response = await fetch(`${apiUrl}/api/documents/upload`, { method: 'POST', body: formData })
      if (!response.ok) throw new Error((await response.json()).detail || 'Upload failed.')
      const uploadedDocuments = await response.json()
      setSelectedDocumentIds(uploadedDocuments.map((document) => document.id))
      await refreshDocuments()
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setUploading(false)
    }
  }

  async function askQuestion(event) {
    event.preventDefault()
    if (!question.trim()) return
    setAskedQuestion(question.trim())
    setAnswerData(null)
    setIsAsking(true)
    setError('')
    try {
      const response = await fetch(`${apiUrl}/api/ask`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: question.trim(), document_ids: selectedDocumentIds.length ? selectedDocumentIds : null }) })
      if (!response.ok) throw new Error('The question could not be answered.')
      setAnswerData(await response.json())
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setIsAsking(false)
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar"><a className="brand" href="/" aria-label="DocuLens home"><span className="brand-mark"><Sparkles size={16} /></span><span>Docu<span>Lens</span></span></a><div className="topbar-context"><span className="status-dot" /> Private workspace</div><button className="icon-button" type="button" title="Start a new workspace" onClick={() => setAskedQuestion('')}><Plus size={18} /><span>New workspace</span></button></header>
      {error && <div className="app-error" role="alert">{error}</div>}<div className="workspace">
        <aside className="sidebar"><div className="sidebar-heading"><div><p className="eyebrow">Workspace</p><h2>My documents</h2></div><span className="count-pill">{documents.length}</span></div><label className="upload-zone"><input type="file" accept=".pdf,.txt" multiple onChange={handleFiles} /><span className="upload-icon"><UploadCloud size={21} /></span><strong>{uploading ? 'Indexing files...' : 'Add documents'}</strong><span>PDF or TXT · up to 20 MB</span></label><p className="selection-hint">{selectedDocumentIds.length ? `${selectedDocumentIds.length} selected for questions` : 'All documents included'}</p><div className="document-list">{documents.map((document) => <button className={`document-row ${selectedDocumentIds.includes(document.id) ? 'selected' : ''}`} type="button" key={document.id} onClick={() => toggleDocument(document.id)}><span className={`file-icon ${document.tone}`}><FileText size={17} /></span><span className="document-copy"><strong>{document.name}</strong><small>{document.meta}</small></span>{selectedDocumentIds.includes(document.id) ? <Check className="ready-icon" size={15} /> : <span className="select-dot" />}</button>)}</div><div className="sidebar-bottom"><div className="privacy-note"><ShieldCheck size={17} /><span><strong>Grounded by design</strong><small>Answers cite only your files.</small></span></div><button className="settings-link" type="button"><FolderOpen size={16} /> Manage storage <ArrowUpRight size={14} /></button></div></aside>
        <main className="main-content"><div className="page-heading"><div><p className="eyebrow">Document intelligence</p><h1>Make sense of your files.</h1><p className="subtitle">Ask precise questions, compare sources, and keep every answer traceable.</p></div><div className="indexed-status"><span className="status-dot" /> All documents indexed</div></div><div className="mode-switcher" role="tablist" aria-label="Workspace mode"><button className={activeView === 'ask' ? 'active' : ''} onClick={() => setActiveView('ask')} type="button" role="tab" aria-selected={activeView === 'ask'}><MessageSquareText size={17} /> Ask questions</button><button className={activeView === 'compare' ? 'active' : ''} onClick={() => setActiveView('compare')} type="button" role="tab" aria-selected={activeView === 'compare'}><GitCompareArrows size={17} /> Compare documents <span className="new-label">New</span></button></div>
          {activeView === 'ask' ? <section className="answer-layout"><div className="question-column"><div className="section-label"><span>Ask your workspace</span><span className="shortcut">⌘ K</span></div><form className="question-box" onSubmit={askQuestion}><Search size={19} /><input value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="What would you like to find out?" aria-label="Ask a question" /><button className="submit-button" type="submit" title="Ask question"><ArrowUpRight size={18} /></button></form><div className="suggestion-row"><span>Try asking</span><button type="button" onClick={() => setQuestion('What is the company leave policy?')}>What is the leave policy?</button><button type="button" onClick={() => setQuestion('What are the working hours?')}>What are the working hours?</button></div><div className="answer-card">{!askedQuestion ? <div className="empty-answer"><span className="empty-icon"><MessageSquareText size={22} /></span><h3>Your answer will appear here</h3><p>Ask a question about the documents in your workspace. DocuLens will show the answer and the exact evidence behind it.</p></div> : <div className="demo-answer"><div className="answer-meta"><span className="question-label">Question</span><span>{askedQuestion}</span></div><div className="answer-divider" />{isAsking ? <div className="loading-line"><LoaderCircle size={17} /><span>Searching your sources...</span></div> : <><div className="loading-line"><Check size={17} /><span>{answerData?.grounded ? 'Grounded answer' : 'API connection ready'}</span></div><p className="demo-copy">{answerData?.answer || 'The API is ready. Start the FastAPI service to retrieve document passages and generate a cited answer.'}</p></>}</div>}</div></div><aside className="evidence-column"><div className="section-label"><span>Evidence</span><span className="evidence-count">{answerData?.sources?.length || 0} sources</span></div>{answerData?.sources?.length ? answerData.sources.map((source) => <div className="evidence-card source-card" key={`${source.filename}-${source.page}`}><strong>{source.filename}{source.page ? ` · page ${source.page}` : ''}</strong><p>{source.excerpt}</p></div>) : <div className="evidence-card"><div className="evidence-empty-icon"><Files size={20} /></div><h3>No evidence yet</h3><p>Relevant excerpts and page references will appear alongside each answer.</p></div>}<div className="confidence-card"><div className="confidence-heading"><span>Answer confidence</span><span className="confidence-muted">{answerData?.confidence || 'Waiting'}</span></div><div className="confidence-track"><span className={answerData?.confidence || ''} /></div><p>Confidence is based on how closely retrieved passages match your question.</p></div></aside></section> : <section className="comparison-view"><div className="comparison-intro"><div className="compare-icon"><GitCompareArrows size={23} /></div><div><h2>Compare what changed.</h2><p>Select documents to surface differences, common ground, and missing information.</p></div></div><div className="comparison-selectors"><div className="selector-card"><span>Document A</span><strong>{documents[0]?.name}</strong><small>Choose a source document</small></div><div className="compare-connector"><GitCompareArrows size={18} /></div><div className="selector-card"><span>Document B</span><strong>{documents[1]?.name}</strong><small>Choose a source document</small></div></div><div className="question-box comparison-input"><Search size={19} /><input placeholder="What should I compare between these documents?" /><button className="submit-button" type="button" title="Run comparison"><ArrowUpRight size={18} /></button></div><div className="comparison-placeholder"><Sparkles size={18} /><span>Comparison results will include citations for each document.</span></div></section>}
        </main>
      </div><footer><span>DocuLens · Document intelligence, grounded in your sources.</span><span>Built for focused research <Sparkles size={13} /></span></footer>
    </div>
  )
}

export default App
