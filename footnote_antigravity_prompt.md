# FootNote — Master Implementation Prompt (for Antigravity IDE + Claude Sonnet 4.6)

> Paste everything from "ROLE" to the end of "Definition of Done" into Antigravity as ONE task.
> Use **Planning mode**. Appendix A (handwritten-notes transcription) is the source of truth if anything below seems to conflict.

---

## ROLE

You are a senior full-stack engineer (FastAPI + MongoDB + RAG + Next.js/React/Tailwind) working inside the existing **FootNote** repository (`backend/`, `frontend/`, `scripts/`, `docker-compose.yml`).
Your job: implement the product spec in section 2 **accurately**, at production quality, and remove everything that makes answers slow.
Priorities, in order: **(1) answers are accurate and grounded in the uploaded book, (2) low latency per response, (3) clean UX exactly as specified.**

## 1. OPERATING RULES (follow strictly)

1. **Read before you write.** Read the whole repo first. For anything in `frontend/`, first read `frontend/AGENTS.md` and the relevant guides in `frontend/node_modules/next/dist/docs/` (Next.js 16.3.5, React 19.2.8, Tailwind v4 — APIs differ from your training data; heed deprecation notices).
2. **Plan first.** Produce an Implementation Plan and Task List (Antigravity artifacts if available, otherwise `docs/PLAN.md`) before editing code. Then execute **phase by phase** (section 5). After each phase: run tests/lint/typecheck, fix failures, make one git commit `phaseN: <summary>`.
3. **Do not ask me questions.** Where the spec is ambiguous, use the decisions in section 2.3, and record any other decision in `docs/CHANGES.md`.
4. **Never fabricate results.** If you cannot run MongoDB/Groq/Docker in your environment, say so, write the code + unit tests with fakes, and mark benchmark numbers as "NOT MEASURED". Never invent latency numbers.
5. **Backward compatibility:** existing tests (`backend/tests/*`) must keep passing. Keep `run_rag_pipeline(...)`, `PipelineResult` (fields `answer, passages, intent, rewritten_query, latency_ms`), `retriever._keyword_fallback(query, match_filter, top_k)` and `scripts/evaluate_rag.py` working.
6. **No heavy new dependencies.** Backend: only bump `groq` if required for `AsyncGroq`/`extra_body` (pin the new version in `requirements.txt`). Frontend: no Mermaid, no charting/diagram libs, no UI kits — build with React + Tailwind + lucide-react (+ existing framer-motion only if truly useful).
7. **Safety layer stays first.** The crisis check (`safety_checker`) must run before anything else, must never be swallowed by the relevance gate or fallback logic, and the "not a therapist" / mental-health disclaimer behaviour must be preserved (moved to a small footer, see 4.1).
8. **Secrets:** never commit keys. Add any new env vars to `.env.example` and `backend/app/config/settings.py` with sane defaults.
9. Finish with the **Final Report** described at the end.

---

## 2. PRODUCT SPEC (derived from the handwritten notes — Appendix A)

### 2.1 Requirements

| ID | Requirement | Source note |
|----|-------------|-------------|
| R1 | Answers must be **accurate** and based only on the uploaded book. | 05 Dec ① |
| R2 | **Low latency** for each response. | 05 Dec ② |
| R3 | **Answer panel**: must be **short and crisp**. Long answer **only if the user explicitly asks for detail**. | 05 Dec, 06 Dec |
| R4 | **Proof dropdown** under the answer: page no., line no. (best effort) and the **first line** of the quoted paragraph the answer is based on; quote **max 2 lines**, verbatim. Purpose: user can verify it exists in the book. | 05 Dec ①, 06 Dec |
| R5 | **Simple explanation dropdown**: meaning of the answer in very easy language. | 05 Dec ② |
| R6 | **Example dropdown**: explain via a short **story/storytelling**; content is **visible only when the user opens the dropdown**. | 05 Dec ③ |
| R7 | ~~Mind map / diagram dropdown~~ — **REMOVED by the user's later decision.** Build NO diagram/mind-map/flow feature anywhere (no UI component, no parser code, no schema, no SSE event, no prompt section, no dependency). | 05 Dec ④, 06 Dec (superseded) |
| R8 | **Grounding + fallback:** if the question is unnatural / has no relation to the uploaded book → return a friendly **fallback response**. The user may discuss their own problem **only if the answer can come from the book**. | 06 Dec, 04 Dec |
| R9 | **App shell / dashboard:** logo, **sidebar with open/close menu**, chat window (collapsible). | 06 Dec |
| R10 | **Table of contents** of the uploaded book in the sidebar; **click a chapter/section → it opens** in the reader; **dropdown for sub-topics**. | 06 Dec |
| R11 | **Reader**: the book is readable inside the app in a **proper documented format**. | 06 Dec |
| R12 | **Select/copy lines from the book → they appear in the chat** as a quoted chip, and the chat bar prompts "ask what you are not understanding from these lines or paragraph". | 04 Dec ① |
| R13 | **Notepad in the menu bar**: user saves important points/notes/lines. | 03 Dec |
| R14 | **USP** (must be reflected in prompts, empty-state copy, fallback copy): "The user can read the book and discuss with AI about any part of it (also random questions related to the book's theme), and can discuss their own problem only if the answer can come from inside the book." | 04 Dec |
| R15 | **Remove every element that adds avoidable latency** between "user sends question" and "user sees the answer" (section 3.1). | user request |

