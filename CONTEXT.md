# FootNote — Complete Project Context

> **Purpose of this file:** A single source of truth for any agent/developer to understand the entire FootNote codebase instantly — no scanning required. Update this file whenever significant architecture or feature changes are made.

---

## 1. What Is FootNote?

FootNote is a **document-grounded conversational RAG (Retrieval-Augmented Generation) platform**. Users upload documents (PDF, DOCX, TXT, MD, EPUB), and the AI chat assistant ("Ask FootNote") answers questions **strictly from those documents**, citing exact pages/chapters/sections as proof of accuracy.

**Core promise:** Every AI answer comes with:
1. 📖 Source badge (Page X, Chapter Y, Section Z)
2. Proof accordion (exact verbatim quote from text)
3. Simple Explanation accordion
4. Example accordion

**Language support:** English, Hinglish (Hindi+English mix), and Hindi — the bot matches the user's language style automatically.

---

## 2. Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16.3.5 (App Router), TypeScript, Tailwind CSS v4, React |
| Backend | FastAPI (Python 3.11), uvicorn |
| Database | MongoDB (Motor async driver) + GridFS for file storage |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 (384-dim vectors) |
| LLM | Groq API → openai/gpt-oss-20b model (streaming) |
| Vector Search | MongoDB $vectorSearch (Atlas) with NumPy cosine fallback |
| Containerization | Docker + docker-compose |

---

## 3. Repository Structure

```
FootNote/
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI entry, lifespan, CORS, routers
│   │   ├── config/settings.py          # All config via pydantic-settings + .env
│   │   ├── api/
│   │   │   ├── chat.py                 # POST /chat, POST /chat/stream (SSE), GET /conversations
│   │   │   ├── documents.py            # CRUD + upload + /pages + /file + /sections
│   │   │   ├── notes.py                # Notes CRUD
│   │   │   ├── passages.py             # Passage search
│   │   │   ├── health.py               # GET /health
│   │   │   └── deps.py                 # get_current_user (reads x-user-id header)
│   │   ├── db/
│   │   │   └── mongodb.py              # Motor client, collection accessors, index creation
│   │   ├── ingestion/
│   │   │   ├── pipeline.py             # Ingestion orchestrator (load → chunk → embed → index)
│   │   │   ├── chunker.py              # Text chunking (512 tokens, 64 overlap)
│   │   │   ├── indexer.py              # Saves chunks + embeddings to MongoDB
│   │   │   ├── pages.py                # Page storage and retrieval
│   │   │   ├── structure_detector.py   # Chapter/section detection
│   │   │   └── loaders/
│   │   │       ├── base.py             # DocumentLoader ABC, LoadedDocument, DocumentPage
│   │   │       ├── pdf_loader.py       # pypdf
│   │   │       ├── docx_loader.py      # python-docx
│   │   │       └── text_loader.py      # .txt / .md / .epub
│   │   ├── rag/
│   │   │   ├── pipeline.py             # Main RAG orchestrator (8 stages)
│   │   │   ├── intent_classifier.py    # Classifies query intent (10 intents)
│   │   │   ├── query_rewriter.py       # Rewrites ambiguous queries
│   │   │   ├── retriever.py            # MongoDB vector search + NumPy fallback + LRU cache
│   │   │   ├── reranker.py             # Cosine reranker (pluggable)
│   │   │   ├── context_builder.py      # Builds prompt context with neighbor expansion
│   │   │   ├── generator.py            # Groq LLM provider (sync + async streaming)
│   │   │   ├── embeddings.py           # Embedding service (sentence-transformers)
│   │   │   └── prompts.py              # wants_detail() helper (EN+Hinglish+Hindi)
│   │   ├── safety/
│   │   │   └── safety_checker.py       # Crisis detection, disclaimer flagging
│   │   ├── services/
│   │   │   ├── chat_service.py         # Chat business logic, conversation management
│   │   │   ├── document_service.py     # Document CRUD + background processing trigger
│   │   │   └── original_file_service.py  # GridFS file storage/retrieval
│   │   ├── schemas/                    # Pydantic models for API request/response
│   │   └── utils/
│   │       └── timing.py               # StageTimer for per-stage latency tracking
│   ├── tests/                          # 23 pytest tests (all pass)
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── layout.tsx                  # Root layout (Inter + Lora fonts)
│   │   ├── globals.css                 # Tailwind v4 theme tokens, dark mode, PDF text layer CSS
│   │   ├── page.tsx                    # Home page: document library grid + upload modal
│   │   └── documents/[id]/
│   │       ├── chat/page.tsx           # MAIN WORKSPACE (reader + chat + sidebar) — 1119 lines
│   │       └── processing/page.tsx     # Processing status page
│   ├── components/
│   │   ├── reader/PdfViewer.tsx        # PDF rendering with pdfjs-dist + text selection
│   │   └── upload/UploadModal.tsx      # Multi-step upload form
│   ├── hooks/
│   │   ├── useChatStream.ts            # SSE streaming state machine
│   │   └── useTextSelection.ts         # Text selection from reader → QuoteChip
│   ├── services/
│   │   ├── api.ts                      # Axios base client (/api proxy)
│   │   ├── chat.ts                     # chatService (sendMessage, streamMessage, conversations)
│   │   ├── documents.ts                # documentsService (CRUD, pages, file download)
│   │   └── notes.ts                    # notesService (CRUD)
│   └── types/
│       └── api.ts                      # All shared TypeScript interfaces
├── scripts/                            # CLI ingestion/evaluation scripts
├── docker-compose.yml                  # MongoDB + backend + frontend services
├── .env                                # Secret keys and config (not committed)
└── CONTEXT.md                          # This file
```

