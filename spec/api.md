# API

## API Style

REST (JSON) + Server-Sent Events (SSE) for streaming query answers. All endpoints are prefixed `/api/` to distinguish them from the static frontend served at `/app/`. No authentication — open shared access.

---

## Endpoints

### `GET /health`

**Purpose:** Liveness check — confirms the server is running and the DB is reachable.

**Request:** none

**Response:**
```json
{ "status": "ok" }
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 503 | DB unreachable |

---

### `POST /api/sessions`

**Purpose:** Create a new analysis session. Returns the session ID the client uses for all subsequent calls.

**Request:** none (empty body)

**Response:**
```json
{
  "data": {
    "session_id": "uuid",
    "created_at": "2026-06-29T10:00:00Z"
  }
}
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 500 | DB write failure |

---

### `GET /api/sessions/{session_id}`

**Purpose:** Restore session state — returns all datasets (profiles + starter questions) and all completed queries (for conversation history rebuild on page reload).

**Response:**
```json
{
  "data": {
    "session_id": "uuid",
    "created_at": "2026-06-29T10:00:00Z",
    "datasets": [
      {
        "dataset_id": "uuid",
        "filename": "sales.csv",
        "row_count": 1500,
        "column_names": ["date", "revenue", "region"],
        "column_types": {"date": "object", "revenue": "float64", "region": "object"},
        "null_counts": {"date": 0, "revenue": 3, "region": 0},
        "sample_values": {"date": ["2024-01-01", "2024-01-02"], "revenue": [1200.5, 980.0], "region": ["North", "South"]},
        "starter_questions": [
          "What is the total revenue by region?",
          "Which month had the highest sales?",
          "Are there any missing revenue values and which rows are they?"
        ]
      }
    ],
    "queries": [
      {
        "query_id": "uuid",
        "question": "What is the total revenue by region?",
        "status": "completed",
        "answer_text": "The North region generated the most revenue...",
        "summary_table_json": {"columns": ["region", "revenue"], "rows": [["North", 50000]]},
        "generated_code": "df.groupby('region')['revenue'].sum()",
        "reasoning_trace": "The user wants to aggregate revenue by region...",
        "prompt_tokens": 320,
        "completion_tokens": 180,
        "cost_usd": 0.00012,
        "created_at": "2026-06-29T10:05:00Z"
      }
    ]
  }
}
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 404 | Session not found |

---

### `POST /api/sessions/{session_id}/files`

**Purpose:** Upload one CSV or Excel file into the session. Saves file to local filesystem, runs pandas profiling, calls Gemini to generate starter questions, persists dataset record.

**Request:** `multipart/form-data`
- `file`: binary file (CSV or `.xlsx`/`.xls`)

**Constraints:**
- Max file size: 100 MB (enforced with `Content-Length` check before reading)
- Accepted MIME types: `text/csv`, `application/vnd.ms-excel`, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- Max 3 files per session

**Response:**
```json
{
  "data": {
    "dataset_id": "uuid",
    "filename": "sales.csv",
    "row_count": 1500,
    "column_names": ["date", "revenue", "region"],
    "column_types": {"date": "object", "revenue": "float64", "region": "object"},
    "null_counts": {"date": 0, "revenue": 3, "region": 0},
    "sample_values": {"date": ["2024-01-01", "2024-01-02"], "revenue": [1200.5, 980.0], "region": ["North", "South"]},
    "starter_questions": [
      "What is the total revenue by region?",
      "Which month had the highest sales?",
      "Are there any missing revenue values and which rows are they?"
    ]
  }
}
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | File too large (>100 MB) |
| 400 | Unsupported file type |
| 400 | Session already has 3 files |
| 404 | Session not found |
| 422 | File is empty or unparseable by pandas |
| 500 | Filesystem write failure or Gemini API error |

---

### `POST /api/sessions/{session_id}/query`

**Purpose:** Submit a plain-English question. Returns a `query_id` immediately; the client then opens the SSE stream for this query.

**Request:**
```json
{
  "question": "What is the total revenue by region?"
}
```

**Response:**
```json
{
  "data": {
    "query_id": "uuid",
    "status": "pending"
  }
}
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 400 | Question is blank |
| 404 | Session not found |
| 422 | No datasets uploaded in this session |

---

### `GET /api/sessions/{session_id}/queries/{query_id}/stream`

**Purpose:** SSE stream for a query's answer. The client subscribes after receiving the `query_id` from `POST /query`. The server runs the LangGraph agent and sends events as they arrive. On reconnect (if the query is already completed), re-streams the buffered `answer_text` from the DB.

**Response:** `Content-Type: text/event-stream`

SSE event types:

```
data: {"type": "token", "content": "The North region"}

data: {"type": "table", "columns": ["region", "revenue"], "rows": [["North", 50000], ["South", 32000]]}

data: {"type": "clarification", "question": "Do you want revenue by calendar month or fiscal quarter?"}

data: {"type": "code", "generated_code": "df.groupby('region')['revenue'].sum()", "reasoning_trace": "Step 1: ..."}

data: {"type": "usage", "prompt_tokens": 320, "completion_tokens": 180, "cost_usd": 0.00012}

data: {"type": "done"}

data: {"type": "error", "message": "Gemini API returned 429. Please retry in 10 seconds."}
```

Event ordering: `token` events interleaved throughout → `table` event (optional, near end) → `code` event → `usage` event → `done` or `error`.

**Error cases:**
| Status | Condition |
|--------|-----------|
| 404 | Query ID not found |
| 404 | Session not found |

---

### `POST /api/sessions/{session_id}/queries/{query_id}/export`

**Purpose:** Generate a downloadable CSV from the query's `result_json`. Creates an `exports` row and writes the file to `data/exports/{session_id}/{export_id}.csv`.

**Request:** none (empty body)

**Response:**
```json
{
  "data": {
    "export_id": "uuid",
    "filename": "export_a1b2c3d4.csv",
    "row_count": 5
  }
}
```

**Error cases:**
| Status | Condition |
|--------|-----------|
| 404 | Query not found or no result to export |
| 422 | Query status is not `completed` |
| 500 | Filesystem write failure |

---

### `GET /api/exports/{export_id}/download`

**Purpose:** Stream the generated CSV file as a file download.

**Response:** `Content-Type: text/csv; charset=utf-8` with `Content-Disposition: attachment; filename="{filename}"`. Body is the raw CSV content.

**Error cases:**
| Status | Condition |
|--------|-----------|
| 404 | Export record not found |
| 404 | CSV file missing from filesystem |

---

## Response Envelope

All JSON responses use a consistent envelope:

```json
{ "data": { ... } }
```

Errors use:
```json
{ "detail": { "code": "NOT_FOUND", "message": "Session abc not found" } }
```

This matches the existing `ok()` / `api_error()` helpers in `src/api/_common.py`.

## Authentication

None. Open shared access — no API keys, tokens, or session cookies required.