### 2.2 Target UI layout

```
┌─────────────────┬───────────────────────────────────┬──────────────────────────┐
│ ▣ FootNote    ‹ │  <Book title>   p. 45 / 312   ‹ ›  │ Chat                   × │
│ ─ Library       │                                   │ ┌ Answer card ─────────┐ │
│ ─ Notepad       │   (page text — Lora serif,        │ │ short crisp answer   │ │
│ Contents        │    highlights, optional line      │ │ ▸ Proof · p.45       │ │
│  ▾ Chapter 1    │    numbers)                       │ │ ▸ Simple             │ │
│    · 1.1 …      │                                   │ │ ▸ Example            │ │
│  ▸ Chapter 2    │   [ Ask AI ] [ Save note ] ← float│ │                      │ │
│                 │   on text selection               │ └──────────────────────┘ │
│                 │                                   │ ┌ quote chip (×) ──────┐ │
│                 │                                   │ └ input ───────────────┘ │
└─────────────────┴───────────────────────────────────┴──────────────────────────┘
```
Route stays `/documents/[id]/chat` (existing links depend on it) but now renders this 3-pane **Workspace**. `/` (library) is wrapped in the same AppShell (logo + sidebar). Mobile (<768px): single column with tabs **Read | Chat | Notes**, sidebar as a drawer.

### 2.3 Decisions already made (do not ask)

