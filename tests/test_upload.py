"""
Integration tests for the upload endpoint.
Uses the real Gemini API for starter question generation.
"""
import io
import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixture: CSV bytes for upload
# ---------------------------------------------------------------------------

SAMPLE_CSV = b"product,price,units_sold\nApple,1.20,150\nBanana,0.50,300\nCherry,3.00,80\n"


def _csv_file(content: bytes = SAMPLE_CSV, filename: str = "sales.csv"):
    return ("file", (filename, io.BytesIO(content), "text/csv"))


# ---------------------------------------------------------------------------
# Happy path — upload a real CSV, Gemini generates starter questions
# ---------------------------------------------------------------------------

@pytest.mark.usefixtures("_require_gemini_key")
def test_upload_csv_returns_profile(api_client: TestClient):
    # Create session first
    r = api_client.post("/api/sessions")
    assert r.status_code == 200
    session_id = r.json()["data"]["session_id"]

    # Upload file
    r = api_client.post(
        f"/api/sessions/{session_id}/files",
        files=[_csv_file()],
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]

    assert data["dataset_id"]
    assert data["filename"] == "sales.csv"
    assert data["row_count"] == 3
    assert "product" in data["column_names"]
    assert "price" in data["column_names"]
    assert "units_sold" in data["column_names"]
    assert isinstance(data["column_types"], dict)
    assert isinstance(data["null_counts"], dict)
    assert isinstance(data["sample_values"], dict)
    assert "Apple" in data["sample_values"].get("product", [])


@pytest.mark.usefixtures("_require_gemini_key")
def test_upload_csv_starter_questions_generated(api_client: TestClient):
    """Starter questions are a non-empty list of strings from Gemini."""
    r = api_client.post("/api/sessions")
    session_id = r.json()["data"]["session_id"]

    r = api_client.post(
        f"/api/sessions/{session_id}/files",
        files=[_csv_file()],
    )
    assert r.status_code == 200
    data = r.json()["data"]

    questions = data["starter_questions"]
    assert isinstance(questions, list)
    assert len(questions) > 0
    for q in questions:
        assert isinstance(q, str)
        assert len(q) > 5  # not empty strings


@pytest.mark.usefixtures("_require_gemini_key")
def test_upload_persisted_in_session(api_client: TestClient):
    """Dataset appears in GET /api/sessions/{id} after upload."""
    r = api_client.post("/api/sessions")
    session_id = r.json()["data"]["session_id"]

    r = api_client.post(
        f"/api/sessions/{session_id}/files",
        files=[_csv_file()],
    )
    assert r.status_code == 200
    dataset_id = r.json()["data"]["dataset_id"]

    # Fetch session
    r = api_client.get(f"/api/sessions/{session_id}")
    assert r.status_code == 200
    datasets = r.json()["data"]["datasets"]
    assert len(datasets) == 1
    assert datasets[0]["dataset_id"] == dataset_id
    assert datasets[0]["filename"] == "sales.csv"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_upload_session_not_found(api_client: TestClient):
    r = api_client.post(
        "/api/sessions/nonexistent-session/files",
        files=[_csv_file()],
    )
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "NOT_FOUND"


def test_upload_unsupported_file_type(api_client: TestClient):
    r = api_client.post("/api/sessions")
    session_id = r.json()["data"]["session_id"]

    r = api_client.post(
        f"/api/sessions/{session_id}/files",
        files=[("file", ("data.json", io.BytesIO(b'{"x": 1}'), "application/json"))],
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "UNSUPPORTED_TYPE"


def test_upload_empty_file(api_client: TestClient):
    r = api_client.post("/api/sessions")
    session_id = r.json()["data"]["session_id"]

    r = api_client.post(
        f"/api/sessions/{session_id}/files",
        files=[("file", ("empty.csv", io.BytesIO(b""), "text/csv"))],
    )
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "EMPTY_FILE"


def test_upload_max_3_files_enforced(api_client: TestClient):
    """Session rejects a 4th file upload."""
    r = api_client.post("/api/sessions")
    session_id = r.json()["data"]["session_id"]

    for i in range(3):
        csv = f"col\n{i}\n".encode()
        r = api_client.post(
            f"/api/sessions/{session_id}/files",
            files=[("file", (f"file{i}.csv", io.BytesIO(csv), "text/csv"))],
        )
        # These may fail on Gemini call if key not set — just check they don't 400
        # for TOO_MANY_FILES
        if r.status_code == 400:
            assert r.json()["detail"]["code"] != "TOO_MANY_FILES"

    # 4th file must be rejected
    r = api_client.post(
        f"/api/sessions/{session_id}/files",
        files=[("file", ("extra.csv", io.BytesIO(b"col\n1\n"), "text/csv"))],
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "TOO_MANY_FILES"


# ---------------------------------------------------------------------------
# Session CRUD (no LLM key required)
# ---------------------------------------------------------------------------

def test_create_session_returns_id(api_client: TestClient):
    r = api_client.post("/api/sessions")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["session_id"]
    assert data["created_at"]


def test_get_session_not_found(api_client: TestClient):
    r = api_client.get("/api/sessions/bad-id")
    assert r.status_code == 404


def test_get_session_empty(api_client: TestClient):
    r = api_client.post("/api/sessions")
    session_id = r.json()["data"]["session_id"]

    r = api_client.get(f"/api/sessions/{session_id}")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["session_id"] == session_id
    assert data["datasets"] == []
    assert data["queries"] == []
