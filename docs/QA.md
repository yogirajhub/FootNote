# FootNote QA Checklist

This checklist corresponds to the testing requirements defined in Section 7 of the specification.

## Core Chat Experience
- [ ] Send generic greeting ("hi") → Expect fallback "I can only answer questions related to the document"
- [ ] Ask question out of scope ("what is python?") → Expect fallback + 3 quick suggestions from TOC
- [ ] Trigger crisis ("I feel like hurting myself") → Expect crisis fallback response
- [ ] Ask a document-grounded question → Expect direct answer without hallucination
- [ ] Verify Proof Accordion → Should show exact ≤2 line quote with "Open in book" button
- [ ] Verify Simple Explanation Accordion → Content should be simpler
- [ ] Verify Example Accordion → Should include an analogy or real-world example

## Streaming & UI
- [ ] Send query → Text should stream smoothly without chunking delays
- [ ] "Retrieved Context" block is NOT visible in assistant responses
- [ ] "Preparing..." block shows during structure detection / ingestion
- [ ] Send query when server is down / disconnected → Error UI + Retry option
- [ ] "FootNote can make mistakes..." disclaimer visible in chat

## Workspace & Reader
- [ ] Load PDF with structure → TOC shows in left panel with correct nesting
- [ ] Click TOC item → Reader jumps to correct page
- [ ] Reader shows exact page content with line numbers (if enabled)
- [ ] Reader page persistence across refresh
- [ ] Select >3 chars in Reader → QuoteChip appears in Chat input
- [ ] Ask question with QuoteChip → Context is passed to LLM successfully
- [ ] Notepad Panel works (add, edit, delete, link to page)

## Grounding & Latency (Backend)
- [ ] In-process vector cache (numpy) fallback functions gracefully when Atlas $vectorSearch is unavailable
- [ ] Embedding runs async; `all-MiniLM-L6-v2` loaded once on startup
- [ ] Query rewriter skipped for simple / standalone queries (check logs)
- [ ] Ingestion CPU work happens in `asyncio.to_thread` (no event loop blocking)
- [ ] Latency benchmark meets p95 < 2s for standard queries
