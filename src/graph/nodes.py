import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import structlog

from graph.state import AgentState
from llm.client import LLMClient
from tools.executor import execute_pandas_code
from tools.profiler import _read_csv_robust

log = structlog.get_logger()

_ANALYSIS_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "analysis.md"

# ---------------------------------------------------------------------------
# Meta-question detection (describe path)
# ---------------------------------------------------------------------------

_META_PATTERNS = [
    r"what (is|'s|was) (this|the|a) (data|dataset|file|csv)",
    r"(data|dataset|file|csv).{0,40}about",
    r"about.{0,40}(data|dataset|file|csv)",
    r"what are (some |the )?(interesting |key |main )?(insights|observations|patterns|trends)",
    r"\bdescribe\b",
    r"\bsummarize\b",
    r"\bsummary\b",
    r"tell me about",
    r"\boverview\b",
    r"what does (this|the) (data|dataset|file|csv)",
    r"what('s| is) in (this|the) (data|dataset|file|csv)",
    r"give me (a )?(summary|overview|description)",
    r"explain (this|the) (data|dataset|file|csv)",
    r"(data|dataset).{0,20}contain",
    r"(data|dataset).{0,20}represent",
    r"(what|which|list|show).{0,30}columns",
    r"columns.{0,30}(data|dataset|file|available|there|exist)",
    r"what (fields|features|variables|attributes)",
]


def _is_meta_question(question: str) -> bool:
    q = question.lower().strip()
    return any(re.search(p, q) for p in _META_PATTERNS)

_TABLE_KEYWORDS = {
    "top", "most", "least", "rank", "ranking", "compare", "comparison",
    "highest", "lowest", "best", "worst", "largest", "smallest",
    "biggest", "sort", "sorted", "order", "ordered",
}

_DATE_PATTERN = re.compile(
    r"\d{4}[-/]\d{1,2}|\d{1,2}[-/]\d{4}|Q[1-4]\s*\d{4}|"
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b",
    re.IGNORECASE,
)


def _detect_chart(table: dict) -> dict | None:
    """Return a chart spec dict if the table is suitable for charting, else None.

    Accepts string OR integer year-like (1800-2100) columns as the x-axis so
    that queries like "movies per year" produce a line chart. Auto-slices to a
    per-type row limit so large results still produce a readable chart.
    """
    columns = table.get("columns", [])
    rows = table.get("rows", [])
    if len(columns) < 2 or len(rows) < 2:
        return None

    # Categorise every column
    str_col_idx: int | None = None   # first non-numeric column → preferred x-axis
    year_col_idx: int | None = None  # first int col where all values look like years
    num_col_idx: int | None = None   # first purely numeric col (y-axis candidate)

    for i in range(len(columns)):
        vals = [r[i] for r in rows if i < len(r) and r[i] is not None]
        if not vals:
            continue
        if all(isinstance(v, (int, float)) for v in vals):
            # Year-like: all integers in 1800-2100 range
            if (year_col_idx is None
                    and all(isinstance(v, int) and 1800 <= v <= 2100 for v in vals)):
                year_col_idx = i
            if num_col_idx is None:
                num_col_idx = i
        else:
            if str_col_idx is None:
                str_col_idx = i

    # Decide x (label/time) and y (metric) columns
    if str_col_idx is not None:
        x_col = str_col_idx
        # y = first numeric col that is not x
        y_col = num_col_idx if num_col_idx != x_col else (
            next((j for j in range(len(columns)) if j != x_col
                  and all(isinstance(r[j], (int, float))
                          for r in rows if j < len(r) and r[j] is not None)),
                 None)
        )
    elif year_col_idx is not None:
        x_col = year_col_idx
        # y = first numeric col that is not the year col
        y_col = next(
            (j for j in range(len(columns))
             if j != year_col_idx
             and all(isinstance(r[j], (int, float))
                     for r in rows if j < len(r) and r[j] is not None)),
            None,
        )
    else:
        return None

    if y_col is None:
        return None

    x_key = columns[x_col]
    y_key = columns[y_col]

    # Choose chart type and per-type row limit
    first_x = rows[0][x_col] if rows[0][x_col] is not None else ""
    first_x_str = str(first_x)

    if x_col == year_col_idx:
        chart_type = "line"
        limit = 50
    elif _DATE_PATTERN.search(first_x_str):
        chart_type = "line"
        limit = 50
    elif len(rows) <= 6:
        chart_type = "pie"
        limit = 6
    else:
        chart_type = "bar"
        limit = 20

    chart_rows = rows[:limit]
    data = [
        {x_key: r[x_col], y_key: r[y_col]}
        for r in chart_rows
        if len(r) > max(x_col, y_col)
    ]

    return {"chart_type": chart_type, "x_key": x_key, "y_key": y_key, "data": data}


