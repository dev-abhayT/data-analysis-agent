# Agent

## Agent Architecture Pattern

**Chosen:** Graph (LangGraph) — Tool Use + Routing + LLM-Generated Code Execution (patterns #5, #2, #22 from `harness/patterns/agentic-ai.md`).

Rationale: Each query requires dynamic routing (ambiguous question → clarify; clear question → execute), tool invocation (pandas code execution against the user's DataFrames), and LLM-generated code execution (the agent generates arbitrary pandas code the executor runs). A LangGraph StateGraph with conditional edges is the minimal correct architecture — a linear chain cannot handle the clarify branch and the error path.

---

## LLM Provider & Model

| Node | Provider | Model ID | Rationale |
|------|----------|----------|-----------|
| `profile_starter_questions` | Google Gemini | `gemini-2.5-flash` (env: `AGENT_LLM_MODEL`) | Low latency; called once per upload, not per query |
| `route_question` | Google Gemini | `gemini-2.5-flash` | Lightweight classification — ambiguous vs. actionable |
| `generate_code` | Google Gemini | `gemini-2.5-flash` | Code generation; same model keeps context cost low |
| `stream_answer` | Google Gemini | `gemini-2.5-flash` | Streaming prose synthesis; fast flash model suits SSE latency target |

> **Assumed:** All nodes use `gemini-2.5-flash` by default. Model is read from `settings.llm_model`; falls back to `gemini-2.5-flash` when the env var is blank.

**Fallback behaviour:** On Gemini 429 (rate limit) → retry once after 2 s. On 5xx → set `state["error"]` and route to `handle_error`. No silent degradation; error message streamed to client.

**Prompt strategy:** System prompt in `src/prompts/analysis.md` defines the agent's role and output format. Each node constructs a user message from state fields. `route_question` uses JSON-mode output (`{"decision": "clarify"|"execute", "reasoning": "..."}`) to make branching deterministic. `generate_code` uses a structured output format requiring the code block to be fenced with ` ```python ... ``` `. `stream_answer` uses streaming mode (`stream=True`) so tokens arrive incrementally.

---

## Tools

| Tool name | Description | Inputs | Output | Side-effects |
|-----------|-------------|--------|--------|--------------|
| `profile_dataset` | Runs pandas profiling on an uploaded file | `file_path: str` | `ProfileResult` (row_count, column_names, column_types, null_counts, sample_values) | None (read-only) |
| `execute_pandas_code` | Executes LLM-generated pandas code in a subprocess with named DataFrames in scope | `code: str`, `dataframes: dict[str, DataFrame]` | `ExecutionResult` (columns, rows, error) | None (read-only; subprocess is isolated) |

**Tool selection strategy:** Tools are not LLM-selected (tool_use API); they are called imperatively by specific nodes (`profile_dataset` by `profile_data` node; `execute_pandas_code` by `execute_code` node). The LLM never decides which tool to call — the graph topology decides.

**Tool failure handling:**
- `profile_dataset` failure → set `state["error"]`, route to `handle_error`.
- `execute_pandas_code` execution error (Python exception in generated code) → retry once with Gemini re-generating the code with the error message injected; on second failure → set `state["error"]`, route to `handle_error`.

---

## Agent State

```python
class AgentState(TypedDict, total=False):
    # Identity
    run_id: str                         # UUID; set at graph invocation
    session_id: str                     # UUID; maps to sessions table
    query_id: str                       # UUID; maps to queries table

    # Input
    question: str                       # User's plain-English question
    dataset_paths: dict[str, str]       # {dataset_id: file_path} for all session datasets
    conversation_history: list[dict]    # [{role, content}] prior turns in session

    # Intermediate (populated progressively)
    route_decision: str                 # "clarify" | "execute"
    route_reasoning: str                # LLM explanation of routing decision
    clarification_question: str         # Set when route_decision == "clarify"
    generated_code: str                 # pandas code string from generate_code node
    reasoning_trace: str                # Step-by-step reasoning before code generation
    execution_result: dict              # {"columns": [...], "rows": [[...]]}
    execution_error: str | None         # Python exception message if code failed
    code_retry_count: int               # 0 or 1 — tracks one retry on code failure

    # Output
    answer_text: str                    # Full accumulated prose answer
    summary_table_json: dict | None     # Top rows for inline table; None if not applicable
    prompt_tokens: int                  # Total Gemini prompt tokens this query
    completion_tokens: int              # Total Gemini completion tokens this query
    cost_usd: float                     # Estimated cost

    # Control
    error: str | None                   # Fatal error message; set by any node on failure
    status: str                         # "pending"|"running"|"clarifying"|"completed"|"failed"
```

---

## Nodes / Steps

### `profile_data` *(called outside the query graph — invoked directly at upload time)*

**Reads from state:** `dataset_paths` (one path per upload)

**Writes to state:** Not part of the query StateGraph; result written directly to `datasets` table and returned via upload API.

**LLM call:** Yes (one call to generate starter questions after profiling). Prompt: profile stats + column names/types → "Generate 3 concise starter questions a non-technical user would ask about this dataset." JSON array output.

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| Local filesystem | Read uploaded file via pandas | Fatal — 422 to client |
| Google Gemini | Generate starter questions | Fatal — 500 to client; file still saved |

**Behaviour:** Reads the uploaded file with pandas. Computes row count, column names, dtypes, null counts, and up to 5 sample values per column. Calls Gemini once to generate 2–3 tailored starter questions. Persists all data to the `datasets` row.

---

### `route_question`

**Reads from state:** `question`, `conversation_history`, `dataset_paths` (column names extracted)

**Writes to state:** `route_decision`, `route_reasoning`

**LLM call:** Yes. Prompt: question + column names + conversation history → JSON `{"decision": "clarify"|"execute", "reasoning": "..."}`. Uses JSON mode.

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| Google Gemini | Classification call | Fatal — set `error`, route to `handle_error` |

**Behaviour:** Determines whether the question is specific enough to execute (has a clear target column and aggregation intent) or ambiguous (references a concept not present in the data, or is genuinely ambiguous between two interpretations). Writes `route_decision` to steer the conditional edge.

---

### `ask_clarification`

**Reads from state:** `route_reasoning`, `question`

**Writes to state:** `clarification_question`, `status`

**LLM call:** No (constructs the clarification question from `route_reasoning` deterministically).

**External calls:** None.

**Behaviour:** Builds a concise clarification question from the routing reasoning. Sets `status = "clarifying"`. The `finalize` node then persists this and the SSE stream sends a `clarification` event. Graph terminates; the client re-submits with the user's clarification appended to the question.

---

### `generate_code`

**Reads from state:** `question`, `conversation_history`, `dataset_paths`, `execution_error` (on retry)

**Writes to state:** `generated_code`, `reasoning_trace`

**LLM call:** Yes. Prompt: question + column names/types + sample values + (on retry: previous code + error message) → fenced Python/pandas code block. Streaming off (need full code before execution).

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| Google Gemini | Code generation | Fatal — set `error`, route to `handle_error` |

**Behaviour:** Generates valid Python/pandas code that answers the question. DataFrames are available in scope as variables named by dataset filename stem (e.g. `sales_df` for `sales.csv`). Captures the step-by-step reasoning prefix before the code block as `reasoning_trace`. On retry (when `execution_error` is set), prepends the error message to the prompt so Gemini can correct the mistake.

---

### `execute_code`

**Reads from state:** `generated_code`, `dataset_paths`

**Writes to state:** `execution_result`, `execution_error`, `code_retry_count`

**LLM call:** No.

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| `src/tools/executor.py` | Run pandas code in subprocess | On error: set `execution_error`; if `code_retry_count < 1`, route back to `generate_code` for retry |

**Behaviour:** Calls `executor.py` which launches a subprocess with the DataFrames loaded and the generated code injected. The subprocess returns a JSON result `{"columns": [...], "rows": [[...]]}` on success or `{"error": "..."}` on failure. On failure with `code_retry_count == 0`, increments counter and routes back to `generate_code` for one retry. On failure with `code_retry_count == 1`, sets `state["error"]` and routes to `handle_error`.

---

### `stream_answer`

**Reads from state:** `question`, `execution_result`, `reasoning_trace`

**Writes to state:** `answer_text`, `summary_table_json`, `prompt_tokens`, `completion_tokens`, `cost_usd`

**LLM call:** Yes — streaming. Prompt: question + execution result JSON → prose answer. Streaming tokens sent via `stream_callback` injected into state. SSE `table` event emitted if answer references a ranked or aggregated result set.

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| Google Gemini | Streaming prose synthesis | Fatal — set `error`, route to `handle_error` |

**Behaviour:** Calls Gemini with streaming enabled. Each token chunk is passed to `stream_callback(chunk)` (injected by the runner, which forwards it to the SSE `StreamingResponse`). Accumulates `answer_text`. On completion, extracts token usage from response metadata and computes `cost_usd` using known Gemini flash pricing. Determines if the execution result should be shown as an inline table (yes, if `len(rows) <= 20` and the question asked for a ranking or comparison).

---

### `handle_error`

**Reads from state:** `error`, `query_id`

**Writes to state:** `status`

**LLM call:** No.

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | Update `queries` row status → "failed", `error_message` | Log and continue |

**Behaviour:** Persists the error. Sets `status = "failed"`. Emits SSE `error` event with the error message. Logs the error with structlog including `query_id` and `session_id`.

---

### `finalize`

**Reads from state:** `query_id`, `answer_text`, `summary_table_json`, `generated_code`, `reasoning_trace`, `prompt_tokens`, `completion_tokens`, `cost_usd`, `clarification_question`, `status`

**Writes to state:** `status` → "completed" (or "clarifying")

**LLM call:** No.

**External calls:**

| System | Operation | On Failure |
|--------|-----------|------------|
| SQLite | Update `queries` row with all output fields | Log and continue |

**Behaviour:** Persists all query artefacts to the `queries` table. Emits SSE `code` event (generated_code + reasoning_trace), `usage` event (tokens + cost), then `done` event. Marks the query row `completed_at`.

---

## Graph / Flow Topology

```
START
  │
  ▼
route_question
  │
  ├─(clarify)──► ask_clarification ──► finalize ──► END
  │
  └─(execute)──► generate_code
                      │
                      ▼
                 execute_code
                      │
                      ├─(retry: execution_error, retry_count < 1)──► generate_code
                      │
                      ├─(error: execution_error, retry_count == 1)──► handle_error ──► END
                      │
                      └─(success)──► stream_answer
                                          │
                                          ├─(error)──► handle_error ──► END
                                          │
                                          └─(success)──► finalize ──► END

Any node that sets state["error"] ──► handle_error ──► END
```

**Conditional edges:**

| Source node | Condition | Target |
|-------------|-----------|--------|
| `route_question` | `state["route_decision"] == "clarify"` | `ask_clarification` |
| `route_question` | `state["route_decision"] == "execute"` | `generate_code` |
| `route_question` | `state.get("error")` | `handle_error` |
| `execute_code` | `state.get("execution_error") and state.get("code_retry_count", 0) < 1` | `generate_code` |
| `execute_code` | `state.get("execution_error") and state.get("code_retry_count", 0) >= 1` | `handle_error` |
| `execute_code` | not `state.get("execution_error")` | `stream_answer` |
| `stream_answer` | `state.get("error")` | `handle_error` |
| `stream_answer` | not `state.get("error")` | `finalize` |

---

## Memory & Context

| Scope | Mechanism | What is stored |
|-------|-----------|----------------|
| **Within a run** | LangGraph `AgentState` TypedDict | All in-progress fields (question, code, result, answer) |
| **Across turns (session)** | SQLite `queries` table | All completed query artefacts; loaded by runner and injected as `conversation_history` |
| **Conversation history** | Last 10 Q&A pairs from `queries` table injected into `route_question` and `generate_code` prompts | Question + answer_text pairs for context |

**Context window management:** `conversation_history` is capped at the last 10 turns (most recent Q&A pairs). The full execution result (`result_json`) is never included in subsequent prompts — only the `answer_text` is. Profile stats (column names/types) are included in every node prompt from `state["dataset_paths"]` metadata (not full data rows).

---

## Human-in-the-Loop Checkpoints

| Checkpoint | What is shown to the user | Expected user action | Timeout / default |
|------------|--------------------------|----------------------|-------------------|
| `ask_clarification` | The agent's clarifying question in an amber-styled bubble | User types an amended question with the clarification and resubmits | No timeout — user submits when ready |

---

## Error Handling & Recovery

**Node-level:** Every node wraps its logic in `try/except`. Fatal exceptions set `state["error"] = str(exc)` and return the mutated state; the graph edge then routes to `handle_error`.

**Graph-level (`handle_error` node):**
- Reads: `state["error"]`, `state["query_id"]`
- Updates DB: `queries.status` → "failed", `queries.error_message`
- Emits SSE `error` event
- Logs with structlog including `run_id`, `session_id`, `query_id`
- Terminates graph

**Resume / retry strategy:** Failed queries are not resumable — the client resubmits the question. The one built-in retry is within the `execute_code` → `generate_code` loop (max 1 retry on code execution failure).

**Partial failure:** The clarification path (`ask_clarification`) is a graceful partial response — the agent surfaces a question rather than failing. All other failures are fatal and terminate the graph via `handle_error`.

---

## Observability

| Signal | What | Where |
|--------|------|-------|
| **LangSmith trace** | One trace per query, one span per node | LangSmith (when `LANGCHAIN_API_KEY` set); silently skipped when absent |
| **LLM calls** | Prompt tokens, completion tokens, latency, model | LangSmith + `queries` table |
| **Tool calls** | `execute_pandas_code` input code, output rows, success/error, latency | structlog JSON to stdout |
| **SSE events** | Each event type emitted, latency from query submission to first token | structlog JSON to stdout |
| **Run outcome** | Query status, total duration, error if any | SQLite `queries` table + structlog |

---

## Concurrency Model

- **Run isolation:** Each query creates a scoped `query_id` and the SSE stream is keyed to it. Multiple concurrent browser queries are supported — each runs its own LangGraph invocation independently.
- **Parallel nodes within a run:** None — the graph is sequential.
- **Checkpointing:** None (LangGraph default `MemorySaver` not used). Failed runs are not resumable; client resubmits.

---

## Graph Assembly (`src/graph/agent.py`)

```python
from langgraph.graph import StateGraph, END
from graph.state import AgentState
from graph.nodes import (
    route_question,
    ask_clarification,
    generate_code,
    execute_code,
    stream_answer,
    handle_error,
    finalize,
)
from graph.edges import (
    after_route,
    after_execute,
    after_stream,
)

def _build_graph() -> StateGraph:
    g = StateGraph(AgentState)

    g.add_node("route_question", route_question)
    g.add_node("ask_clarification", ask_clarification)
    g.add_node("generate_code", generate_code)
    g.add_node("execute_code", execute_code)
    g.add_node("stream_answer", stream_answer)
    g.add_node("handle_error", handle_error)
    g.add_node("finalize", finalize)

    g.set_entry_point("route_question")

    g.add_conditional_edges(
        "route_question",
        after_route,
        {
            "ask_clarification": "ask_clarification",
            "generate_code": "generate_code",
            "handle_error": "handle_error",
        },
    )

    g.add_edge("ask_clarification", "finalize")

    g.add_conditional_edges(
        "execute_code",
        after_execute,
        {
            "generate_code": "generate_code",   # retry path
            "stream_answer": "stream_answer",
            "handle_error": "handle_error",
        },
    )

    g.add_conditional_edges(
        "stream_answer",
        after_stream,
        {
            "finalize": "finalize",
            "handle_error": "handle_error",
        },
    )

    g.add_edge("generate_code", "execute_code")
    g.add_edge("finalize", END)
    g.add_edge("handle_error", END)

    return g.compile()


analysis_agent = _build_graph()
```

**Phase 1 node status:**
- `route_question` — REAL (Gemini call, JSON mode)
- `ask_clarification` — REAL
- `generate_code` — REAL (Gemini call, code generation)
- `execute_code` — REAL (subprocess executor)
- `stream_answer` — REAL (Gemini streaming)
- `handle_error` — REAL
- `finalize` — REAL (persists to DB, emits SSE done/code/usage events)

All nodes are real in Phase 1. Phase 2 adds token/cost capture refinements to `stream_answer` and multi-file join context to `generate_code`.
