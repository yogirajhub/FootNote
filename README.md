# FootNote

**Turn every document into a conversation.**

FootNote is a document-grounded conversational RAG platform. Upload books, research papers, and documents to automatically convert them into independent, searchable knowledge bases. Discuss passages, explore related concepts, and get plain-English explanations — all completely grounded in the source text.

## Features

- **Document-Agnostic Ingestion:** Supports PDF, EPUB, DOCX, TXT, and Markdown.
- **Structure-Aware Processing:** Detects chapters, sections, and pages automatically.
- **Document-Scoped RAG:** Prevents cross-contamination by searching only within the active document.
- **Rich 3-Pane Workspace:** Combines a Table of Contents sidebar, a live document reader, and a chat pane.
- **Streaming LLM Responses:** Fast, token-by-token streaming via SSE.
- **Interactive Reading:** Select any text in the reader to instantly ask the AI to explain it.
- **Notepad:** Save important AI explanations and your own notes directly linked to document pages.
- **Safety Layer:** Includes crisis detection and mental-health disclaimers for sensitive texts.

## Architecture & Tech Stack

### Frontend
- **Next.js (App Router)**
- **TypeScript**
- **Tailwind CSS** (Custom warm/stone palette for reading comfort)
- **React Dropzone** & **React Markdown**

### Backend
- **Python / FastAPI**
- **MongoDB** (Atlas Vector Search or fallback to in-memory numpy cosine similarity)
- **Hugging Face Sentence Transformers** (`all-MiniLM-L6-v2` run asynchronously)
- **Groq API** (`llama3-70b-8192` or similar via `AsyncGroq` singleton)

---

## Getting Started

### 1. Environment Setup

Copy the example environment file and fill in your details:
```bash
cp .env.example .env
```
Ensure you have added your `GROQ_API_KEY`.

### 2. Run with Docker Compose

The easiest way to run the entire stack (MongoDB, FastAPI Backend, Next.js Frontend) locally:
```bash
docker compose up --build
```

- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **API Docs (Swagger):** http://localhost:8000/docs

### 3. Backfill Pages (Important for v2)

If you are upgrading from FootNote v1, you must run the backfill script to extract raw pages for the new Reader pane:

```bash
python scripts/backfill_pages.py --all
```

### 4. Benchmark Latency

Run the benchmark script to measure extraction, chunking, and embedding times:
```bash
python scripts/benchmark_latency.py
```

---

## Folder Structure

```text
footnote/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routers
│   │   ├── config/       # Pydantic settings
│   │   ├── db/           # MongoDB connection & indexes
│   │   ├── ingestion/    # Loaders, parser, chunker, structure detector
│   │   ├── models/       # DB Models
│   │   ├── rag/          # Embeddings, retrieval, generation, intent
│   │   ├── safety/       # Crisis detection
│   │   ├── schemas/      # Pydantic API schemas
│   │   ├── services/     # Business logic
│   │   └── main.py       # App entry point
│   └── tests/
├── frontend/
│   ├── app/              # Next.js pages & layouts
│   ├── components/       # React components
│   ├── hooks/            # Custom React hooks
│   ├── lib/              # Utilities
│   ├── services/         # API wrappers
│   └── types/            # TypeScript interfaces
└── scripts/
    ├── ingest_document.py
    ├── evaluate_rag.py
    └── cleanup_vectors.py
```

---

## Evaluation & Cleanup

Run the basic evaluation script to test RAG retrieval accuracy:
```bash
python scripts/evaluate_rag.py
```

Run the cleanup script to remove orphaned vectors if documents were deleted improperly:
```bash
python scripts/cleanup_vectors.py
```
