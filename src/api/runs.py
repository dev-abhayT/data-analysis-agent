"""
Legacy runs endpoint — kept for import compatibility.
The router is no longer included in the main app (replaced by sessions/upload/query).
"""
from fastapi import APIRouter

from api._common import ok, api_error
from db.models import RunRow

router = APIRouter()


@router.post("/runs")
def create_run() -> dict:
    raise api_error("GONE", "The /runs endpoint has been removed. Use /api/sessions.", 410)


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    raise api_error("GONE", "The /runs endpoint has been removed. Use /api/sessions.", 410)