def _generate_suggestions(question: str, answer_text: str) -> list[str]:
    """Ask the LLM for 3 short follow-up questions based on the current Q&A."""
    prompt = (
        f"A user asked this data question and received the answer below.\n"
        f"Question: {question}\n"
        f"Answer: {answer_text[:600]}\n\n"
        f"Suggest exactly 3 concise follow-up data analysis questions (under 12 words each) "
        f"that would give additional useful insight.\n"
        f'Return ONLY valid JSON: {{"suggestions": ["...", "...", "..."]}}'
    )
    try:
        result = LLMClient().call_json(prompt)
        suggestions = result.get("suggestions", [])
        if isinstance(suggestions, list):
            return [str(s).strip() for s in suggestions[:3] if s]
    except Exception:
        pass
    return []


def _load_system_prompt() -> str:
    return _ANALYSIS_PROMPT_PATH.read_text(encoding="utf-8").strip()


def _var_name_for_file(file_path: str) -> str:
    """Return a pandas variable name for a file path, e.g. sales_df for sales.csv."""
    stem = Path(file_path).stem
    # Sanitize: replace non-alphanumeric with underscore, lowercase
    safe = re.sub(r"[^a-zA-Z0-9]", "_", stem).lower().strip("_")
    if not safe:
        safe = "df"
    return f"{safe}_df"


def _load_dataframes(dataset_paths: dict[str, str]) -> dict[str, pd.DataFrame]:
    """Load all dataset files into DataFrames keyed by variable name."""
    dfs: dict[str, pd.DataFrame] = {}
    for _ds_id, file_path in dataset_paths.items():
        suffix = Path(file_path).suffix.lower()
        if suffix == ".csv":
            df = _read_csv_robust(file_path)
        elif suffix in (".xlsx", ".xls"):
            df = pd.read_excel(file_path)
        else:
            raise ValueError(f"Unsupported file type: {suffix}")
        var = _var_name_for_file(file_path)
        dfs[var] = df
    return dfs


def _dataset_summary(dataset_paths: dict[str, str]) -> str:
    """Return a brief textual summary of column names for each dataset."""
    lines = []
    for _ds_id, file_path in dataset_paths.items():
        var = _var_name_for_file(file_path)
        try:
            suffix = Path(file_path).suffix.lower()
            if suffix == ".csv":
                df = _read_csv_robust(file_path).iloc[:0]
            elif suffix in (".xlsx", ".xls"):
                df = pd.read_excel(file_path, nrows=0)
            else:
                df = pd.DataFrame()
            cols = list(df.columns)
        except Exception:
            cols = []
        lines.append(f"Dataset variable: {var}\nColumns: {cols}")
    return "\n\n".join(lines)


