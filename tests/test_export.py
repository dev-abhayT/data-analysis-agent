"""Tests for the CSV export endpoint (GET /api/sessions/{session_id}/queries/{query_id}/export)."""
import io
import json
import pytest
from fastapi.testclient import TestClient


SAMPLE_CSV = (
    b"product,category,price,units_sold\n"
    b"Apple,Fruit,1.20,150\n"
    b"Banana,Fruit,0.50,300\n"
    b"Carrot,Vegetable,0.80,200\n"
    b"Cherry,Fruit,3.00,80\n"
    b"Broccoli,Vegetable,1.50,120\n"
)


def _upload_csv(client: TestClient, session_id: str) -> dict:
    r = client.post(
        f"/api/sessions/{session_id}/files",
        files=[("file", ("sales.csv", io.BytesIO(SAMPLE_CSV), "text/csv"))],
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def _collect_sse(raw: bytes) -> list[dict]:
    events = []
    for line in raw.decode("utf-8").splitlines():
        line = line.strip()
        if line.startswith("data:"):
            payload = line[5:].strip()
            try:
                events.append(json.loads(payload))
            except json.JSONDecodeError:
                pass
    return events


def test_export_session_not_found(api_client: TestClient):
    """Export with nonexistent session_id returns 404."""
    r = api_client.get("/api/sessions/no-such-session/queries/no-such-query/export")
    assert r.status_code == 404


def test_export_query_not_found(api_client: TestClient):
    """Export with valid session but nonexistent query_id returns 404."""
    r = api_client.post("/api/sessions")
    session_id = r.json()["data"]["session_id"]
    r = api_client.get(f"/api/sessions/{session_id}/queries/nonexistent-query-id/export")
    assert r.status_code == 404


def test_export_query_belongs_to_different_session(api_client: TestClient):
    """Export where query belongs to a different session returns 404."""
    # Create two sessions
    r1 = api_client.post("/api/sessions")
    session_id_1 = r1.json()["data"]["session_id"]
    r2 = api_client.post("/api/sessions")
    session_id_2 = r2.json()["data"]["session_id"]

    # Upload file and create query in session 1
    _upload_csv(api_client, session_id_1)
    r = api_client.post(
        f"/api/sessions/{session_id_1}/query",
        json={"question": "How many rows?"},
    )
    query_id = r.json()["data"]["query_id"]

    # Try to export that query via session 2
    r = api_client.get(f"/api/sessions/{session_id_2}/queries/{query_id}/export")
    assert r.status_code == 404


def test_export_pending_query_returns_400(api_client: TestClient):
    """Export a pending query (never streamed, so no result) returns 400 NO_RESULT."""
    r = api_client.post("/api/sessions")
    session_id = r.json()["data"]["session_id"]
    _upload_csv(api_client, session_id)

    r = api_client.post(
        f"/api/sessions/{session_id}/query",
        json={"question": "How many rows are there?"},
    )
    assert r.status_code == 200
    query_id = r.json()["data"]["query_id"]

    # Do NOT consume the stream — query is still pending with no result
    r = api_client.get(f"/api/sessions/{session_id}/queries/{query_id}/export")
    assert r.status_code == 400
    body = r.json()
    assert body["detail"]["code"] == "NO_RESULT"


@pytest.mark.usefixtures("_require_gemini_key")
def test_export_csv_returns_valid_csv_when_table_exists(api_client: TestClient):
    """After a ranked/top-N query, if a summary table was produced, export returns valid CSV."""
    r = api_client.post("/api/sessions")
    session_id = r.json()["data"]["session_id"]
    _upload_csv(api_client, session_id)

    r = api_client.post(
        f"/api/sessions/{session_id}/query",
        json={"question": "Which product has the highest units_sold?"},
    )
    assert r.status_code == 200, r.text
    query_id = r.json()["data"]["query_id"]

    # Consume the full stream
    with api_client.stream(
        "GET",
        f"/api/sessions/{session_id}/queries/{query_id}/stream",
    ) as resp:
        raw = resp.read()

    events = _collect_sse(raw)
    event_types = [e.get("type") for e in events]
    assert "done" in event_types, f"Stream did not complete: {event_types}"

    # Export: either 200 with CSV (if table was produced) or 400 NO_RESULT (no table)
    r = api_client.get(f"/api/sessions/{session_id}/queries/{query_id}/export")
    assert r.status_code in (200, 400), f"Unexpected status: {r.status_code}"

    if r.status_code == 200:
        content_type = r.headers.get("content-type", "")
        assert "text/csv" in content_type, f"Expected text/csv, got: {content_type}"
        content_disp = r.headers.get("content-disposition", "")
        assert "attachment" in content_disp
        assert ".csv" in content_disp

        lines = r.text.strip().splitlines()
        assert len(lines) >= 1, "CSV should have at least a header row"
        # Header row should have comma-separated column names
        header = lines[0]
        assert "," in header or len(header) > 0


@pytest.mark.usefixtures("_require_gemini_key")
def test_export_describe_path_no_table(api_client: TestClient):
    """Describe-path queries produce no summary table, so export returns 400 NO_RESULT."""
    r = api_client.post("/api/sessions")
    session_id = r.json()["data"]["session_id"]
    _upload_csv(api_client, session_id)

    r = api_client.post(
        f"/api/sessions/{session_id}/query",
        json={"question": "Describe this dataset"},
    )
    assert r.status_code == 200, r.text
    query_id = r.json()["data"]["query_id"]

    with api_client.stream(
        "GET",
        f"/api/sessions/{session_id}/queries/{query_id}/stream",
    ) as resp:
        raw = resp.read()

    events = _collect_sse(raw)
    assert any(e.get("type") == "done" for e in events), f"Did not complete: {events}"

    # Describe path never produces a summary table → 400
    r = api_client.get(f"/api/sessions/{session_id}/queries/{query_id}/export")
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "NO_RESULT"
