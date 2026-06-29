# Data Model

## Storage Technology

SQLite via SQLAlchemy 2.0 sync ORM. Schema managed with Alembic migrations. DB file at `data/agent.db` (configurable via `AGENT_DATABASE_URL`). The existing `runs` table (`RunRow`) is retained as-is; new tables extend it.

---

## Entities

### Entity: `runs` (existing `RunRow` — retained unchanged)

Skeleton audit row for raw agent invocations. Not used by the analysis agent's primary flows; kept for backward compatibility.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | TEXT (UUID) | yes | Primary key |
| `status` | TEXT | yes | `pending` / `completed` / `failed` |
| `input_text` | TEXT | no | Original input |
| `output_text` | TEXT | no | Agent output |
| `error_message` | TEXT | no | Error detail if failed |
| `created_at` | TIMESTAMP WITH TIMEZONE | yes | Row creation time |
| `updated_at` | TIMESTAMP WITH TIMEZONE | yes | Last update time |

---

### Entity: `sessions`

Represents a user's working session. Groups datasets and queries together. A session persists until explicitly deleted (never auto-expired).

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | TEXT (UUID) | yes | Primary key |
| `created_at` | TIMESTAMP WITH TIMEZONE | yes | Session start time |
| `updated_at` | TIMESTAMP WITH TIMEZONE | yes | Last activity time |

---

### Entity: `datasets`

Represents one uploaded file within a session. Stores the file path, profile statistics, and generated starter questions.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | TEXT (UUID) | yes | Primary key |
| `session_id` | TEXT (UUID FK → sessions.id) | yes | Owning session |
| `filename` | TEXT | yes | Original filename as uploaded |
| `file_path` | TEXT | yes | Absolute path on local filesystem (`data/uploads/{session_id}/{filename}`) |
| `file_size_bytes` | INTEGER | yes | File size in bytes |
| `row_count` | INTEGER | no | Number of data rows (populated after profiling) |
| `column_names` | TEXT (JSON array) | no | Ordered list of column names |
| `column_types` | TEXT (JSON object) | no | `{column: pandas_dtype_string}` |
| `null_counts` | TEXT (JSON object) | no | `{column: null_count_integer}` |
| `sample_values` | TEXT (JSON object) | no | `{column: [up_to_5_sample_values]}` |
| `starter_questions` | TEXT (JSON array) | no | 2–3 Gemini-generated starter questions |
| `created_at` | TIMESTAMP WITH TIMEZONE | yes | Upload time |

---

### Entity: `queries`

Represents one user question within a session. Stores every artefact of the query round-trip for full audit trail.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | TEXT (UUID) | yes | Primary key |
| `session_id` | TEXT (UUID FK → sessions.id) | yes | Owning session |
| `question` | TEXT | yes | The user's plain-English question |
| `status` | TEXT | yes | `pending` / `running` / `completed` / `failed` / `clarifying` |
| `generated_code` | TEXT | no | The pandas code the agent generated and executed |
| `reasoning_trace` | TEXT | no | Step-by-step reasoning the agent produced before generating code |
| `result_json` | TEXT (JSON) | no | Execution output: `{"columns": [...], "rows": [[...]]}` — top 100 rows max |
| `answer_text` | TEXT | no | Full prose answer (accumulated from streamed tokens) |
| `summary_table_json` | TEXT (JSON) | no | Subset of `result_json` for inline display (top 5–10 rows); null if no table |
| `clarification_question` | TEXT | no | If status = `clarifying`, the question asked back to the user |
| `prompt_tokens` | INTEGER | no | Gemini prompt token count for this query (sum across all nodes) |
| `completion_tokens` | INTEGER | no | Gemini completion token count for this query |
| `cost_usd` | REAL | no | Estimated cost in USD based on token counts and model pricing |
| `error_message` | TEXT | no | Error detail if status = `failed` |
| `created_at` | TIMESTAMP WITH TIMEZONE | yes | Question submission time |
| `completed_at` | TIMESTAMP WITH TIMEZONE | no | Time answer was fully streamed |

---

### Entity: `exports`

Represents a downloadable CSV export generated from a query result.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | TEXT (UUID) | yes | Primary key |
| `session_id` | TEXT (UUID FK → sessions.id) | yes | Owning session |
| `query_id` | TEXT (UUID FK → queries.id) | yes | The query whose result was exported |
| `file_path` | TEXT | yes | Absolute path to the generated CSV on local filesystem |
| `filename` | TEXT | yes | Suggested download filename (e.g. `export_{query_id[:8]}.csv`) |
| `row_count` | INTEGER | yes | Number of data rows in the export |
| `created_at` | TIMESTAMP WITH TIMEZONE | yes | Export creation time |

---

## Relationships

```
sessions 1──N datasets
sessions 1──N queries
sessions 1──N exports
queries  1──N exports
```

- One session has many datasets (up to 3 files).
- One session has many queries (the conversation history).
- One query may have zero or one export (a user may export the result of any completed query).
- Exports reference both session and query for independent querying.

---

## Data Lifecycle

| Table | Created | Updated | Deleted |
|-------|---------|---------|---------|
| `sessions` | On first file upload (POST /api/sessions) | On each query or upload | Never (audit) |
| `datasets` | On file upload (POST /api/sessions/{id}/files) | After profiling completes | Never (audit) |
| `queries` | When user submits a question | Progressively during streaming | Never (audit) |
| `exports` | When user requests download | Never | Never (audit) |

Files in `data/uploads/` and `data/exports/` are never deleted automatically (audit requirement). The `exports` CSV files are written to `data/exports/{session_id}/{export_id}.csv`.

---

## Sensitive Data

No PII is explicitly collected. Uploaded files may contain PII (user's responsibility). No fields are encrypted at rest; the tool is a local single-user deployment. `AGENT_GEMINI_API_KEY` is loaded from `.env` and never persisted to the database.
