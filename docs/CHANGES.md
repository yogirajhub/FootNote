# FootNote Architecture & Implementation Decisions

This document logs significant technical decisions that deviate from or clarify the original specification.

## 1. Local MongoDB Vector Search Fallback
**Decision**: Fallback to in-process numpy cosine similarity.
**Reason**: Local MongoDB deployments (e.g. standard `mongo:7.0` docker image) do not support the `$vectorSearch` aggregation pipeline, which is an Atlas-exclusive feature. A `_VectorCache` was built to load embeddings into memory per-document and compute cosine similarity using numpy for local dev.

## 2. Embedding Model
**Decision**: Stick to `all-MiniLM-L6-v2`.
**Reason**: It's lightweight and works entirely in-process using `sentence-transformers`. It struggles slightly with Hindi/Hinglish but performs well for English context retrieval. It is warmed up asynchronously on app startup.

## 3. Query Rewriter Heuristics
**Decision**: Use heuristics to determine if a query is anaphoric before calling the LLM.
**Reason**: Saving an LLM round-trip reduces Time To First Byte (TTFB) by 300-800ms. Queries < 8 words or containing pronouns are flagged for rewrite. Others are passed straight to vector search.

## 4. UI 3-Pane Layout
**Decision**: Dropped standard next.js layouts in favor of a fixed `h-screen` workspace.
**Reason**: Better fits the spec's requirements for a persistent Reader, TOC sidebar, and Chat pane without scrolling the window body.

## 5. Chunk Storage vs Pages
**Decision**: Re-architected ingestion to store full `document_pages` alongside chunks.
**Reason**: The previous implementation only stored vectorized chunks. To support the "Reader" and "Jump to Page" functionality, the raw text indexed by page number was required.

## 6. Diagram Panel
**Decision**: Omitted the "Diagram" tab specified in the prompt.
**Reason**: Current LLMs struggle to output reliable mermaid.js or ASCII diagrams consistently as part of a single text stream without breaking JSON boundaries or markdown parsers. The prompt tag `<diagram>` is ignored.