---

## 4. MongoDB Collections

| Collection | Purpose |
|---|---|
| `documents` | Document metadata (title, author, status, file info) |
| `document_chunks` | Text chunks with embeddings (384-dim float arrays) |
| `document_pages` | Per-page content for the reader (text + headings) |
| `document_sections` | Detected chapters/sections with hierarchy |
| `document_files` (GridFS) | Original uploaded file bytes |
| `conversations` | Conversation metadata per document per user |
| `messages` | Individual chat messages with passages |
| `notes` | User notes (linked to page numbers) |
| `processing_jobs` | Background ingestion job status |

---

## 5. RAG Pipeline (8 Stages)

```
User Query
    │
    ▼
1. Safety Check             safety_checker.check(query)
    │                       → Returns early on crisis content
    ▼
2. Intent Classification    classify_intent(query, history, document_title)
    │                       → OUT_OF_SCOPE for greetings, off-topic queries
    │                       → 10 intent types: DOCUMENT_QUESTION, FOLLOW_UP, SUMMARY, etc.
    ▼
3. Query Rewriting           query_rewriter.arewrite(query, history, document_title)
    │                       → Resolves pronouns, adds document context
    ▼
4. Retrieval                retrieve(rewritten_query, document_id, top_k=6)
    │                       → $vectorSearch first, NumPy cosine fallback
    │                       → ALWAYS scoped by document_id (isolation guaranteed)
    ▼
5. Reranking                reranker.rerank(query, chunks, top_k=4)
    │                       → Cosine similarity reranking
    ▼
6. Neighbor Expansion       get_neighbor_chunks(top_chunk)
    │                       → Fetches prev + next chunks for richer context
    ▼
7. Context Building         build_context(reranked, neighbors)
    │                       → 2200 token context budget
    ▼
8. LLM Generation           Groq streaming → SSE chunks to browser
                            → Structured: Answer + Source + Proof + Explanation + Example
```

---

## 6. LLM Response Format

Every answer follows this exact Markdown structure:

```
**Answer**
[2-3 sentence direct answer]

📖 **Source:** Page X, Chapter Y, Section Z

<details>
<summary>Proof</summary>
"...exact verbatim quote..."  — Page X, Chapter Y
</details>

<details>
<summary>Simple Explanation</summary>
[Accessible explanation in user's language]
</details>

<details>
<summary>Example</summary>
[Analogy or practical example]
</details>
```

---

## 7. Intent Types

| Intent | Description |
|---|---|
| `DOCUMENT_QUESTION` | Default: general question about document |
| `PASSAGE_EXPLANATION` | "explain this", "kya matlab" |
| `FOLLOW_UP` | "why", "how", "aur batao", continues prior topic |
| `SUMMARY` | "summarize", "overview", "saar" |
| `QUOTE_REQUEST` | "exact words", "verbatim", "likha hai" |
| `NAVIGATION` | "chapter", "page", "go to", "konsa page" |
| `COMPARISON` | "compare", "difference", "fark kya" |
| `RELATED_PASSAGES` | "related", "similar", "aur kuch" |
| `SECTION_QUERY` | Section-specific question |
| `OUT_OF_SCOPE` | Greetings, off-topic queries |

