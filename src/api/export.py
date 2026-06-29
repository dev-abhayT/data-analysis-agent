"""CSV export endpoint for query results."""
import csv
import io
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as DBSession

from api._common import api_error
from db.session import get_session
from db.models import Query, Session as SessionModel

router = APIRouter(prefix="/api")


@router.get("/sessions/{session_id}/queries/{query_id}/export")
def export_query_csv(
    session_id: str,
    query_id: str,
    db: DBSession = Depends(get_session),
) -> StreamingResponse:
    """Export a query's result table as a CSV file download."""
    session = db.get(SessionModel, session_id)
    if session is None:
        raise api_error("NOT_FOUND", f"Session {session_id} not found", 404)

    query = db.get(Query, query_id)
    if query is None or query.session_id != session_id:
        raise api_error("NOT_FOUND", f"Query {query_id} not found", 404)

    if not query.summary_table_json:
        raise api_error("NO_RESULT", "No result data available for export", 400)

    table = json.loads(query.summary_table_json)
    columns = table.get("columns", [])
    rows = table.get("rows", [])

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    writer.writerows(rows)
    csv_content = output.getvalue()

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="query_{query_id[:8]}.csv"',
            "Content-Length": str(len(csv_content.encode("utf-8"))),
        },
    )
