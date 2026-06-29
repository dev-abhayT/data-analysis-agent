# Architecture

## System Overview

The data analysis agent is a monorepo with a Python FastAPI backend serving both the REST/SSE API and the compiled Next.js static frontend. The LangGraph agent graph runs inline in the FastAPI process (no separate worker). Uploads are stored on the local filesystem; metadata and audit trail go into SQLite.

```
Browser (Next.js static export)
    │  HTTP REST + SSE (same origin /api/*)
    ▼
FastAPI app (uvicorn, port 8001)
    ├── /app/*          → serves frontend/out/ (static)
    ├── /sessions/*     → session management
    ├── /datasets/*     → file upload + profiling
    ├── /queries/*      → query submission + SSE stream
    ├── /health         → health check
    └── LangGraph agent (inline)
            ├── route_question  (Gemini)
            ├── generate_code   (Gemini)
            ├── execute_code    (pandas, sandboxed exec)
            └── stream_answer   (Gemini streaming)
                    │
                    ▼
            SQLite (data/agent.db) + local files (data/uploads/)
```

## Data Flow

1. **Upload**: Browser POSTs multipart file → FastAPI saves to `data/uploads/<session_id>/<filename>` → pandas reads file → profiler computes row count, column names, dtypes, null counts, 3 sample values per column → Gemini generates 3 starter questions → profile + questions returned as JSON → stored in `datasets` table.

2. **Query**: Browser POSTs question text + session_id → FastAPI creates `queries` row (status=pending) → returns `{query_id}` → Browser opens SSE stream `GET /queries/{query_id}/stream` → FastAPI invokes LangGraph agent → agent streams tokens via SSE → Browser renders tokens word-by-word → on final event, browser renders summary table if present.

3. **LangGraph Graph**: `route_question` → `generate_code` → `execute_code` → `stream_answer`. On any error: → `handle_error`. On ambiguous question: → `ask_clarification` → END (client re-submits with clarification).

## File Storage

- Upload directory: `data/uploads/` (created at startup if missing)
- Path per file: `data/uploads/{session_id}/{original_filename}`
- Max file size: 100 MB (enforced at FastAPI upload endpoint)
- Files never deleted automatically (audit requirement)

## SSE Streaming Design

- Client GETs `/sessions/{session_id}/queries/{query_id}/stream`
- Server sends `data: {"type": "token", "content": "..."}` events as Gemini yields tokens
- Final event: `data: {"type": "done", "summary_table": [...] | null}`
- On error: `data: {"type": "error", "message": "..."}`
- EventSource reconnects automatically on disconnect; server re-streams from `queries.answer_text` buffer if already completed

## Observability

- LangSmith tracing: enabled via `LANGCHAIN_API_KEY` in `.env` (optional — agent works without it)
- structlog: all requests and agent runs logged as JSON to stdout
- SQLite audit trail: every query, generated code, result, token counts stored in `queries` table

---

## Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| Web framework | FastAPI 0.115+ with uvicorn |
| Agent orchestration | LangGraph 0.1+ |
| LLM | Google Gemini (`gemini-2.5-flash`, configurable via `AGENT_GEMINI_MODEL`) via `google-genai` SDK |
| Data processing | pandas 2.x, openpyxl (Excel), numpy |
| Database | SQLite via SQLAlchemy 2.0 ORM + Alembic migrations |
| Streaming | Server-Sent Events (SSE) via FastAPI StreamingResponse |
| Frontend framework | Next.js 15 (static export mode) |
| Frontend styling | Tailwind CSS v3 |
| Frontend language | TypeScript |
| Observability | LangSmith (optional), structlog (structured JSON logs) |
| File storage | Local filesystem (`data/uploads/`) |
| Python package manager | uv |
| Frontend package manager | pnpm |

> **Assumed:** The intake brief specifies `gemini-2.0-flash` but `harness/patterns/tech-stack.md` states that model is unavailable for new users as of 2026. `gemini-2.5-flash` is used as the current fast-path model. Configurable via `AGENT_GEMINI_MODEL` env var.

| Key library | Version pin | Purpose |
|-------------|-------------|---------|
| `google-genai` | ≥1.0 | Gemini SDK (streaming + sync) |
| `langgraph` | ≥0.2 | LangGraph agent graph |
| `langsmith` | ≥0.1 | LangSmith tracing |
| `pandas` | ≥2.0 | Data profiling and code execution scope |
| `openpyxl` | ≥3.1 | Excel .xlsx reading |
| `xlrd` | ≥2.0 | Legacy Excel .xls reading |
| `fastapi` | ≥0.111 | HTTP API and SSE endpoint |
| `uvicorn` | ≥0.29 | ASGI server |
| `sqlalchemy` | ≥2.0 | ORM and DB session |
| `alembic` | ≥1.13 | DB migrations |
| `structlog` | ≥24.0 | Structured JSON logging |
| `python-multipart` | ≥0.0.9 | Multipart upload parsing |
| `sse-starlette` | ≥2.0 | SSE streaming response |
| `pydantic-settings` | ≥2.0 | Settings from `.env` |

**Avoid:**
- `subprocess` or `os.system` inside generated pandas code — sandboxed `exec()` must restrict builtins.
- Client-side state management libraries (Redux, Zustand) — `useState` + `api.ts` is sufficient.
- `aiofiles` for graph node I/O — keep pandas synchronous; use `asyncio.to_thread` only at the API boundary.