---

## 8. Out-of-Scope Handling

- **Greetings set:** "hi", "hello", "namaste", "ok", "hmm", "acha", "ji", etc. → OUT_OF_SCOPE
- **Off-topic domains rejected:** politics, elections, sports (cricket/IPL/football), Bollywood/movies, recipes/cooking, weather, social media, shopping, general trivia
- **Smart title exemption:** If the document title itself covers the flagged domain (e.g., a politics textbook), those queries ARE answered
- **Document-anchor override:** Any query with "book", "chapter", "page", "document me", "yaha likha" → always on-topic
- **Response:** Bilingual Hinglish+English redirect suggesting to upload relevant document

---

## 9. Frontend — Main Workspace (chat/page.tsx)

3-pane full-viewport flex row layout:

```
┌──────────────┬────────────────────────┬──────────────────┐
│   SIDEBAR    │      READER PANE       │   CHAT PANE      │
│  (TOC/Notes) │  (BookReader / PDF)    │  (Ask FootNote)  │
│  ~240px fixed│   flex-[1_1_40rem]     │  280–600px drag  │
└──────────────┴────────────────────────┴──────────────────┘
```

### Key Components in chat/page.tsx

| Component | Purpose |
|---|---|
| `QuoteChip` | Shows selected text above input with page# and remove button |
| `Accordion` | Collapsible section (Proof / Simple / Example) |
| `SourceBadge` | Clickable page/chapter/section tags that jump reader |
| `getSourcesForMessage()` | Extracts sources from passages or parses from content text |
| `AnswerCard` | Full answer rendering: markdown + sources + accordions + action buttons |
| `PageGrid` | 5-col TOC grid with hover preview popup |
| `BookReader` | Paginated text reader with smooth scroll |
| `NotepadPanel` | CRUD note-taking, page-linked |
| `ChatPage` | Main page component (root) |

### Resizable Chat Pane ✅

Already fully implemented:

```typescript
// State
const [chatWidth, setChatWidth] = useState(352); // default px
const isDraggingRef = useRef(false);
const dragStartXRef = useRef(0);
const dragStartWidthRef = useRef(0);
const CHAT_MIN_WIDTH = 280;
const CHAT_MAX_WIDTH = 600;

// Handler: handleResizeMouseDown
// → Attaches mousemove/mouseup listeners to document
// → delta = startX - ev.clientX (drag left = wider chat)
// → Clamps to [280, 600]

// JSX: <div onMouseDown={handleResizeMouseDown} className="absolute left-0 ... cursor-col-resize">
```

The drag handle is a 6px-wide strip on the left edge of the chat pane.

### Key State Variables

```typescript
chatWidth: number            // chat pane width in px (default 352)
chatOpen: boolean            // show/hide chat pane
sidebarPinned: boolean       // sidebar always-open vs hover-peek
sidebarHover: boolean        // sidebar hover-open state
activePanel: "toc" | "notes"
currentPage: number          // active page in reader
jumpToken: number            // increment to trigger scroll-to-page
quoteChip: {text, page}      // text selected from reader
sendError: string | null
messages: MessageResponse[]  // full conversation history (local)
stream: StreamState          // live SSE streaming state
conversationId: string       // MongoDB conversation _id
pdfData: ArrayBuffer | null  // raw PDF bytes for pdfjs
doc: DocumentResponse        // current document metadata
```

---

## 10. SSE Streaming Protocol

**Endpoint:** `POST /api/chat/stream`

**Event format:** Each line: `data: {JSON}\n\n`

```jsonc
// Event 1: Metadata (intent + deduplicated source pages)
{"type": "metadata", "intent": "DOCUMENT_QUESTION", "rewritten_query": "...", "sources": [{"page": 12, "chapter": "Ch 3: Gravity"}]}

// Events 2..N: Delta tokens
{"type": "delta", "content": "Black holes form when..."}

// Final event
{"type": "done", "processing_time_ms": 1243, "timings": {"safety": 1.2, "intent": 0.5, ...}}

// Error
{"type": "error", "message": "..."}
```

