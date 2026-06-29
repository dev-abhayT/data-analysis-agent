# UI

## UI Type

Chat-style web interface. Single-page application (Next.js 15 static export) served from the FastAPI backend at `/app/`. No navigation or routing — one page, one session context.

---

## Views / Screens

### Screen: Main Analysis Page (`/app/`)

**Purpose:** The single workspace. Houses file upload, data profile, starter questions, and the chat conversation in one view.

**Layout (left-to-right on wide screens, stacked on mobile):**

```
┌─────────────────────────────────────────────────────────────┐
│  Data Analysis Agent                    [session indicator]  │
├──────────────────┬──────────────────────────────────────────┤
│  LEFT PANEL      │  RIGHT PANEL — Chat                      │
│  ─────────────   │  ──────────────────────────────────────  │
│  [File Upload    │  [Conversation history — message list]   │
│   Dropzone]      │                                          │
│                  │  User: "What is revenue by region?"      │
│  [Profile Card   │  Agent: "The North region leads with…"   │
│   per file]      │         [SummaryTable]                   │
│  • row count     │         [CodeTrace accordion — stub P1]  │
│  • columns       │         [TokenCost badge — stub P1]      │
│  • types         │                                          │
│  • nulls         │  [Input box + Send button]               │
│  • samples       │                                          │
│                  │  [Export button — stub P1]               │
│  [Starter Qs     │                                          │
│   chips]         │                                          │
└──────────────────┴──────────────────────────────────────────┘
```

**Key elements — LEFT PANEL:**
- `FileUploader` — drag-and-drop zone plus "Browse" button; accepts `.csv`, `.xlsx`, `.xls`; shows filename + size + upload progress bar after selection; error state for oversized or unsupported files. Phase 1: single file. Phase 2: second file slot appears after first upload (shows "Add second file for join queries").
- `ProfileCard` — appears per uploaded file after profiling completes. Shows: filename badge, row count, a two-column table of column name / dtype / null count, and up to 5 sample values per column in a collapsed expandable sub-row.
- `StarterQuestions` — 2–3 clickable chip buttons labelled with the Gemini-generated starter questions. Clicking a chip populates the chat input and submits it.

**Key elements — RIGHT PANEL:**
- `ChatInterface` — scrollable message list. Each message is a `MessageBubble`.
- `MessageBubble (user)` — right-aligned, blue background, plain text.
- `MessageBubble (agent)` — left-aligned, white card. Contains: prose text (streaming, word-by-word render), optional `SummaryTable` below the prose, optional `CodeTrace` accordion (Phase 2 — shows "Code trace — available in Phase 2" stub in Phase 1), optional `TokenCost` badge (Phase 2 — shows "Cost — Phase 2" stub in Phase 1).
- `SummaryTable` — rendered when the SSE `table` event arrives. Styled HTML table with sticky header, alternating row shading, max-height scroll. Present and real in Phase 1.
- `CodeTrace` (Phase 1: stub labelled "Code it ran — available in Phase 2"; Phase 2: real accordion showing `generated_code` in a `<pre>` block + `reasoning_trace` in prose below).
- `TokenCost` (Phase 1: stub labelled "Token cost — Phase 2"; Phase 2: real badge showing `N prompt + M completion tokens ≈ $X.XXXX`).
- Chat input — full-width text area + "Ask" button. Disabled while a response is streaming. "Ask" triggers `POST /api/sessions/{id}/query` then subscribes to SSE stream.
- `ExportButton` (Phase 1: stub labelled "Download CSV — Phase 2"; Phase 2: real button that calls `POST /api/.../export` then navigates to download URL).

**Clarification flow:** If the SSE stream sends a `clarification` event, the agent message bubble shows the clarifying question in amber styling with a re-submission input pre-filled with the original question, prompting the user to add context.

---

### Phase 1 stub labelling convention

Every stub element carries `title="Coming in Phase 2"` tooltip text and a muted badge "(Phase 2)". Stubs are never disabled or hidden — they are visible but inert. Their color is `text-gray-400` / `border-gray-200` to signal "not yet active". This ensures stubs are never mistaken for broken functionality.

---

## Error States

| State | Trigger | UI treatment |
|-------|---------|--------------|
| Upload error (too large) | File > 100 MB | Inline error banner below dropzone: "File too large — max 100 MB" |
| Upload error (unsupported type) | Non-CSV/Excel file | Inline error: "Unsupported format — upload a .csv or .xlsx file" |
| Profile error | Pandas parse failure | ProfileCard shows error state: "Could not parse this file. Check that it is a valid CSV or Excel file." |
| Query error | Gemini API failure or executor crash | Agent message bubble shows error in red styling with "Try again" button that resubmits the same question |
| Network error | Fetch or SSE disconnect | Toast notification: "Connection lost — trying to reconnect…"; SSE reconnects automatically via EventSource |
| Session not found | Session ID in localStorage no longer in DB | Full-page prompt: "Session expired or not found. Start a new session." with a "New Session" button |

## Loading States

- **File upload:** Upload progress bar on the dropzone; ProfileCard shows skeleton loader while profiling and starter-question generation run.
- **Query streaming:** Blinking cursor appended to the last streamed token while SSE is open. "Ask" button shows spinner and is disabled.
- **Export (Phase 2):** Export button shows spinner while export CSV is being generated server-side.

## Tech Stack

Next.js 15 (static export, `output: 'export'`, `basePath: '/app'`), React 19, TypeScript, Tailwind CSS v4. State management: React `useState` / `useRef` (no external state library). SSE consumed via the browser `EventSource` API. Bundled with `pnpm build` to `frontend/out/`; served by FastAPI as static files at `/app`.
