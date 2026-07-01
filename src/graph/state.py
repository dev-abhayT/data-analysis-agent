from typing import TypedDict


class AgentState(TypedDict, total=False):
    # Identity
    run_id: str
    session_id: str
    query_id: str

    # Input
    question: str
    dataset_paths: dict[str, str]        # {dataset_id: file_path}
    dataframe_vars: dict[str, str]       # {var_name: dataset_id} — for executor scope
    conversation_history: list[dict]     # [{role, content}] prior turns

    # Routing
    route_decision: str                  # "clarify" | "execute" | "describe"
    route_reasoning: str
    is_describe_path: bool

    # Clarification
    clarification_question: str

    # Code generation
    generated_code: str
    reasoning_trace: str

    # Execution
    execution_result: dict | None        # {"columns": [...], "rows": [[...]]}
    execution_error: str | None
    code_retry_count: int

    # Answer
    answer_text: str
    summary_table_json: dict | None
    chart_spec: dict | None
    suggested_followups: list[str]
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float

    # Control
    error: str | None
    status: str
    stream_callback: object | None       # Callable[[str], None] — injected by runner