def _dataset_detail(dataset_paths: dict[str, str]) -> str:
    """Return detailed column info (names, dtypes, sample values) for all datasets."""
    lines = []
    for _ds_id, file_path in dataset_paths.items():
        var = _var_name_for_file(file_path)
        try:
            suffix = Path(file_path).suffix.lower()
            if suffix == ".csv":
                df = _read_csv_robust(file_path).head(20)
            elif suffix in (".xlsx", ".xls"):
                df = pd.read_excel(file_path, nrows=20)
            else:
                df = pd.DataFrame()
            col_lines = []
            for col in df.columns:
                samples = df[col].dropna().head(3).tolist()
                samples = [s.item() if hasattr(s, "item") else s for s in samples]
                samples_str = str([str(s) for s in samples])
                col_lines.append(f"  - {col} ({df[col].dtype}): samples {samples_str}")
            lines.append(
                f"Dataset variable: {var} (file: {Path(file_path).name})\n"
                + "\n".join(col_lines)
            )
        except Exception as exc:
            lines.append(f"Dataset variable: {var} — could not read: {exc}")
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


def route_question(state: AgentState) -> AgentState:
    question = state.get("question", "")
    if _is_meta_question(question):
        log.info("route_question", decision="describe")
        return {**state, "route_decision": "describe"}
    log.info("route_question", decision="execute")
    return {**state, "route_decision": "execute"}


def describe_dataset(state: AgentState) -> AgentState:
    """Describe the dataset using its profiling data stored in the DB."""
    try:
        session_id = state.get("session_id", "")

        # Read profile from DB
        from db.session import create_db_session
        from db.models import Dataset as DatasetModel

        profile_lines: list[str] = []
        with create_db_session() as db:
            datasets = (
                db.query(DatasetModel)
                .filter(DatasetModel.session_id == session_id)
                .all()
            )
            for ds in datasets:
                profile_lines.append(f"File: {ds.filename}")
                profile_lines.append(f"  Rows: {ds.row_count}")

                if ds.column_names_json:
                    col_names = json.loads(ds.column_names_json)
                else:
                    col_names = []
                profile_lines.append(f"  Columns: {col_names}")

                if ds.column_types_json:
                    col_types = json.loads(ds.column_types_json)
                    for col, dtype in col_types.items():
                        profile_lines.append(f"    - {col}: type={dtype}")

                if ds.null_counts_json:
                    null_counts = json.loads(ds.null_counts_json)
                    non_zero_nulls = {k: v for k, v in null_counts.items() if v > 0}
                    if non_zero_nulls:
                        profile_lines.append(f"  Columns with nulls: {non_zero_nulls}")

                if ds.sample_values_json:
                    sample_values = json.loads(ds.sample_values_json)
                    profile_lines.append("  Sample values per column:")
                    for col, samples in sample_values.items():
                        profile_lines.append(f"    - {col}: {samples}")

        profile_text = "\n".join(profile_lines) if profile_lines else "No profile data available."

        prompt = (
            f"You are a data analyst. Based on the following dataset profile, write a clear "
            f"2-3 paragraph description of what this dataset contains and what it can be used for. "
            f"Then provide 3-5 bullet points highlighting the most interesting observations or patterns "
            f"you notice.\n\n"
            f"Dataset profile:\n{profile_text}\n\n"
            f"Format your response as:\n"
            f"[2-3 paragraph description]\n\n"
            f"**Interesting observations:**\n"
            f"• [observation 1]\n"
            f"• [observation 2]\n"
            f"• [observation 3]\n"
            f"(up to 5 bullets)"
        )

        answer_text = LLMClient().call_model(prompt)

        log.info("describe_dataset", session_id=session_id, answer_length=len(answer_text))
        return {
            **state,
            "answer_text": answer_text,
            "generated_code": "",
            "reasoning_trace": "",
            "is_describe_path": True,
        }
    except Exception as exc:
        log.error("describe_dataset_error", error=str(exc))
        return {**state, "error": str(exc)}


def ask_clarification(state: AgentState) -> AgentState:
    try:
        reasoning = state.get("route_reasoning", "")
        question = state.get("question", "")

        # Build a concise clarifying question from the routing reasoning
        clarification = (
            f"I need a bit more information to answer your question about '{question}'. "
            f"{reasoning} Could you please clarify?"
        )

        log.info("ask_clarification", clarification=clarification)
        return {**state, "clarification_question": clarification, "status": "clarifying"}
    except Exception as exc:
        log.error("ask_clarification_error", error=str(exc))
        return {**state, "error": str(exc)}


