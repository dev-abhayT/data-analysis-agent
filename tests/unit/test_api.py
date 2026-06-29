"""API contract tests — no LLM key required."""


def test_health(api_client):
    r = api_client.get("/health")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "ok"


def test_create_session(api_client):
    r = api_client.post("/api/sessions")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["session_id"]
    assert data["created_at"]


def test_get_session_not_found(api_client):
    r = api_client.get("/api/sessions/nonexistent-id")
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "NOT_FOUND"


def test_create_query_blank(api_client):
    r = api_client.post("/api/sessions")
    session_id = r.json()["data"]["session_id"]
    r = api_client.post(
        f"/api/sessions/{session_id}/query", json={"question": ""}
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "BLANK_QUESTION"


def test_create_query_no_datasets(api_client):
    r = api_client.post("/api/sessions")
    session_id = r.json()["data"]["session_id"]
    r = api_client.post(
        f"/api/sessions/{session_id}/query",
        json={"question": "How many rows?"},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "NO_DATASETS"


def test_upload_session_not_found(api_client):
    import io
    r = api_client.post(
        "/api/sessions/nonexistent/files",
        files=[("file", ("data.csv", io.BytesIO(b"a,b\n1,2\n"), "text/csv"))],
    )
    assert r.status_code == 404


def test_upload_bad_filetype(api_client):
    import io
    r = api_client.post("/api/sessions")
    session_id = r.json()["data"]["session_id"]
    r = api_client.post(
        f"/api/sessions/{session_id}/files",
        files=[("file", ("data.pdf", io.BytesIO(b"%PDF"), "application/pdf"))],
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "UNSUPPORTED_TYPE"
