# Capability: Data Query and Answer

## What It Does

Accepts a plain-English question about an uploaded dataset, classifies whether clarification is needed, generates pandas code to compute the answer, executes it safely in a sandboxed scope, and streams a prose answer incorporating the computed results, with an optional inline summary table.

## Inputs

| Input | Type | Source | Required |
|-------|------|---------|----------|
| `session_id` | UUID string | URL path parameter | Yes |
| `question` | String (plain English) | POST request body JSON | Yes |
| `dataset_ids` | Array of UUID strings | POST request body JSON (optional; defaults to all datasets in session) | No |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| `query_id` | UUID string | POST response body JSON |
| Streamed tokens | SSE events `{type: "token", content: "<word>"}` | SSE stream on `GET /sessions/{session_id}/queries/{query_id}/stream` |
| Summary table | SSE event `{type: "done", summary_table: {columns, rows} \| null}` | SSE stream (final event) |
| Clarification question | SSE event `{type: "clarification", question: "<text>"}` | SSE stream (if routed to clarification branch) |
| `queries` row | DB record with `answer_text`, `pandas_code`, `status` | SQLite `queries` table |

## External Calls

| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | Read session datasets (`profile_json`, `file_path`); write query row | Emit SSE error event; mark query `status=error` |
| Local filesystem | Load dataset files into pandas DataFrames | Emit SSE error event; mark query `status=error` |
| Gemini API | `route_question`: classify ambiguity (non-streaming structured output) | Assume question is clear; proceed to code generation |
| Gemini API | `generate_code`: produce pandas code as structured JSON output | Emit SSE error event; mark query `status=error` |
| Gemini API | `stream_answer`: stream prose answer given question + execution result | Emit SSE error event; mark query `status=error` |
| sandboxed `exec()` | Execute generated pandas code with DataFrames in scope | Emit SSE error event with exec error message; mark query `status=error` |

## Business Rules

- A question submitted to a session with no uploaded datasets returns HTTP 400 with message `"No datasets uploaded to this session"`.
- `session_id` must reference an existing session; if not found, return HTTP 404.
- The `generate_code` node requests pandas code from Gemini as structured JSON output: `{code: "<Python code string>", description: "<what the code does>"}`. The generated code may only access DataFrame variables named after the dataset filenames (without extension), `pd` (pandas), and `np` (numpy). Access to `os`, `sys`, `open`, `subprocess`, `__import__`, and all other builtins not explicitly whitelisted is blocked in the `exec()` sandbox.
- If code execution raises an exception, `handle_error` emits an error SSE event and marks the query `status=error`. The error message is shown to the user verbatim so they can rephrase.
- The execution result is captured as `{"columns": [...], "rows": [[...], ...]}` — up to 50 rows are included in the result passed to `stream_answer`; the full result is used for CSV export.
- The summary table in the final SSE `done` event is the same `{columns, rows}` structure, capped at 20 rows for inline display.
- `queries.answer_text` is written incrementally as tokens arrive (updated at completion) and `queries.pandas_code` is written after code generation. Both are stored for audit and Phase 2 code-trace display.
- If the route_question node determines clarification is needed (confidence below threshold), the graph emits a `clarification` SSE event and terminates. The client is expected to re-submit with an updated question incorporating the clarification answer.
- Token streaming must produce the first token within 10 seconds of the SSE stream being opened.

## Success Criteria

- [ ] Submitting a clear question to a session with an uploaded CSV returns a `query_id` immediately (HTTP 200) within 500 ms.
- [ ] Opening the SSE stream for that `query_id` delivers the first `token` event within 10 seconds.
- [ ] The streamed prose answer references actual computed values from the dataset (not hallucinated numbers).
- [ ] The `done` event is emitted after all tokens; its `summary_table` is non-null when the question requests aggregation or filtering.
- [ ] Submitting an ambiguous question causes a `clarification` SSE event to be emitted instead of tokens, and `status` stays `pending` until re-asked.
- [ ] Generated pandas code that raises an exception causes an `error` SSE event and marks the query `status=error`.
- [ ] The `queries` row in SQLite contains `answer_text` (full answer) and `pandas_code` after a completed query.
- [ ] Sandboxed code cannot access `os`, `subprocess`, or `open` — attempting to do so in the question causes an `error` event rather than executing the forbidden call.