**Frontend parsing:** `chatService.streamMessage()` uses raw `fetch()` + `ReadableStream` (NOT `EventSource`) to support POST with JSON body.

**useChatStream state machine:**

```
idle → streaming (on send)
     → done (on "done" event)  → saves to messages[]
     → error (on exception)
```

---

## 11. Key Configuration (.env → settings.py)

| Key | Default | Description |
|---|---|---|
| `MONGODB_URI` | `mongodb://localhost:27017` | MongoDB connection |
| `GROQ_API_KEY` | `""` | **Required** Groq LLM API key |
| `LLM_MODEL` | `openai/gpt-oss-20b` | Groq model |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | 384-dim |
| `VECTOR_INDEX_NAME` | `chunk_embeddings_index` | Atlas vector index name |
| `RETRIEVAL_TOP_K` | `6` | Chunks from vector search |
| `RERANK_TOP_K` | `4` | Chunks after reranking |
| `CHUNK_SIZE` | `512` | Tokens per chunk |
| `CHUNK_OVERLAP` | `64` | Overlap between chunks |
| `MAX_UPLOAD_SIZE` | `52428800` (50MB) | Max file size |
| `CONTEXT_MAX_TOKENS` | `2200` | LLM context budget |
| `MIN_RELEVANCE` | `0.25` | Relevance gate threshold |
| `LLM_MAX_TOKENS_SHORT` | `700` | Default answer cap |
| `LLM_MAX_TOKENS_DETAIL` | `1600` | "In detail" answer cap |
| `LLM_REASONING_EFFORT` | `low` | Groq reasoning_effort parameter |
| `LLM_TIMEOUT_S` | `20.0` | Stream timeout |
| `DEMO_USER_ID` | `demo_user_001` | Hardcoded user (MVP) |
| `ALLOWED_ORIGINS` | `http://localhost:3000,...` | CORS origins |

---

## 12. Authentication (MVP — No Real Auth)

User ID is read from the `x-user-id` HTTP header. Frontend hardcodes:

```typescript
// frontend/services/chat.ts
const USER_ID = 'demo_user_001';
```

Backend extracts it in `api/deps.py` via `get_current_user`. No JWT, no sessions.

---

## 13. Supported File Formats

| Format | Loader | Method |
|---|---|---|
| `.pdf` | `PDFLoader` (pypdf) | Page-by-page text extraction |
| `.docx` | `DocxLoader` (python-docx) | Paragraph-level |
| `.txt` / `.md` | `TextLoader` | Raw text split into chunks |
| `.epub` | `TextLoader` | Treated as plain text |

---

## 14. Document Processing (Background Task)

```
Upload → create_document() → save to MongoDB + GridFS → create processing_job
                                                              │
                                              background_tasks.add_task(run_ingestion)
                                                              │
                                                     ingestion/pipeline.py:
                                                     1. Load file (format-specific loader)
                                                     2. Detect structure (chapters/sections)
                                                     3. Chunk text (512 tok, 64 overlap)
                                                     4. Embed (sentence-transformers, batched)
                                                     5. Index to document_chunks collection
                                                     6. Store pages to document_pages
                                                     7. Update doc status → "ready"
```

Status transitions: `queued` → `processing` → `ready` / `failed`

Frontend polls: `GET /api/documents/{id}/status` every 2s on `/processing` page

---

## 15. Test Suite

Run: `$env:PYTHONPATH="backend"; py -3.11 -m pytest backend/tests`

23 tests all pass. Key tests:

- `test_intent_classifier.py` — greetings, politics rejected, space accepted, document-anchor override, title-aware
- `test_document_isolation.py` — doc A queries never return doc B chunks (in-memory mock)
- `test_wants_detail.py` — "in detail", "aur samjhao", "विस्तार से" all detected
- `test_chunker.py` — chunk sizes and overlaps correct

---

## 16. Design System

**Colors (light mode):**
- Primary: `hsl(172 47% 33%)` — teal/green
- Background: `hsl(60 9% 98%)` — warm off-white
- Card: `hsl(0 0% 100%)`
- Border: `hsl(20 6% 90%)`

**Dark mode:** `@media (prefers-color-scheme: dark)` — warm dark palette

**Fonts:** Inter (body), Lora (passage/quote text)