def generate_code(state: AgentState) -> AgentState:
    try:
        question = state.get("question", "")
        dataset_paths = state.get("dataset_paths", {})
        execution_error = state.get("execution_error")
        conversation_history = state.get("conversation_history", [])

        dataset_detail = _dataset_detail(dataset_paths)

        # Build variable name mapping for the prompt
        var_mapping_lines = []
        for _ds_id, file_path in dataset_paths.items():
            var = _var_name_for_file(file_path)
            var_mapping_lines.append(f"  - {var} = pd.read_csv/read_excel('{Path(file_path).name}')")
        var_mapping = "\n".join(var_mapping_lines)

        history_text = ""
        if conversation_history:
            pairs = [
                f"{m['role'].capitalize()}: {m['content']}"
                for m in conversation_history
            ]
            history_text = "Conversation so far:\n" + "\n".join(pairs) + "\n\n"

        retry_prefix = ""
        if execution_error:
            retry_prefix = (
                f"IMPORTANT: Your previous code failed with this error:\n"
                f"{execution_error}\n\nPlease fix the error and try again.\n\n"
            )

        prompt = (
            f"{retry_prefix}"
            f"{history_text}"
            f"Current question: {question}\n\n"
            f"Available DataFrames (already loaded, do NOT re-read files):\n"
            f"{var_mapping}\n\n"
            f"Dataset details:\n{dataset_detail}\n\n"
            f"Rules:\n"
            f"1. Assign your final result to a variable named `result`.\n"
            f"2. Never import subprocess, os, sys. Never use open(), eval(), exec().\n"
            f"3. Do not print() — assign to result instead.\n"
            f"4. Keep code concise.\n"
            f"5. CRITICAL — for comparisons, rankings, popularity, distributions, counts, "
            f"top-N, or trends: return a DataFrame with the aggregated/sorted data. "
            f"NEVER return a string like 'Most popular: X'. Return the full DataFrame.\n"
            f"   Example: result = df.groupby('genre').size().reset_index(name='count').sort_values('count', ascending=False)\n"
            f"6. If the user asks for a PIE chart, limit to the top 6 categories (.head(6)).\n"
            f"   If the user asks for a BAR chart, limit to the top 15 (.head(15)).\n"
            f"7. For a single numeric answer (average, total, count) a scalar is fine.\n\n"
            f"First, briefly explain your approach and any assumption you're making if the question "
            f"is ambiguous (1-2 sentences). Then write the pandas code in a ```python code block."
        )

        system = _load_system_prompt()
        response = LLMClient().call_model(prompt, system=system)

        # Extract reasoning trace (text before the code block)
        code_match = re.search(r"```python\s*(.*?)```", response, re.DOTALL)
        if code_match:
            generated_code = code_match.group(1).strip()
            reasoning_trace = response[: code_match.start()].strip()
        else:
            # Fallback: treat entire response as code if no fences found
            generated_code = response.strip()
            reasoning_trace = ""

        log.info(
            "generate_code",
            code_length=len(generated_code),
            retry=bool(execution_error),
        )
        return {
            **state,
            "generated_code": generated_code,
            "reasoning_trace": reasoning_trace,
            # Clear previous execution error for retry tracking
            "execution_error": None,
        }
    except Exception as exc:
        log.error("generate_code_error", error=str(exc))
        return {**state, "error": str(exc)}


