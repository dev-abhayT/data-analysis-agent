# Capability: Multi-File Join

## What It Does

Allows a user to upload 2–3 CSV or Excel files in the same session and ask questions that span multiple files; Gemini identifies a join key and the executor merges the DataFrames before running the analysis query.

## Inputs

| Input | Type | Source | Required |
|-------|------|---------|----------|
| `session_id` | UUID string | URL path parameter | Yes |
| Multiple uploaded datasets | 2–3 files previously uploaded to the session | Session `datasets` list | Yes (at least 2 datasets in session) |
| `question` | String (plain English cross-file question) | POST `/sessions/{session_id}/queries` request body | Yes |

## Outputs

| Output | Type | Destination |
|--------|------|-------------|
| `join_key_suggestion` | Object `{left_dataset, right_dataset, left_column, right_column}` | Stored in `queries.reasoning_trace` JSON; not separately surfaced in Phase 1 UI |
| Streamed prose answer | SSE token events | SSE stream |
| Summary table | SSE table event | SSE stream |
| Merged DataFrame (in-memory) | pandas DataFrame (not persisted) | Query-scoped executor scope only |

## External Calls

| System | Operation | On Failure |
|--------|-----------|------------|
| Gemini API | Non-streaming call in `generate_code` node: given dataset profiles + question, produce pandas code that merges the relevant DataFrames and answers the question | Emit SSE error event; mark query `status=error` |
| Local filesystem | Load all session datasets into pandas DataFrames | Emit SSE error event if any file is missing |

## Business Rules

- Multi-file join is triggered automatically whenever a session has 2 or more uploaded datasets and the question references columns or concepts that appear in more than one dataset profile. There is no explicit "join mode" switch; the `generate_code` node always receives all dataset profiles and decides whether to merge.
- The `generate_code` Gemini prompt includes: (a) the profile JSON for every dataset in the session, (b) the variable name each DataFrame is bound to in the `exec()` scope (the filename without extension, snake_cased), and (c) the user's question. Gemini decides which datasets to merge and on which keys.
- The executor binds each dataset as a named DataFrame: a file named `orders.csv` becomes `orders`, `customer_data.xlsx` becomes `customer_data`. Variable names are sanitized (non-alphanumeric replaced with `_`, leading digits prefixed with `df_`).
- Maximum of 3 datasets per session is enforced at upload time (HTTP 400 if a 4th file is uploaded).
- Merged DataFrames are never written to disk — they exist only in the in-process query scope for the duration of a single query execution.
- If the generated pandas code attempts a join on a column that does not exist (a hallucination), the `execute_code` node catches the `KeyError` and emits an `error` SSE event with the message so the user can rephrase.
- The join strategy (inner/left/outer) is chosen by Gemini based on the question; the generated code must use `pd.merge()` explicitly.

## Success Criteria

- [ ] Uploading 2 CSV files to the same session and asking "How many orders did each customer place?" (where one file has orders and the other has customers) returns a correct merged answer without the user specifying a join key.
- [ ] The generated pandas code in `queries.pandas_code` uses `pd.merge()` referencing the correct column names from both files.
- [ ] A join on a non-existent column causes an `error` SSE event rather than a silent wrong answer.
- [ ] Uploading a 4th file to a session with 3 existing datasets returns HTTP 400.
- [ ] A question that only references one dataset when multiple are uploaded still works correctly (single-DataFrame code path, no merge).
- [ ] The merged DataFrame result is not written to `data/uploads/` — only the original uploaded files persist on disk.