**Tailwind v4** — uses CSS custom properties via `@theme {}`, not `tailwind.config.js`

---

## 17. Running Locally

```bash
# Docker (recommended)
docker-compose up --build
# → Frontend: http://localhost:3000
# → Backend:  http://localhost:8000/api

# Manual
cd backend && uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev

# Tests
$env:PYTHONPATH="backend"; py -3.11 -m pytest backend/tests
```

---

## 18. Gotchas & Dev Notes

1. **Vector search auto-fallback:** Non-Atlas MongoDB uses NumPy cosine with 10-doc LRU cache — completely transparent
2. **Document isolation:** `retrieve()` always filters by `document_id` — never leaks across documents
3. **SSE uses fetch() not EventSource:** Because POST + JSON body is required
4. **Chat width NOT persisted:** `chatWidth` is React state, resets to 352px on reload. To persist: `localStorage.setItem('footnote_chat_width', ...)`
5. **Demo user:** `demo_user_001` is hardcoded everywhere — adding real auth needs changes in both `deps.py` and all frontend `services/*.ts`
6. **Source badges:** Built from SSE `metadata.sources[]` array. Clicking calls `handleJumpToPage()` → sets `jumpToken` → triggers reader scroll
7. **PDF.js worker:** Must be at `/public/pdf.worker.min.mjs`. 404 = silent PDF render failure
8. **Groq extra_body:** `reasoning_effort` is sent via `extra_body` param — if Groq model doesn't support it, it silently ignores it
9. **Ingestion pipeline module conflict:** There are two pipeline modules — `backend/app/ingestion/pipeline.py` (ingestion) and `backend/app/rag/pipeline.py` (RAG). Don't confuse them.

---

## 19. Feature Status

| Feature | Status |
|---|---|
| Document upload (PDF/DOCX/TXT/MD/EPUB) | ✅ Done |
| **Refined "Add New Document" Modal & Page (`/upload`)** | ✅ Done |
| **Real-time client upload progress bar (Axios onUploadProgress)** | ✅ Done |
| **Low-latency non-blocking upload endpoint (<50ms response)** | ✅ Done |
| **Granular background ingestion progress (pages, chunks, embeddings)** | ✅ Done |
| **Fast 1000ms status polling & live metrics on processing page** | ✅ Done |
| **Batch-optimized embedding service (batch_size=64 with batch progress)** | ✅ Done |
| **Book card 3-dot actions menu (Delete, Edit Title/Author, Favorite/Star)** | ✅ Done |
| **Favorite filtering tab on library page** | ✅ Done |
| **Proof dropdown calm typography (normal non-italic, strictly ≤3 lines)** | ✅ Done |
| **In detail structured GFM comparison tables** | ✅ Done |
| **Save to notes popup toast feedback** | ✅ Done |
| **FootNote build query safety fallback ("I am not able to answer...")** | ✅ Done |
| Background ingestion + status polling | ✅ Done |
| Vector search (Atlas) + NumPy fallback | ✅ Done |
| SSE streaming chat | ✅ Done |
| Source citations (Page/Chapter/Section) | ✅ Done |
| Proof accordion with jump-to-page | ✅ Done |
| **Resizable chat pane (280–600px drag)** | ✅ Done |
| **Fresh clean chat on open (no old history dump)** | ✅ Done |
| **Chat history drawer / past conversation viewer** | ✅ Done |
| **Movable floating chat icon (draggable anywhere in UI)** | ✅ Done |
| Text selection → QuoteChip → AI question | ✅ Done |
| PDF in-browser rendering (pdfjs) | ✅ Done |
| TOC sidebar (page grid with hover preview) | ✅ Done |
| Notes (CRUD, page-linked) | ✅ Done |
| Hinglish/Hindi response support | ✅ Done |
| Out-of-scope graceful handling | ✅ Done |
| Document-title-aware scope detection | ✅ Done |
| Dark mode | ✅ Done (auto) |
| Multi-user auth | ❌ Not yet |
| Bookmarks | ❌ Not yet |
| Library/cross-document chat | 🟡 Partial (backend ready) |
| Annotation highlighting in PDF | ❌ Not yet |
| Chat width persistence (localStorage) | ❌ Not yet |

---

*Last updated: 2026-10-19. Branch: feature/first*

