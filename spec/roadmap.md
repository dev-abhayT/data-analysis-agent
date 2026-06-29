# Data Analysis Agent — Roadmap

## What This Agent Does

A chat-style web data analysis agent that lets users upload CSV or Excel files and ask plain-English questions about their data. The agent automatically profiles uploaded files, suggests starter questions, and streams prose answers backed by real pandas computations. It targets both technical owners and non-technical stakeholders who need to extract insights from tabular data without writing code.

## Who Uses It

Primary users: the technical owner and non-technical stakeholders (analysts, managers) who need to understand their data. Users upload a file, ask questions in plain English, and receive production-quality answers they can act on.

## Core Problem Being Solved

Non-technical users cannot run pandas/SQL queries. Technical users waste time writing boilerplate data exploration code for every new dataset. This agent eliminates both problems: it profiles the data automatically, lets users ask questions naturally, and generates + runs the code on their behalf — streaming the answer back in prose.

## Success Criteria

- [ ] User uploads a CSV and sees a complete data profile (row count, columns, types, nulls, sample values) within 5 seconds
- [ ] Agent suggests 3 relevant starter questions tailored to the actual column names and data
- [ ] User asks a plain-English question and receives a streaming answer within 30 seconds backed by real pandas execution
- [ ] Optional inline summary table (top-N rows or aggregation) renders in the chat response
- [ ] Every query, generated code, and result is stored in SQLite for full audit trail

## What This Agent Does NOT Do (Out of Scope)

- No authentication or access control — open shared access
- No cloud storage — files stored on local server only
- No SQL databases as data sources (CSV/Excel only)
- No scheduled/automated reports — interactive queries only
- No multi-user isolation or tenancy

## Key Constraints

- Files up to 100 MB each; answers within 30 seconds
- LLM: Google Gemini via `AGENT_GEMINI_API_KEY` (already in `.env`)
- Files stored on local filesystem under `data/uploads/`
- Full audit trail required: every query, code run, result, and export stored in SQLite
- Production-quality answers — users act on them

## Phases of Development

### Phase 1 — Upload, Profile, and Ask

- **Goal:** User uploads a CSV, sees an auto-generated data profile and 3 starter questions, types a question, and receives a streaming Gemini answer with an optional inline summary table — all real end-to-end.
- **Independent slices (parallel build units):**
  - `slice-a` (backend, `src/`) — file upload endpoint, pandas profiling tool, starter-question generation via Gemini, LangGraph analysis graph, SSE streaming query endpoint, Gemini streaming support, DB models (sessions/datasets/queries); deps: none
  - `slice-b` (frontend, `frontend/`) — file upload dropzone, profile panel, starter-question chips, chat interface with streaming text renderer, inline summary table; clearly-labelled stubs for export/code-trace/token-cost; deps: none
- **Key surfaces / files:**
  - slice-a: `src/api/upload.py`, `src/api/query.py`, `src/api/sessions.py`, `src/tools/profiler.py`, `src/tools/executor.py`, `src/graph/nodes.py`, `src/graph/state.py`, `src/graph/agent.py`, `src/graph/edges.py`, `src/graph/runner.py`, `src/db/models.py`, `src/llm/providers/gemini.py`, `src/prompts/analysis.md`, `src/api/__init__.py`, `src/config/settings.py`
  - slice-b: `frontend/src/app/page.tsx`, `frontend/src/components/FileUploader.tsx`, `frontend/src/components/ProfilePanel.tsx`, `frontend/src/components/StarterQuestions.tsx`, `frontend/src/components/ChatInterface.tsx`, `frontend/src/components/SummaryTable.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/types.ts`
- **Gate command:** `uv run alembic upgrade head && uv run pytest tests/ -x -v`
- **How the user tests it:** Open `http://localhost:8001/app/` → drag-drop a CSV file → see profile card appear (row count, column names, data types, null counts, 3 sample values per column) → see 3 suggested questions → click one or type a question → watch answer stream word by word → see optional summary table below the answer. Export button and code-trace section are clearly labelled "[Coming in Phase 2]" stubs and never look like bugs.

### Phase 2 — Full Feature Completion

- **Goal:** Wire all Phase-1 stubs into real functionality: session persistence across reloads, downloadable CSV export, collapsible code trace, token usage + estimated cost display, AND graceful meta/descriptive question handling via `describe_dataset`.
- **Independent slices (parallel build units):**
  - `slice-a` (backend, `src/`) — `describe_dataset` node + routing update + graph wiring, session-restore API (GET /sessions/{id} full state), CSV export endpoint (GET /sessions/{session_id}/queries/{query_id}/export), code/usage SSE events emitted from `finalize`, token tracking from Gemini metadata; deps: none
  - `slice-b` (frontend, `frontend/`) — session restore from localStorage on page load, real ExportButton component wired to export API, real CodeTrace accordion (collapsible, displays code or "Answered from dataset profile."), real TokenCost badge (input+output tokens + ~$0.00X cost), ChatInterface SSE handler updated to process `code`/`usage`/`table` events; deps: none
- **Key surfaces / files:**
  - slice-a: `src/api/sessions.py`, `src/api/export.py` (new), `src/graph/nodes.py` (add `describe_dataset`, update `route_question`), `src/graph/agent.py`, `src/graph/edges.py`, `src/graph/state.py`, `src/db/models.py`, tests/test_export.py (new), tests/test_query.py (describe-path tests added)
  - slice-b: `frontend/src/app/page.tsx`, `frontend/src/components/ExportButton.tsx` (new), `frontend/src/components/CodeTrace.tsx` (new), `frontend/src/components/TokenCost.tsx` (new), `frontend/src/components/ChatInterface.tsx`, `frontend/src/lib/api.ts`, `frontend/src/lib/types.ts`
- **Gate command:** `uv run pytest tests/ -x -v`
- **How the user tests it:** Reload the page → previous session data and conversation history still shows. Ask "What is this data about?" → receive a natural-language description with bullet-point insights, no code shown. Ask a normal analytical question → see token count + estimated cost below the answer, click "Show code" → see the pandas code that ran in a collapsible section, click "Download CSV" → file downloads.
