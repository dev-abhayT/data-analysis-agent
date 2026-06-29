import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api._common import ok, api_error
from db.session import get_session
from db.models import Session as SessionModel, Dataset, Query

router = APIRouter(prefix="/api")


@router.post("/sessions")
def create_session(db: Session = Depends(get_session)) -> dict:
    session = SessionModel()
    db.add(session)
    db.flush()
    return ok({"session_id": session.id, "created_at": session.created_at.isoformat()})


@router.get("/sessions/{session_id}")
def get_session_detail(session_id: str, db: Session = Depends(get_session)) -> dict:
    session = db.get(SessionModel, session_id)
    if session is None:
        raise api_error("NOT_FOUND", f"Session {session_id} not found", 404)

    datasets_out = []
    for d in session.datasets:
        datasets_out.append({
            "dataset_id": d.id,
            "filename": d.filename,
            "row_count": d.row_count,
            "column_names": json.loads(d.column_names_json or "[]"),
            "column_types": json.loads(d.column_types_json or "{}"),
            "null_counts": json.loads(d.null_counts_json or "{}"),
            "sample_values": json.loads(d.sample_values_json or "{}"),
            "starter_questions": json.loads(d.starter_questions_json or "[]"),
        })

    queries_out = []
    for q in session.queries:
        queries_out.append({
            "query_id": q.id,
            "question": q.question,
            "status": q.status,
            "answer_text": q.answer_text,
            "summary_table_json": (
                json.loads(q.summary_table_json) if q.summary_table_json else None
            ),
            "generated_code": q.generated_code,
            "reasoning_trace": q.reasoning_trace,
            "prompt_tokens": q.prompt_tokens,
            "completion_tokens": q.completion_tokens,
            "cost_usd": q.cost_usd,
            "created_at": q.created_at.isoformat(),
        })

    return ok({
        "session_id": session.id,
        "created_at": session.created_at.isoformat(),
        "datasets": datasets_out,
        "queries": queries_out,
    })