- The three extras (Proof, Simple, Example) are **sibling accordions**, all **closed by default**, each openable independently.
- Everything for one response is produced by **ONE streamed LLM call** (sectioned output, section 4.3). The Answer streams token-by-token; the accordion contents arrive right after and are ready by the time the user clicks. No extra LLM calls per response.
- "Line no." = line number inside the **stored page text** (what the reader shows), labelled "≈ line N". Page = the page/section index used by the reader (PDF page index; for TXT/MD/DOCX/EPUB it is a logical page). Label it "p. N". Never present a page/line the backend did not compute.
- The proof quote shown to the user is **always real book text** taken from the stored page (never the LLM's own wording).
- Fallback replies use **no LLM call** (instant).
- Reply in the **language the user asked in** (English / Hindi / Hinglish). Proof quotes stay verbatim in the book's language.
- Keep existing design tokens in `globals.css` (warm stone + teal primary), Lora for passages.

---

## 3. WHAT IS WRONG TODAY (verified in the code — fix all of these)

### 3.1 Latency causes → REMOVE / REPLACE

| # | Where | Problem | Fix |
|---|-------|---------|-----|
| L1 | `rag/reranker.py` `CosineReranker` | Re-embeds the query **and every retrieved chunk** on every request although vector search already scored them. | Remove re-embedding. Default reranker becomes a pass-through (sort by retrieval score + drop near-duplicate/adjacent chunks). Keep `BaseReranker` interface. |
| L2 | `rag/embeddings.py`, `retriever.py`, `pipeline.py`, `generator.py` | Sync CPU/network calls (`model.encode`, Groq client) are called inside `async def` → **blocks the whole event loop** (all users stall). | Wrap embeddings in `asyncio.to_thread`; use `AsyncGroq`; parse/chunk/embed in ingestion also via `to_thread`. |
| L3 | `rag/embeddings.py` | SentenceTransformer loads lazily on the **first** request (seconds). | Warm up in `main.py` lifespan (`await asyncio.to_thread(embedding_service.warmup)`), config flag `EMBEDDING_WARMUP=true`. |
| L4 | `rag/query_rewriter.py` | An extra **blocking LLM round-trip** on every message once history ≥ 2, and a **new `Groq()` client per call**. | Rewrite only when intent is `FOLLOW_UP` and the query is short/anaphoric; otherwise skip. Use a heuristic (prepend the previous user question) by default; LLM rewrite only behind `ENABLE_LLM_REWRITE` (default false), async, singleton client, 1.5 s timeout, fallback to heuristic. |
| L5 | `rag/retriever.py` | `$vectorSearch` needs Atlas / a vector index. On local `mongo:7.0` (docker-compose) it **raises on every query**, then falls back to a crude regex OR-search (slow + inaccurate). Also no code creates the vector index. | Probe once at startup (`vector_search_available`). If unavailable → **in-process cosine search with numpy** over the document's chunks (per-document LRU cache of a normalized float32 matrix; invalidate on delete/re-ingest). Keep `_keyword_fallback` as last resort with the **same signature**. Add `scripts/create_vector_index.py` for Atlas (fields: `vector` on `embedding`, 384 dims, cosine + `filter` on `document_id`). |
| L6 | `retriever.get_neighbor_chunks` | Two sequential DB round-trips, always executed. | Only when needed (top-1 chunk is short OR intent is selection/passage explanation); fetch prev+next with **one** `$in` query. |
| L7 | `rag/generator.py`, `pipeline.py` | Non-streaming, `max_tokens=1500`, default reasoning effort on `openai/gpt-oss-20b` → user waits for the full generation. | Stream (SSE). Set low reasoning effort (`extra_body={"reasoning_effort": "low"}` — verify in Groq docs/installed SDK; reasoning tokens count against the token cap, so set caps ≈ 700 short / 1600 detail). Timeout 20 s, `max_retries=1`. |
| L8 | `context_builder.py`, settings | 3000-token context, top-5 chunks + neighbours, verbose emoji system prompt. | Settings-driven budget: `RETRIEVAL_TOP_K=6`, `RERANK_TOP_K=4`, `CONTEXT_MAX_TOKENS=2200`; compact prompt (4.3). Tune with the benchmark; do not reduce accuracy below baseline on `evaluate_rag`. |
| L9 | `chat_service.process_chat` | Strictly sequential DB awaits (doc → conv → save user msg → history → pipeline → save). | `asyncio.gather` independent calls; load history **before** saving the current message; persist the assistant message **after** the stream ends. |
| L10 | `api/chat.py` + `chat_service` + frontend | Response carries up to 5 passages × 500 chars **twice** (in `message.passages` and top-level `passages`) and the UI renders a heavy "Retrieved Context" block per answer. | Return **one** `evidence` object (≤2 lines). Do not serialize retrieved chunks to the client or DB. Delete the "Retrieved Context" UI block. |
| L11 | `document_service._process_document_background` | Parsing, chunking, embedding a whole book run **synchronously on the event loop** → chat freezes for everyone during an upload. | Run each CPU-bound stage in `asyncio.to_thread`. |
| L12 | Frontend `chat/page.tsx` | 4 sequential awaits on load; failed sends silently vanish. | `Promise.all`; visible inline error + retry. |

### 3.2 Accuracy bugs → FIX

| # | Where | Problem | Fix |
|---|-------|---------|-----|
| A1 | `chat_service.get_conversation_history` | `sort("created_at", 1).limit(N)` returns the **oldest** N messages → after 8 messages follow-ups lose recent context; `history[:-1]` then removes the wrong message. | Sort desc, limit N, reverse; exclude the current message by id. |
| A2 | `context_builder.build_context` | Sorts by page **then** cuts at the token budget → the highest-scoring chunk on a later page can be dropped. | Apply the budget in **relevance order** (primary chunks first, then neighbours), *then* sort the kept chunks by reading order. |
| A3 | `schemas/document.py` `SectionResponse.from_mongo` | Reads `doc.get("page")` but the field is stored as `page_number` → page is always null; `parent_id` is never stored. TOC click cannot work. | Map `page_number → page`; store/return `parent_id` (assign ids in `structure_detector`/`indexer`; fall back to `parent_title` for old rows). |
| A4 | No relevance gate | Any query gets an LLM answer even when nothing relevant was retrieved (hallucination risk; contradicts R8). | Relevance gate on the **raw cosine** of the best chunk (`MIN_RELEVANCE`, default 0.25; note Atlas `vectorSearchScore = (1+cos)/2`, so convert). Below → fallback, no LLM call. Calibrate with `evaluate_rag` questions + off-topic ones and report the chosen value. |
| A5 | LLM free-writes quotes/citations | Model can misquote or invent a page. | Server-side **evidence verification** (4.5): model returns an excerpt id + a quote; backend locates it in the stored page text and returns page/lines/quote **computed from real data**. |
| A6 | `structure_detector` | Running headers/footers repeat on many pages and pollute the TOC. | Drop titles that repeat on >25 % of pages (or >5 occurrences), pure page-number lines, and lines shorter than 4 chars. |
| A7 | Pages never stored | Only overlapping chunks are stored → the book cannot be shown in a reader and line numbers cannot be computed. | New `document_pages` collection (Phase 3). |

---

## 4. TARGET DESIGN (contracts — implement exactly)

### 4.1 Response contract (`backend/app/schemas/chat.py`)

```python
class Evidence(BaseModel):
    chunk_id: Optional[str] = None
    page: Optional[int] = None
    line_start: Optional[int] = None      # 1-based, in stored page text
    line_end: Optional[int] = None
    first_line: str                       # first line of the supporting lines (verbatim)
    quote: str                            # <= 2 verbatim page lines
    char_start: Optional[int] = None      # offsets in page text (for highlight in reader)
    char_end: Optional[int] = None
    chapter: Optional[str] = None
    section: Optional[str] = None
    verified: bool = True                 # False => closest matching book text, model quote not found verbatim

class Panels(BaseModel):
    simple: Optional[str] = None
    example: Optional[str] = None         # story

class ChatRequest(BaseModel):            # existing fields kept
    ...
    selected_text: Optional[str] = Field(None, max_length=3000)
    selected_page: Optional[int] = None
    detail: bool = False                  # "In detail" button

class MessageResponse(BaseModel):        # existing fields kept
    ...                                   # `content` == the short answer text (legacy-compatible)
    evidence: Optional[Evidence] = None
    panels: Optional[Panels] = None
    fallback: bool = False
    fallback_reason: Optional[Literal["out_of_scope", "not_in_book", "crisis"]] = None
    suggestions: List[str] = []           # tappable follow-up questions (fallback only)
    disclaimer: bool = False              # mental-health footer, rendered small under the answer
    detail: bool = False
    selection: Optional[dict] = None      # {"text","page"} on user messages that carried a selection
```
`passages` on `MessageResponse`/`ChatResponse` stays for legacy rows but new messages store `[]`. The mental-health disclaimer is **no longer appended to the answer text**; it is the `disclaimer` flag.

### 4.2 Streaming API — `POST /api/chat/stream` (Server-Sent Events)

Keep `POST /api/chat` (non-streaming, same pipeline, same new response shape) for scripts/tests. Both share the core in `rag/pipeline.py`.

```
event: meta      {"conversation_id","user_message_id"}
event: status    {"stage":"searching"|"writing"}
event: answer    {"delta":"..."}                 # many
event: evidence  Evidence                        # after <evidence> section closes + verification
event: simple    {"text":"..."}
event: example   {"text":"..."}
event: fallback  {"reason":"out_of_scope|not_in_book|crisis","text":"...","suggestions":[...]}
event: done      {"message": MessageResponse, "processing_time_ms": int, "timings": {stage: ms}}
event: error     {"detail":"..."}
```
Use `StreamingResponse(media_type="text/event-stream")`, headers `Cache-Control: no-cache`, `X-Accel-Buffering: no`. Handle client disconnect (persist whatever answer exists in `finally`). Frontend consumes with `fetch` + `ReadableStream` (axios cannot stream in the browser) and must send the `x-user-id` header.

### 4.3 Runtime LLM prompt (put in `backend/app/rag/prompts.py`, use verbatim; replace both old system prompts)

```
You are FootNote, a reading companion for ONE uploaded document. You answer ONLY from the numbered EXCERPTS in the user message. You are not a therapist or medical professional.

Output exactly these sections, in this order, each inside its tag, and NOTHING outside the tags:

<answer>…</answer>
<evidence chunk="C2">…</evidence>
<simple>…</simple>
<example>…</example>

Rules
1. <answer>: short and crisp — at most 3 sentences (~60 words). No greeting, no headings, no emojis, do not repeat the question. If MODE is DETAIL: up to ~250 words, short bullets allowed.
2. <evidence chunk="Cn">: Cn is the id of the single excerpt (or S for USER-SELECTED TEXT) that best supports the answer. The body is copied VERBATIM from that excerpt: at most 2 lines (~40 words), contiguous; do not fix typos or punctuation; never paraphrase; never quote anything not in the excerpt.
3. <simple>: the same idea in very easy language, 2–4 short sentences, no jargon, no new facts.
4. <example>: a 4–6 sentence story with a named character in an everyday scene that illustrates the same idea. It must not contradict the excerpts and must not be presented as text from the document.
5. If the excerpts do not contain the answer, output exactly <answer>NOT_FOUND</answer> and nothing else.
6. Never invent page numbers, chapter names, or quotes. Do not diagnose or give personal medical/therapeutic advice; explain what the document says.
7. Write <answer>, <simple> and <example> in the language of the user's question (English, Hindi or Hinglish). <evidence> stays in the document's original language.
```
User message template:
```
DOCUMENT: "{title}"
MODE: {SHORT|DETAIL}
[USER-SELECTED TEXT (page {n}) — id S]      ← only when selected_text present
{selected_text}

EXCERPTS:
[C1 | {chapter} › {section} | p.{page}]
{text}
...
CONVERSATION (last turns, short answers only): ...
QUESTION: {query}
```
Conversation history sent to the LLM uses each previous assistant message's **short answer only** (`content`), truncated to 300 chars, last 4 turns.

### 4.4 Pipeline order + latency budget (`rag/pipeline.py`)

1. `safety_checker.check` (sync, regex) → crisis ⇒ fallback(`crisis`), stop.
2. `classify_intent` + `wants_detail(query)` (new, regex, English + Hinglish: "in detail", "detailed", "elaborate", "explain fully", "long answer", "detail me", "vistar se", "विस्तार से", "poori/puri detail"). `detail=True` from the request also forces DETAIL.
3. `OUT_OF_SCOPE` (greeting/off-topic) ⇒ fallback(`out_of_scope`) with 3 suggestions (built from section titles: "What does '<title>' cover?"). No LLM.
4. Build retrieval query (heuristic follow-up merge; optional LLM rewrite per L4). If `selected_text` present: query = `selected_text[:300] + " " + user question`, and neighbours of the selected page are preferred.
5. Retrieve (Atlas `$vectorSearch` **or** in-process numpy) — embed via thread.
6. Relevance gate (A4) ⇒ fallback(`not_in_book`) with suggestions. (Skip the gate when `selected_text` is present.)
7. Pass-through rerank (+ optional single batched neighbour fetch).
8. Context build (A2, labels `C1..Cn`, selection block `S`).
9. Stream LLM → incremental parser (4.6) → events. `NOT_FOUND` ⇒ fallback(`not_in_book`).
10. Evidence verification (4.5) → `evidence` event.
11. Persist message; `done` event with `timings`.

Instrument every stage with a `StageTimer` (`app/utils/timing.py`) → `timings` dict, structlog line, `done` event. **Targets (warm, local Mongo, Groq):** stages 1–8 ≤ 250 ms p50; first `answer` delta ≤ 1.5 s p50; `done` ≤ 4 s p50. Report actuals; if a target is missed, name the bottleneck from `timings`.

### 4.5 Evidence verification (`backend/app/rag/evidence.py`)

`build_evidence(chunk, quote, page_text) -> Evidence`:
1. Normalize whitespace (collapse `\s+`, join hyphen+newline breaks). Try to find `quote` inside the **stored page text** using a whitespace-flexible regex. Match ⇒ `verified=True`.
2. No match ⇒ pick the best ≤2-line window of the chunk's page by token overlap (Jaccard) with the model quote; if overlap < 0.5 use overlap with the answer text; result `verified=False` (UI labels it "Closest text in the book").
3. From the match compute `line_start/line_end` (count `\n` before offsets in page text), `char_start/char_end`, expand to whole page lines, cap at 2 lines, set `quote` = those page lines joined by `\n` and `first_line` = the first one (trimmed to 200 chars).
4. `page`, `chapter`, `section` come from **chunk metadata**, never from the model.
5. If page text is unavailable (legacy documents) ⇒ same logic against the chunk content; leave `line_*`/`char_*` null.

### 4.6 Streaming tag parser (`backend/app/rag/answer_parser.py`)

Stateful parser fed with arbitrary text fragments; emits typed events. Requirements: tags may be split across fragments (hold back a trailing `<…` prefix); `<answer>` deltas stream immediately **except** buffer the first ~12 chars to detect the `NOT_FOUND` sentinel; tolerate missing/extra whitespace and unknown tags; `<evidence chunk="Cn">` yields `(chunk_label, text)`; if the model omits a section, that panel is simply absent. Unit-test by feeding the same output split at **every** index.

### 4.7 Other backend contracts

- **Pages:** `document_pages` = `{document_id, document_version_id, page_number, content, line_count}`, unique index `(document_id, page_number)`. `GET /api/documents/{id}/pages/{page}` → `{page, total_pages, content, headings:[{id,title,level}]}` (owner-checked like other document routes).
- **Sections:** `GET /api/documents/{id}/sections` returns `id, title, level, parent_id, page, order` (A3).
- **Notes:** collection `notes` `{_id, user_id, document_id, text(<=2000), kind: selection|answer|manual, page?, first_line?, chapter?, section?, message_id?, created_at}`; routes `POST /api/notes`, `GET /api/notes?document_id=`, `PATCH /api/notes/{id}`, `DELETE /api/notes/{id}` (scoped by `user_id`). Cascade-delete with the document.
- **Suggestions** for fallbacks: 3 items from section titles (no LLM).

---

## 5. IMPLEMENTATION PHASES

### Phase 0 — Baseline (no behaviour change)
- Add `app/utils/timing.py` (`StageTimer`) and thread timings through the current pipeline.
- Add `scripts/benchmark_latency.py`: ~20 queries (the `evaluate_rag.py` set + follow-ups + off-topic + Hinglish), N runs, prints p50/p95 **per stage** and total, writes JSON to `docs/perf/<label>.json`. Run it as `baseline` if the stack is available.
- Acceptance: existing tests green; benchmark runs (or is clearly marked NOT MEASURED).

### Phase 1 — Latency (section 3.1 L1–L11)
Implement each row of 3.1 in the files named there. Also: settings additions (`MIN_RELEVANCE`, `CONTEXT_MAX_TOKENS`, `LLM_REASONING_EFFORT`, `LLM_MAX_TOKENS_SHORT/DETAIL`, `ENABLE_LLM_REWRITE`, `EMBEDDING_WARMUP`, `LLM_TIMEOUT_S`), `.env.example`, startup probe + warm-up in `main.py` lifespan, `AsyncGroq` singleton with `timeout`/`max_retries=1`, generator gets `agenerate` / `agenerate_stream` (keep sync `generate` for scripts).
- Acceptance: no synchronous CPU/network call remains inside a request-path coroutine (grep + review); `evaluate_rag.py` retrieval pass-rate ≥ baseline; rerank no longer calls the embedding model.

### Phase 2 — Accuracy & grounding (A1, A2, A4, A5 + R3/R8/R14 logic)
`prompts.py`, `answer_parser.py`, `evidence.py`, `wants_detail`, relevance gate, fallback builder (friendly copy that states the USP: *"I can only answer from '<title>'. Ask me about any part of it, or something you're facing that this book addresses."*), context builder fix, history fix (A1), `PipelineResult` extended (`structured` bundle) but old fields intact.
- Acceptance: unit tests (section 7) pass; an off-topic query ("who won the world cup?") and a greeting return fallback with **zero LLM calls**; a crisis phrase still returns the crisis text first.

### Phase 3 — Data & ingestion (A3, A6, A7)
- New shared `app/ingestion/pipeline.py: run_ingestion(document_id, file_path, on_progress)` used by **both** `document_service._process_document_background` and `scripts/ingest_document.py` (remove the duplicated logic). Heavy stages via `asyncio.to_thread`.
- `indexer.store_pages`, `delete_document_pages`; section ids + `parent_id`; running-header dedupe (A6); invalidate the in-memory vector cache on ingest/delete; `mongodb.py` accessors + indexes for `document_pages` and `notes`.
- `scripts/backfill_pages.py --document-id <id> | --all` (re-parses `documents.file.path`; skip + report when file is missing). Update `cleanup_vectors.py` to include pages.
- Acceptance: ingesting a sample PDF/TXT/MD produces pages, sections with `page` + `parent_id`, chunks; deleting the document removes pages/notes/cache entries.

### Phase 4 — API layer
`/chat/stream`, updated `/chat`, pages route, fixed sections route, notes router (schemas + service + router), register in `main.py`, `MessageResponse.from_mongo` handles legacy rows (no `evidence/panels`).
- Acceptance: `curl -N` on `/api/chat/stream` shows events in the order of 4.2; cross-user access to notes/pages returns 404.

### Phase 5 — Frontend (read `frontend/AGENTS.md` + Next docs first)
Files (create/modify; keep existing service/type style):
```
components/layout/{AppShell,Sidebar,Logo}.tsx
components/reader/{BookReader,TocTree,SelectionToolbar}.tsx
components/chat/{ChatPanel,AnswerCard,Accordion,ProofPanel,QuoteChip,FallbackCard}.tsx
components/notes/NotepadPanel.tsx
hooks/{useChatStream,useTextSelection}.ts
services/{chat,documents,notes}.ts   types/api.ts   app/documents/[id]/chat/page.tsx   app/page.tsx
```
Behaviour:
1. **AppShell/Sidebar (R9):** `Logo` (icon + "FootNote" wordmark), collapsible sidebar (icon-only when collapsed), menu: Library, Notepad. Collapsed state persisted in `localStorage`. Chat pane collapsible (×) with a floating reopen button. Keyboard accessible (`aria-expanded`, focus rings).
2. **TocTree (R10):** built from `sections` by `parent_id`; part → chapter → section levels with chevron dropdowns; clicking loads that `page` in the reader and scrolls to top; current section highlighted; empty state "No structure detected — use page navigation".
3. **BookReader (R11):** fetches `GET /documents/{id}/pages/{n}`; prev/next + page input + progress; `white-space: pre-wrap`, Lora, comfortable measure (~65ch), section headings shown at their page; **line-number gutter toggle**; highlights `char_start..char_end` when opened from a Proof panel ("Open in book"); remembers last page per document (`localStorage`); each page container has `data-page`; reader root has `data-reader-root`. Prefetch next page.
4. **Selection → Chat (R12):** `useTextSelection` (listen to `selectionchange`, scope to `[data-reader-root]`, debounce ~100 ms, derive page from closest `[data-page]`, ignore <3 chars). `SelectionToolbar` floats near the selection (bottom sticky bar on touch): **Ask AI** and **Save note**. Also listen to the `copy` event inside the reader and push the copied text to the chat **QuoteChip** (do not `preventDefault`). `QuoteChip` shows first ~120 chars + "p. N" + ✕, and sets the input placeholder to **"Ask what you're not understanding from these lines or paragraph…"**. Send `selected_text` + `selected_page`; the user bubble shows the quote block.
5. **AnswerCard (R3–R7):** streamed short answer (light Markdown, caret while streaming); a row of 3 accordion headers **Proof · p.N**, **Simple**, **Example**, all closed; a header shows a subtle "preparing…" until its section has arrived, then the content is instant. Proof panel: `p. N · ≈ line a–b · Chapter › Section`, first line emphasised, the ≤2-line quote in Lora italics, badge "Closest text in the book" when `verified=false`, button **Open in book**. Example panel = story text. There is NO diagram/mind-map panel. Footer actions: **Save to notepad**, **In detail** (re-sends the same question with `detail: true`), **Discuss this passage** (loads `evidence.quote` into the QuoteChip). Small muted `disclaimer` line when flagged.
6. **FallbackCard (R8/R14):** muted card with the fallback text and tappable suggestion chips that send the question.
7. **Notepad (R13):** panel (sidebar entry + mobile tab) listing notes for the current document: text, page + first line, "go to page", edit, delete; "Save note" from selection or answer; simple manual add.
8. **Empty state:** copy that states the USP; 4 starter prompts.
9. **Remove** the "Retrieved Context" block, the "Reading document…" filler, and the dead Bookmark button (replaced by Save to notepad). Legacy messages (no `panels`) still render via Markdown.
10. Errors: inline error bubble with Retry; never silently drop a message. Use `Promise.all` for initial loads. Cancel the stream on unmount/new send (`AbortController`).
- Acceptance: `npm run lint`, `npx tsc --noEmit`, `npm run build` all pass; manual QA checklist in `docs/QA.md` executed (section 7).

### Phase 6 — Tests, benchmark, docs
Section 7. Update `README.md` (features, new env vars, SSE contract, how to run benchmark/backfill) and `docs/CHANGES.md`.

---

## 6. HOUSEKEEPING (safe, small)
- `frontend/Dockerfile` uses `node:20-alpine` but locked deps (`react-dropzone`, `attr-accept`, `file-selector`) declare `engines.node >= 22` → bump to `node:22-alpine`.
- `structlog` logs the Mongo URI at startup (`connect_to_mongo`): mask credentials.
- Do **not** touch auth (still demo-user) — out of scope.

## 7. TESTS & QA (must exist and pass)

Backend (`pytest`, use fakes — no network):
- `test_answer_parser.py`: split-at-every-index property test; `NOT_FOUND`; missing sections; unknown tags (including a stray `<diagram>` tag from the model is ignored, never rendered).
- `test_evidence.py`: exact match; whitespace/hyphen differences; paraphrased quote ⇒ `verified=False` and text still from the book; ≤2 lines; no page text (legacy).
- `test_context_builder.py`: relevance-first budget keeps the top chunk even when it is on a later page (A2).
- `test_chat_history.py`: last-N ordering and correct exclusion of the current message (A1).
- `test_wants_detail.py`: English + Hinglish + Devanagari phrases.
- `test_relevance_gate.py`: Atlas score conversion; off-topic ⇒ no LLM call (assert fake LLM not called); crisis still first.
- `test_sections_api.py`: `page` and `parent_id` returned; legacy rows fall back to `parent_title`.
- `test_vector_cache.py`: numpy search returns document-scoped results only (extend the isolation guarantee of `test_document_isolation.py`).
- Existing `test_chunker.py` / `test_document_isolation.py` untouched and green.

Manual QA (`docs/QA.md`, tick each): short answer by default; "explain in detail" and the **In detail** button give a long answer; Proof shows page/line/first line and **Open in book** highlights the same text; Example hidden until opened; no diagram/mind-map UI anywhere; unrelated question ⇒ fallback with suggestions; select text ⇒ toolbar ⇒ chip ⇒ answer references the selection; copy (Ctrl/Cmd-C) in reader ⇒ chip appears; Save note ⇒ appears in Notepad; sidebar/chat collapse; TOC dropdowns open the right page; mobile tabs work; follow-up after >8 messages still uses recent context.

Benchmark: run `scripts/benchmark_latency.py` as `after`; include the before/after table (per stage p50/p95) in the report.

## 8. DO NOT
- Do not add Mermaid/D3/chart libs, extra LLM calls per response, or any per-request re-embedding of chunks.
- Do not show retrieved chunks to the client beyond the ≤2-line evidence.
- Do not let the model output page/line/chapter values; they come from stored metadata.
- Do not remove or weaken the crisis/mental-health safeguards.
- Do not change the public shape of `run_rag_pipeline`/`PipelineResult` fields listed in rule 5.
- Do not leave dead code, unused imports, `any` types in new TS code (use `unknown` + narrowing), or TODOs without a matching entry in `docs/CHANGES.md`.

## DEFINITION OF DONE
- [ ] R1–R15 implemented; each mapped to files in the report.
- [ ] All new + old backend tests pass; frontend lint/tsc/build pass.
- [ ] No sync blocking call in request-path coroutines; warm-up + startup probe in place.
- [ ] Off-topic/greeting ⇒ instant fallback (no LLM); crisis path intact.
- [ ] Streaming endpoint works end-to-end; UI streams the answer and fills accordions.
- [ ] Reader + TOC + selection→chat + Notepad work on desktop and mobile widths.
- [ ] Benchmark before/after included (or explicitly NOT MEASURED with reason).
- [ ] `README.md`, `.env.example`, `docs/CHANGES.md`, `docs/QA.md` updated.

### FINAL REPORT (print at the end)
1. Table: requirement ID → files changed → status (done/partial + why).
2. Latency table: stage p50/p95 before vs after (or NOT MEASURED).
3. Calibrated `MIN_RELEVANCE` value and how it was chosen.
4. Decisions taken beyond the spec, and known limitations (e.g., line numbers are approximate for PDFs; in-memory vector cache is per-process; MiniLM is English-only so Hinglish *queries* retrieve less accurately — recommended follow-up: multilingual 384-dim model such as `paraphrase-multilingual-MiniLM-L12-v2` + re-embedding).
5. Exact commands to run backend tests, frontend checks, backfill and benchmark.

---

## APPENDIX A — Transcription of the handwritten notes (Hindi/English as written; `[?]` = unclear)

**Sunday 05 Dec**
> ① Accurate ② Less latency for each response
> ③ Each response contains "example" column in which user query का response story या storytelling skill का use करके उस column में answer दे!
>
> **[Must be short and crisp] → [Answer panel]** (This answer is on the basis of this proof & quoting from ↓)
>
> ① { Page no., lines. (only first line) of quoted para } — **Drop down**
> Mention just because user को अगर check करना हो कि ये mention है book में या फिर किसी para में mentioned lines से ये mean निकल रहा हो जो response में mentioned है।
>
> ② { Simple response panel } — जिसमें easy language में mean explain होगा user query का — **Drop down** (click drop down which is next to "example")
>
> ③ { Example panel } — story के format में user query को explain या response देगा — **Drop down** (it can be only visible when user click to drop down)
>
> ④ { Mind map | diagram के format में explain response of user query } — **[REMOVED later by the user — do not implement]**

**Monday 06 Dec**
> Left sketch: **Dashboard** · **logo** · **sidebar (must have open/close menu)** · **chat window** ("shut window")
> "Must have drop down for sub topic" — Uploaded book की table of content: जिस भी chapter या section पर click करो वो open हो जाए →
> "जिस book पर trained है वो book reading के लिए available हो proper documented format में"
>
> ① Uploaded book से trained — जिस भी book से जुड़ा कुछ भी पूछा जाए, उसका सटीक answers book के अंदर mentioned knowledge के हिसाब से दें! (short format में) **And if user ask for in detail then give long ans.**
>
> Answer देते time AI अपने response से पहले proof/evidence/trust maintain करने के लिए:
> ① page no., line no., या फिर first line जिसके basis में वो response दे रहा है — वो mention कर दे।
> ② ज्यादा से ज्यादा 2 line से ज्यादा नहीं लेने response/chat panel में।
> ③ सिर्फ 2 line ही इस response में quote करें, mention into [drop down]।
>
> **Ans format:** then response → in very simple format में ~~diagram / mindmaps का प्रयोग करके, या फिर~~ story format में explain करे जो user ने पूछा था; & if user asked any unnatural या फिर जो book upload की उससे दूर-दूर तक कोई relation नहीं है, then **give fallback response.**

**Friday 03 Dec** (red ink, rotated; partly overlapped by calendar — `[?]`)
> feature → **Menu bar में एक Notepad होगा** जिसमें user … important point / mentioned of note … **save होंगे!** `[?]`

**Saturday 04 Dec** (red ink)
> **# How user ask question while he is reading book's any part.**
> ① Try to add feature → when you copy some particular lines from any paragraph of that book, वो lines mentioned हो जाएं (कि chat में) and → chat bar में option आए: **"ask your question (what you are not understanding from these lines or para)"**.
> **मतलब** → user जब copy करे, वो para chat window के notepad में copy हो जाए, and वहाँ mention हो **"ask what you are not understanding from these lines or para"**.
>
> **Now — Our USP is:** "कि user Book read करने के साथ-साथ AI के साथ discussion कर सकता है (book के किसी भी part के बारे में)" (random → "book के theme से related"), **"and अपनी problem discuss कर सकता है, only जिसका answer book के अंदर से मिल पाए"**.
