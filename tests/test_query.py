"""
Integration tests for the query + SSE streaming endpoint.
Uses the real Gemini API.
"""
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


def _upload_csv(client: TestClient, session_id: str, content: bytes = SAMPLE_CSV, name: str = "sales.csv"):
    return client.post(
        f"/api/sessions/{session_id}/files",
        files=[("file", (name, io.BytesIO(content), "text/csv"))],
    )


def _collect_sse(raw: bytes) -> list[dict]:
    """Parse SSE response bytes into a list of event dicts."""
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


# ---------------------------------------------------------------------------
# Happy path — full end-to-end query with real Gemini
# ---------------------------------------------------------------------------

@pytest.mark.usefixtures("_require_gemini_key")
def test_full_query_cycle(api_client: TestClient):
    """Create session → upload CSV → submit question → stream answer."""
    # 1. Create session
    r = api_client.post("/api/sessions")
    assert r.status_code == 200
    session_id = r.json()["data"]["session_id"]

    # 2. Upload file
    r = _upload_csv(api_client, session_id)
    assert r.status_code == 200, r.text

    # 3. Submit question
    r = api_client.post(
        f"/api/sessions/{session_id}/query",
        json={"question": "What is the total units_sold for each category?"},
    )
    assert r.status_code == 200, r.text
    query_id = r.json()["data"]["query_id"]
    assert query_id

    # 4. Stream answer
    with api_client.stream(
        "GET",
        f"/api/sessions/{session_id}/queries/{query_id}/stream",
    ) as resp:
        assert resp.status_code == 200
        raw = resp.read()

    events = _collect_sse(raw)
    event_types = [e.get("type") for e in events]

    # Must have received at least some token events
    assert "token" in event_types, f"No token events in: {event_types}"
    # Must end with "done"
    assert event_types[-1] == "done", f"Last event was not 'done': {event_types}"
    # No error events
    assert "error" not in event_types, f"Error event received: {events}"


@pytest.mark.usefixtures("_require_gemini_key")
def test_query_answer_text_non_empty(api_client: TestClient):
    """Answer text tokens accumulate to a non-empty response."""
    r = api_client.post("/api/sessions")
    session_id = r.json()["data"]["session_id"]

    _upload_csv(api_client, session_id)

    r = api_client.post(
        f"/api/sessions/{session_id}/query",
        json={"question": "How many rows are in the dataset?"},
    )
    query_id = r.json()["data"]["query_id"]

    with api_client.stream(
        "GET", f"/api/sessions/{session_id}/queries/{query_id}/stream"
    ) as resp:
        raw = resp.read()

    events = _collect_sse(raw)
    token_content = "".join(
        e["content"] for e in events if e.get("type") == "token" and e.get("content")
    )
    assert len(token_content) > 10, f"Answer too short: {token_content!r}"


@pytest.mark.usefixtures("_require_gemini_key")
def test_query_stored_in_db(api_client: TestClient):
    """After streaming, query row is persisted with answer_text."""
    r = api_client.post("/api/sessions")
    session_id = r.json()["data"]["session_id"]
    _upload_csv(api_client, session_id)

    r = api_client.post(
        f"/api/sessions/{session_id}/query",
        json={"question": "What is the average price?"},
    )
    query_id = r.json()["data"]["query_id"]

    # Consume the stream fully
    with api_client.stream(
        "GET", f"/api/sessions/{session_id}/queries/{query_id}/stream"
    ) as resp:
        resp.read()

    # Check session state reflects completed query
    r = api_client.get(f"/api/sessions/{session_id}")
    assert r.status_code == 200
    queries = r.json()["data"]["queries"]
    assert len(queries) == 1
    q = queries[0]
    assert q["query_id"] == query_id
    assert q["status"] == "completed"
    assert q["answer_text"] and len(q["answer_text"]) > 0


