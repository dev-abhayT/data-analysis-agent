import json
import asyncio

import structlog
from fastapi import APIRouter, Depends, Query as QueryParam
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as DBSession
from pydantic import BaseModel

from api._common import ok, api_error
from db.session import get_session, create_db_session
from db.models import Session as SessionModel, Dataset, Query
from graph.runner import run_analysis

log = structlog.get_logger()

router = APIRouter(prefix="/api")


class QueryRequest(BaseModel):
    question: str


@router.post("/sessions/{session_id}/query")
def create_query(
    session_id: str,
    body: QueryRequest,
    db: DBSession = Depends(get_session),
) -> dict:
    question = body.question.strip()
    if not question:
        raise api_error("BLANK_QUESTION", "Question cannot be blank", 400)

    session = db.get(SessionModel, session_id)
    if session is None:
        raise api_error("NOT_FOUND", f"Session {session_id} not found", 404)

    dataset_count = db.query(Dataset).filter(Dataset.session_id == session_id).count()
    if dataset_count == 0:
        raise api_error(
            "NO_DATASETS",
            "Upload at least one file before asking a question",
            422,
        )

    query = Query(session_id=session_id, question=question, status="pending")
    db.add(query)
    db.flush()

    return ok({"query_id": query.id, "status": query.status})


@router.get("/sessions/{session_id}/queries/{query_id}/stream")
async def stream_query(
    session_id: str,
    query_id: str,
    dataset_ids: str | None = QueryParam(None),
) -> StreamingResponse:
    parsed_dataset_ids: list[str] | None = (
        [d.strip() for d in dataset_ids.split(",") if d.strip()]
        if dataset_ids
        else None
    )

    async def event_generator():
        # Check if already completed — replay from DB
        with create_db_session() as db:
            query = db.get(Query, query_id)
            if query is None:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Query not found'})}\n\n"
                return
            if query.session_id != session_id:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Query does not belong to this session'})}\n\n"
                return
            question = query.question
            if query.status == "completed" and query.answer_text:
                # Replay completed answer
                yield f"data: {json.dumps({'type': 'token', 'content': query.answer_text})}\n\n"
                if query.summary_table_json:
                    table = json.loads(query.summary_table_json)
                    yield f"data: {json.dumps({'type': 'table', **table})}\n\n"
                if query.chart_json:
                    chart = json.loads(query.chart_json)
                    yield f"data: {json.dumps({'type': 'chart', **chart})}\n\n"
                if query.suggestions_json:
                    suggestions = json.loads(query.suggestions_json)
                    yield f"data: {json.dumps({'type': 'suggestions', 'questions': suggestions})}\n\n"
                if query.generated_code:
                    yield f"data: {json.dumps({'type': 'code', 'generated_code': query.generated_code, 'reasoning_trace': query.reasoning_trace or ''})}\n\n"
                if query.prompt_tokens:
                    yield f"data: {json.dumps({'type': 'usage', 'prompt_tokens': query.prompt_tokens, 'completion_tokens': query.completion_tokens or 0, 'cost_usd': query.cost_usd or 0})}\n\n"
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                return
            if query.status == "failed":
                yield f"data: {json.dumps({'type': 'error', 'message': query.error_message or 'Query failed'})}\n\n"
                return

        # Run the graph and stream events via a thread-safe queue
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        def sse_send(data: str) -> None:
            # Called from asyncio.to_thread — must use call_soon_threadsafe
            loop.call_soon_threadsafe(queue.put_nowait, data)

        async def run_and_signal():
            try:
                await run_analysis(session_id, query_id, question, sse_send, parsed_dataset_ids)
            except Exception as exc:
                log.error("run_and_signal_error", error=str(exc))
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    json.dumps({"type": "error", "message": str(exc)})
                )
            finally:
                # Use a small delay to ensure all queued events are processed first
                loop.call_soon_threadsafe(queue.put_nowait, None)

        asyncio.create_task(run_and_signal())

        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=120.0)
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Query timed out'})}\n\n"
                break
            if item is None:
                break
            yield f"data: {item}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
