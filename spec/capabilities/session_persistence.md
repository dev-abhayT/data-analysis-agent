# Capability: Session Persistence

## What It Does

Preserves a user's uploaded datasets and full conversation history across browser page reloads by storing a session ID in `localStorage` and rehydrating the session state from the SQLite database on page load.

## Inputs

| Input | Type | Source | Required |
|-------|------|---------|----------|
| `session_id` | UUID string | Browser `localStorage` key `"data_agent_session_id"` | No (if absent, a new session is created) |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| Rehydrated session state | `{session_id, datasets: [...], queries: [...]}` | Browser React state (populated from API on page load) |
| `session_id` | UUID string | Written to `localStorage["data_agent_session_id"]` on new session creation |

## External Calls

| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | `GET /sessions/{session_id}` — load session row | If 404 (stale ID), clear localStorage and create a new session |
| SQLite | `GET /sessions/{session_id}/datasets` — list datasets | Return empty datasets list; show "No files uploaded" state |
| SQLite | `GET /sessions/{session_id}/queries` — list conversation history | Return empty query list; show empty chat state |
| Local filesystem | Verify uploaded files still exist at `file_path` | Mark dataset as `status=missing`; show warning in profile card |

## Business Rules

- On page load, the frontend reads `localStorage["data_agent_session_id"]`. If present, it calls `GET /sessions/{session_id}` to rehydrate. If the session is not found (HTTP 404), the stale ID is removed from `localStorage` and a fresh session is created via `POST /sessions`.
- On first visit (no `localStorage` key), the frontend calls `POST /sessions` immediately to create a session and stores the returned `session_id` in `localStorage`.
- All subsequent API calls (upload, query) include the `session_id` from `localStorage` — it is never regenerated for an existing session.
- Rehydrated conversation history is displayed in chronological order with the same formatting as live-streamed answers (prose + inline table if present).
- Session names are optional; the API supports `PATCH /sessions/{session_id}` to set a human-readable name, but this is a Phase 2 UI feature. The DB column exists from Phase 1.
- Sessions are never deleted automatically. The Phase 1 UI shows only the current session; the Phase 2 session selector lists all sessions by creation date.
- Datasets listed on rehydration display their profile card (from stored `profile_json`) without re-uploading the file.
- If a dataset's file is missing from the filesystem (e.g. server was reinstalled), the profile card shows a "File missing — re-upload to query" warning, and the dataset cannot be queried until re-uploaded.

## Success Criteria

- [ ] After uploading a file and asking a question, reloading the page restores the profile card and the full conversation (question + answer + summary table if present) without re-uploading.
- [ ] After reloading, asking a new question in the restored session succeeds and appends to the existing conversation history.
- [ ] If `localStorage` contains a stale session ID (deleted from DB), the page loads cleanly with a new empty session rather than showing an error.
- [ ] The `session_id` written to `localStorage` on first visit is the same UUID used in all subsequent API calls.
- [ ] Rehydrated query history displays answers in the same visual format as live-streamed answers (prose text + inline table).
- [ ] A dataset whose file is missing from the filesystem shows a warning indicator on its profile card in the rehydrated state.