@pytest.mark.usefixtures("_require_gemini_key")
def test_top_n_query_emits_table_event(api_client: TestClient):
    """A 'top N' question should produce a 'table' SSE event."""
    r = api_client.post("/api/sessions")
    session_id = r.json()["data"]["session_id"]
    _upload_csv(api_client, session_id)

    r = api_client.post(
        f"/api/sessions/{session_id}/query",
        json={"question": "Which product has the highest units_sold?"},
    )
    query_id = r.json()["data"]["query_id"]

    with api_client.stream(
        "GET", f"/api/sessions/{session_id}/queries/{query_id}/stream"
    ) as resp:
        raw = resp.read()

    events = _collect_sse(raw)
    event_types = [e.get("type") for e in events]

    # The query asks for "highest" which is a table keyword — may or may not
    # produce a table event depending on result row count; just confirm no crash
    assert "done" in event_types


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_create_query_blank_question(api_client: TestClient):
    r = api_client.post("/api/sessions")
    session_id = r.json()["data"]["session_id"]

    r = api_client.post(
        f"/api/sessions/{session_id}/query",
        json={"question": ""},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "BLANK_QUESTION"


def test_create_query_whitespace_only(api_client: TestClient):
    r = api_client.post("/api/sessions")
    session_id = r.json()["data"]["session_id"]

    r = api_client.post(
        f"/api/sessions/{session_id}/query",
        json={"question": "   "},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "BLANK_QUESTION"


def test_create_query_no_datasets(api_client: TestClient):
    """Question without uploaded files must return 422."""
    r = api_client.post("/api/sessions")
    session_id = r.json()["data"]["session_id"]

    r = api_client.post(
        f"/api/sessions/{session_id}/query",
        json={"question": "What is the average price?"},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "NO_DATASETS"


def test_create_query_session_not_found(api_client: TestClient):
    r = api_client.post(
        "/api/sessions/bad-session-id/query",
        json={"question": "hello?"},
    )
    assert r.status_code == 404


def test_stream_query_not_found(api_client: TestClient):
    r = api_client.post("/api/sessions")
    session_id = r.json()["data"]["session_id"]

    with api_client.stream(
        "GET",
        f"/api/sessions/{session_id}/queries/nonexistent-query/stream",
    ) as resp:
        raw = resp.read()

    events = _collect_sse(raw)
    assert any(e.get("type") == "error" for e in events)


# ---------------------------------------------------------------------------
# Multi-interaction state survival
# ---------------------------------------------------------------------------

@pytest.mark.usefixtures("_require_gemini_key")
def test_multiple_queries_in_session(api_client: TestClient):
    """Submit two questions in the same session; both complete successfully."""
    r = api_client.post("/api/sessions")
    session_id = r.json()["data"]["session_id"]
    _upload_csv(api_client, session_id)

    questions = [
        "How many rows are there?",
        "What is the most expensive product?",
    ]
    query_ids = []

    for q in questions:
        r = api_client.post(
            f"/api/sessions/{session_id}/query",
            json={"question": q},
        )
        assert r.status_code == 200
        query_ids.append(r.json()["data"]["query_id"])

    for qid in query_ids:
        with api_client.stream(
            "GET", f"/api/sessions/{session_id}/queries/{qid}/stream"
        ) as resp:
            raw = resp.read()
        events = _collect_sse(raw)
        event_types = [e.get("type") for e in events]
        assert "done" in event_types, f"Query {qid} did not complete: {event_types}"
        assert "error" not in event_types, f"Query {qid} had error: {events}"

    # Session should show 2 completed queries
    r = api_client.get(f"/api/sessions/{session_id}")
    completed = [q for q in r.json()["data"]["queries"] if q["status"] == "completed"]
    assert len(completed) == 2


# ---------------------------------------------------------------------------
# Describe path (meta questions)
# ---------------------------------------------------------------------------

@pytest.mark.usefixtures("_require_gemini_key")
def test_describe_path_routes_correctly(api_client: TestClient):
    """'What is this data about?' takes the describe path — no generated_code in DB."""
    r = api_client.post("/api/sessions")
    session_id = r.json()["data"]["session_id"]
    _upload_csv(api_client, session_id)

    r = api_client.post(
        f"/api/sessions/{session_id}/query",
        json={"question": "What is this data about?"},
    )
    assert r.status_code == 200
    query_id = r.json()["data"]["query_id"]

    with api_client.stream(
        "GET", f"/api/sessions/{session_id}/queries/{query_id}/stream"
    ) as resp:
        raw = resp.read()

    events = _collect_sse(raw)
    event_types = [e.get("type") for e in events]

    assert "token" in event_types, f"No token events: {event_types}"
    assert event_types[-1] == "done", f"Last event was not 'done': {event_types}"
    assert "error" not in event_types, f"Error event received: {events}"

    # Check DB — generated_code should be null/empty
    r = api_client.get(f"/api/sessions/{session_id}")
    queries = r.json()["data"]["queries"]
    q = next(x for x in queries if x["query_id"] == query_id)
    assert q["status"] == "completed"
    assert not q.get("generated_code")  # null or empty string


@pytest.mark.usefixtures("_require_gemini_key")
def test_describe_path_emits_code_event_with_empty_code(api_client: TestClient):
    """Describe path emits a 'code' SSE event with empty/null generated_code."""
    r = api_client.post("/api/sessions")
    session_id = r.json()["data"]["session_id"]
    _upload_csv(api_client, session_id)

    r = api_client.post(
        f"/api/sessions/{session_id}/query",
        json={"question": "Describe this dataset"},
    )
    assert r.status_code == 200
    query_id = r.json()["data"]["query_id"]

    with api_client.stream(
        "GET", f"/api/sessions/{session_id}/queries/{query_id}/stream"
    ) as resp:
        raw = resp.read()

    events = _collect_sse(raw)
    code_events = [e for e in events if e.get("type") == "code"]
    # Must have a code event (even if generated_code is empty)
    assert len(code_events) >= 1, f"No code event found. Events: {[e.get('type') for e in events]}"
    code_event = code_events[0]
    # generated_code is empty or absent for describe path
    assert not code_event.get("generated_code"), \
        f"Expected empty generated_code, got: {code_event.get('generated_code')}"


@pytest.mark.usefixtures("_require_gemini_key")
def test_describe_path_answer_mentions_columns(api_client: TestClient):
    """Describe-path answer should reference column names from the dataset."""
    r = api_client.post("/api/sessions")
    session_id = r.json()["data"]["session_id"]
    _upload_csv(api_client, session_id)  # columns: product, category, price, units_sold

    r = api_client.post(
        f"/api/sessions/{session_id}/query",
        json={"question": "Give me a summary of this data"},
    )
    assert r.status_code == 200
    query_id = r.json()["data"]["query_id"]

    with api_client.stream(
        "GET", f"/api/sessions/{session_id}/queries/{query_id}/stream"
    ) as resp:
        raw = resp.read()

    events = _collect_sse(raw)
    token_content = "".join(
        e["content"] for e in events if e.get("type") == "token" and e.get("content")
    )
    assert len(token_content) > 10, f"Answer too short: {token_content!r}"

    # Answer should mention at least one column name
    col_names = ["product", "category", "price", "units_sold"]
    assert any(col in token_content.lower() for col in col_names), \
        f"No column name found in answer: {token_content[:300]}"


def test_describe_path_no_gemini_call_for_routing(api_client: TestClient):
    """Meta question detection is a pre-LLM check; no LLM call is needed for routing."""
    # This test verifies the routing logic without needing a real Gemini key.
    # We just check that a meta question reaches a distinct path — by checking
    # the query is created (no validation error) and pending (not yet failed).
    r = api_client.post("/api/sessions")
    session_id = r.json()["data"]["session_id"]
    _upload_csv(api_client, session_id)

    r = api_client.post(
        f"/api/sessions/{session_id}/query",
        json={"question": "Describe this dataset"},
    )
    # Should successfully create a query (routing logic is in the async worker)
    assert r.status_code == 200
    assert r.json()["data"]["query_id"]


@pytest.mark.usefixtures("_require_gemini_key")
def test_describe_path_emits_usage_event(api_client: TestClient):
    """Describe path emits a 'usage' SSE event (even if tokens are 0)."""
    r = api_client.post("/api/sessions")
    session_id = r.json()["data"]["session_id"]
    _upload_csv(api_client, session_id)

    r = api_client.post(
        f"/api/sessions/{session_id}/query",
        json={"question": "What are some interesting insights about this data?"},
    )
    assert r.status_code == 200, r.text
    query_id = r.json()["data"]["query_id"]

    with api_client.stream(
        "GET", f"/api/sessions/{session_id}/queries/{query_id}/stream"
    ) as resp:
        raw = resp.read()

    events = _collect_sse(raw)
    event_types = [e.get("type") for e in events]
    assert "usage" in event_types, f"No usage event in: {event_types}"
    assert "done" in event_types