def execute_code(state: AgentState) -> AgentState:
    try:
        code = state.get("generated_code", "")
        dataset_paths = state.get("dataset_paths", {})

        # Load all DataFrames
        dfs = _load_dataframes(dataset_paths)

        result = execute_pandas_code(code, dfs)

        if "error" in result:
            retry_count = (state.get("code_retry_count") or 0) + 1
            log.warning(
                "execute_code_error",
                error=result["error"],
                retry_count=retry_count,
            )
            return {
                **state,
                "execution_error": result["error"],
                "code_retry_count": retry_count,
            }

        log.info(
            "execute_code_success",
            row_count=len(result.get("rows", [])),
        )
        return {
            **state,
            "execution_result": result,
            "execution_error": None,
        }
    except Exception as exc:
        log.error("execute_code_fatal", error=str(exc))
        return {**state, "error": str(exc)}


def stream_answer(state: AgentState) -> AgentState:
    try:
        is_describe = state.get("is_describe_path", False)
        stream_callback = state.get("stream_callback")

        if is_describe:
            # The answer text was already generated by describe_dataset; stream it word-by-word
            answer_text = state.get("answer_text", "")
            if stream_callback and answer_text:
                words = answer_text.split(" ")
                for i, word in enumerate(words):
                    chunk = word if i == len(words) - 1 else word + " "
                    try:
                        stream_callback(json.dumps({"type": "token", "content": chunk}))
                    except Exception:
                        pass
            log.info("stream_answer_done", path="describe", answer_length=len(answer_text))
            return {
                **state,
                "answer_text": answer_text,
                "summary_table_json": None,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "cost_usd": 0.0,
            }

        question = state.get("question", "")
        execution_result = state.get("execution_result") or {}
        reasoning_trace = state.get("reasoning_trace", "")
        conversation_history = state.get("conversation_history", [])

        result_json = json.dumps(execution_result)

        history_context = ""
        if conversation_history:
            recent = conversation_history[-6:]  # last 3 turns
            pairs = [f"{m['role'].capitalize()}: {m['content']}" for m in recent]
            history_context = "Recent conversation:\n" + "\n".join(pairs) + "\n\n"

        prompt = (
            f"{history_context}"
            f"The user asked: {question}\n\n"
            f"The pandas code produced this result:\n{result_json}\n\n"
            f"Write a concise 2-4 sentence prose answer. "
            f"If you made an assumption to interpret this question, state it in one sentence at the start. "
            f"Reference actual values from the result. "
            f"If the result has multiple rows, say 'A chart is shown below with the full breakdown.' "
            f"Do not include code. Do not repeat the question."
        )

        system = _load_system_prompt()
        chunks = LLMClient().stream_model(prompt, system=system)

        accumulated = []
        usage_data: dict | None = None

        for chunk_text, usage in chunks:
            if chunk_text:
                accumulated.append(chunk_text)
                if stream_callback is not None:
                    try:
                        stream_callback(json.dumps({"type": "token", "content": chunk_text}))
                    except Exception:
                        pass
            if usage is not None:
                usage_data = usage

        answer_text = "".join(accumulated)

        # Token accounting
        prompt_tokens = 0
        completion_tokens = 0
        if usage_data:
            prompt_tokens = usage_data.get("prompt_tokens", 0)
            completion_tokens = usage_data.get("completion_tokens", 0)

        # Gemini 2.5 Flash pricing (per million tokens)
        cost_usd = (prompt_tokens * 0.075 + completion_tokens * 0.3) / 1_000_000

        # Show table (and chart) for any result with ≤ 25 rows — no keyword gate
        summary_table_json = None
        rows = execution_result.get("rows", [])
        if rows and len(rows) <= 25:
            summary_table_json = execution_result

        log.info(
            "stream_answer_done",
            answer_length=len(answer_text),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
        )
        return {
            **state,
            "answer_text": answer_text,
            "summary_table_json": summary_table_json,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_usd": cost_usd,
        }
    except Exception as exc:
        log.error("stream_answer_error", error=str(exc))
        return {**state, "error": str(exc)}


