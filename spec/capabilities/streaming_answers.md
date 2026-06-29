# Capability: Streaming Answers

## What It Does

Delivers the agent's prose answer to the browser word-by-word over a Server-Sent Events (SSE) connection, so the user sees the response building in real time rather than waiting for the full answer to be assembled.

## Inputs

| Input | Type | Source | Required |
|-------|------|---------|----------|
| `session_id` | UUID string | URL path parameter | Yes |
| `query_id` | UUID string | URL path parameter | Yes |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| Token events | `event: token\ndata: {"text": "<word or punctuation>"}\n\n` repeated for every Gemini streaming chunk | SSE stream to browser |
| Table event | `event: table\ndata: {"columns": [...], "rows": [...]}\n\n` once, after all tokens | SSE stream to browser |
| Clarification event | `event: clarification\ndata: {"question": "<text>"}\n\n` once, in place of tokens when question is ambiguous | SSE stream to browser |
| Error event | `event: error\ndata: {"message": "<text>"}\n\n` once, on any unhandled exception | SSE stream to browser |
| Done event | `event: done\ndata: {}\n\n` as the final event | SSE stream to browser |

## External Calls

| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini API | `stream_answer` node calls Gemini in streaming mode; each yielded chunk is forwarded as a `token` event | Emit `error` event; mark query `status=error` |
| SQLite | Read `queries` row to verify it exists and belongs to session | Return HTTP 404 if query not found; HTTP 403 if session mismatch |

## Business Rules

- The SSE endpoint `GET /sessions/{session_id}/queries/{query_id}/stream` is opened by the browser immediately after it receives the `query_id` from the POST response.
- If the query is already `status=completed` when the SSE endpoint is opened (e.g. client reconnects), the server re-streams the full `answer_text` from the DB as a single `token` event followed by the stored `summary_table` (if any) as a `table` event, then `done`.
- If the query is `status=error`, the server immediately emits a single `error` event with the stored error message, then `done`.
- If the query is `status=pending`, the server holds the connection open and forwards events from the LangGraph graph as they are generated.
- Each SSE `token` event carries exactly one chunk as returned by the Gemini streaming SDK (may be a word, sub-word, or punctuation mark — the frontend concatenates them without adding spaces).
- The `table` event is emitted only when the execution result contains at least one row; it is omitted otherwise.
- The connection must not be held open longer than 120 seconds; if the graph has not completed by then, the server emits an `error` event and closes the stream.
- The FastAPI `StreamingResponse` content type is `text/event-stream`; cache-control headers must disable caching (`Cache-Control: no-cache`).
- The frontend's `EventSource` uses the native browser API; on `error` event type the browser does not auto-reconnect.

## Success Criteria

- [ ] Opening the SSE stream for a `pending` query delivers the first `token` event within 10 seconds.
- [ ] All tokens arrive in order and concatenate to the full prose answer with no gaps or duplicates.
- [ ] The `done` event is the last event emitted on every successful query.
- [ ] Re-opening the stream for a `completed` query returns the same answer (from DB) without calling Gemini again.
- [ ] Re-opening the stream for an `error` query returns an `error` event immediately.
- [ ] A `table` event is present after tokens on a question requesting aggregation; absent on a question requesting a prose-only answer.
- [ ] The SSE `Content-Type` header is exactly `text/event-stream`.
- [ ] The connection closes cleanly within 1 second of the `done` event being sent.
