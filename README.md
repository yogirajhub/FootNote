# FootNote

**Turn every document into a conversation.**

FootNote is a document-grounded conversational RAG platform. Upload books, research papers, and documents to automatically convert them into independent, searchable knowledge bases. Discuss passages, explore related concepts, and get plain-English explanations — all completely grounded in the source text.

## Features

- **Document-Agnostic Ingestion:** Supports PDF, EPUB, DOCX, TXT, and Markdown.
- **Structure-Aware Processing:** Detects chapters, sections, and paragraphs automatically.
- **Document-Scoped RAG:** Prevents cross-contamination by searching only within the active document unless explicitly told otherwise.
- **Rich Chat UI:** Displays exact source citations (chapter/page), quoted passages, and plain-English explanations.
- **Interactive Passages:** "Discuss this passage" mode allows you to dive deep into specific concepts.
- **Safety Layer:** Includes crisis detection and mental-health disclaimers for sensitive texts.

## Architecture & Tech Stack

### Frontend
- **Next.js (App Router)**
- **TypeScript**
- **Tailwind CSS** (Custom warm/stone palette for reading comfort)
- **React Dropzone** & **React Markdown**

### Backend
- **Python / FastAPI**
- **MongoDB** (Atlas Vector Search or local via Docker)
- **Hugging Face Sentence Transformers** (`all-MiniLM-L6-v2`)
- **Groq API** (`openai/gpt-oss-20b`)

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

### 3. Ingesting Documents (CLI)

You can ingest documents via the Web UI (Upload Modal) or using the provided CLI scripts:

```bash
# Ingest a general document
python scripts/ingest_document.py --file path/to/document.pdf --title "My Document"

# Ingest a book specifically
python scripts/ingest_book.py --file path/to/book.epub --title "My Book" --author "Author Name"
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

## Future Improvements

- **Full Authentication:** The architecture supports user_ids; implement a JWT/OAuth flow.
- **Cross-Encoder Reranking:** Replace the MVP Cosine reranker with a dedicated cross-encoder model.
- **Cloud Vector Search:** Swap the local MongoDB for a MongoDB Atlas cluster to enable true scalable vector search.
- **Streaming UI:** Implement SSE (Server-Sent Events) in the UI to stream LLM responses token-by-token.