def handle_error(state: AgentState) -> AgentState:
    error_msg = state.get("error", "Unknown error")
    query_id = state.get("query_id")

    log.error(
        "handle_error",
        error=error_msg,
        query_id=query_id,
        session_id=state.get("session_id"),
    )

    # Persist to DB
    if query_id:
        try:
            from db.session import create_db_session
            from db.models import Query
            with create_db_session() as db:
                q = db.get(Query, query_id)
                if q:
                    q.status = "failed"
                    q.error_message = error_msg
        except Exception as db_exc:
            log.error("handle_error_db_write_failed", error=str(db_exc))

    # Emit SSE error event if callback available
    stream_callback = state.get("stream_callback")
    if stream_callback is not None:
        try:
            stream_callback(json.dumps({"type": "error", "message": error_msg}))
        except Exception:
            pass

    return {**state, "status": "failed"}


def finalize(state: AgentState) -> AgentState:
    query_id = state.get("query_id")
    clarification_question = state.get("clarification_question")
    stream_callback = state.get("stream_callback")

    final_status = "clarifying" if clarification_question else "completed"

    # Compute derived artefacts BEFORE the DB write so everything is persisted together
    summary = state.get("summary_table_json")
    chart_spec: dict | None = None
    suggestions: list[str] = []
    if not clarification_question:
        chart_source = summary or state.get("execution_result") or {}
        chart_spec = _detect_chart(chart_source)
        answer_text = state.get("answer_text") or ""
        question = state.get("question") or ""
        if answer_text and question:
            suggestions = _generate_suggestions(question, answer_text)

    # Persist all artefacts to DB
    if query_id:
        try:
            from db.session import create_db_session
            from db.models import Query
            with create_db_session() as db:
                q = db.get(Query, query_id)
                if q:
                    q.status = final_status
                    q.answer_text = state.get("answer_text")
                    q.generated_code = state.get("generated_code")
                    q.reasoning_trace = state.get("reasoning_trace")
                    q.clarification_question = clarification_question
                    q.prompt_tokens = state.get("prompt_tokens") or 0
                    q.completion_tokens = state.get("completion_tokens") or 0
                    q.cost_usd = state.get("cost_usd") or 0.0
                    q.error_message = state.get("error")

                    q.summary_table_json = (
                        json.dumps(summary) if summary is not None else None
                    )
                    q.chart_json = (
                        json.dumps(chart_spec) if chart_spec is not None else None
                    )
                    q.suggestions_json = (
                        json.dumps(suggestions) if suggestions else None
                    )

                    if final_status == "completed":
                        q.completed_at = datetime.now(timezone.utc)
        except Exception as db_exc:
            log.error("finalize_db_write_failed", error=str(db_exc))

    # Emit SSE events via stream_callback
    if stream_callback is not None:
        try:
            if clarification_question:
                stream_callback(
                    json.dumps({"type": "clarification", "question": clarification_question})
                )
            else:
                if summary:
                    stream_callback(json.dumps({"type": "table", **summary}))
                if chart_spec:
                    stream_callback(json.dumps({"type": "chart", **chart_spec}))
                if suggestions:
                    stream_callback(json.dumps({"type": "suggestions", "questions": suggestions}))

                # Code event — emit even if generated_code is empty string (describe path)
                generated_code = state.get("generated_code")
                if generated_code is not None:
                    stream_callback(
                        json.dumps({
                            "type": "code",
                            "generated_code": generated_code,
                            "reasoning_trace": state.get("reasoning_trace") or "",
                        })
                    )

                # Usage event
                prompt_tokens = state.get("prompt_tokens") or 0
                completion_tokens = state.get("completion_tokens") or 0
                cost_usd = state.get("cost_usd") or 0.0
                stream_callback(
                    json.dumps({
                        "type": "usage",
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "cost_usd": cost_usd,
                    })
                )

            # Always emit done
            stream_callback(json.dumps({"type": "done"}))
        except Exception as cb_exc:
            log.error("finalize_callback_failed", error=str(cb_exc))

    log.info("finalize", status=final_status, query_id=query_id)
    return {**state, "status": final_status}
