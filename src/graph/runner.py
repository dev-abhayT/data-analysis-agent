import json
import asyncio
from typing import Callable

import structlog

from graph.agent import analysis_agent
from graph.state import AgentState
from db.session import create_db_session
from db.models import Query, Dataset

log = structlog.get_logger()


async def run_analysis(
    session_id: str,
    query_id: str,
    question: str,
    sse_send: Callable[[str], None],
    dataset_ids: list[str] | None = None,
) -> None:
    """
    Run the LangGraph analysis agent and stream SSE events via sse_send.
    sse_send is called with raw JSON strings (the "data:" value of each SSE event).
    This function blocks until the graph is complete.
    """
    # Load session state from DB
    with create_db_session() as db:
        query_row = db.get(Query, query_id)
        if query_row is None:
            sse_send(json.dumps({"type": "error", "message": "Query not found"}))
            return
        query_row.status = "running"

        # Load datasets for the session (optionally filtered to selected IDs)
        datasets = db.query(Dataset).filter(Dataset.session_id == session_id).all()
        if dataset_ids:
            dataset_paths = {d.id: d.file_path for d in datasets if d.id in dataset_ids}
        else:
            dataset_paths = {d.id: d.file_path for d in datasets}

        # Load conversation history (last 10 completed queries, interleaved)
        from db.models import Query as QueryModel
        from sqlalchemy import select, desc
        history_rows = db.execute(
            select(QueryModel)
            .where(QueryModel.session_id == session_id)
            .where(QueryModel.status == "completed")
            .where(QueryModel.id != query_id)
            .order_by(desc(QueryModel.created_at))
            .limit(10)
        ).scalars().all()

        # Interleave: [user, assistant, user, assistant, ...]
        conversation_history = []
        for r in reversed(list(history_rows)):
            conversation_history.append({"role": "user", "content": r.question})
            conversation_history.append(
                {"role": "assistant", "content": r.answer_text or ""}
            )

    def _sse_callback(data: str) -> None:
        """Called by nodes to send pre-formatted SSE event JSON strings."""
        if data:
            sse_send(data)

    initial: AgentState = {
        "session_id": session_id,
        "query_id": query_id,
        "question": question,
        "dataset_paths": dataset_paths,
        "conversation_history": conversation_history,
        "execution_error": None,
        "code_retry_count": 0,
        "error": None,
        "status": "running",
        "stream_callback": _sse_callback,
    }

    try:
        # Run the graph synchronously in a thread pool to avoid blocking the event loop
        final = await asyncio.to_thread(analysis_agent.invoke, initial)
        log.info("analysis_complete", query_id=query_id, status=final.get("status"))
    except Exception as exc:
        log.error("analysis_error", query_id=query_id, error=str(exc))
        sse_send(json.dumps({"type": "error", "message": str(exc)}))
        with create_db_session() as db:
            q = db.get(Query, query_id)
            if q:
                q.status = "failed"
                q.error_message = str(exc)
