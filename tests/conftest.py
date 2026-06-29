"""
Top-level test configuration.

- _reset_settings_singleton: ensures Settings is re-read from env each test.
- _isolated_db: patches the DB engine/session to use a fresh in-memory SQLite
  DB per test so nothing touches data/agent.db.
- app / async_client: FastAPI app and async HTTP client wired to the isolated DB.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import config.settings as settings_module
import db.session as session_module
from db.models import Base


@pytest.fixture(autouse=True)
def _reset_settings_singleton():
    """Reset the Settings singleton so env monkeypatches take effect."""
    settings_module._settings = None
    yield
    settings_module._settings = None


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    """
    Replace the global SQLAlchemy engine and session factory with a fresh
    SQLite DB in a temporary directory for each test.
    """
    db_url = f"sqlite:///{tmp_path}/test.db"
    monkeypatch.setenv("AGENT_DATABASE_URL", db_url)

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    monkeypatch.setattr(session_module, "_engine", engine)
    monkeypatch.setattr(session_module, "_SessionLocal", factory)
    monkeypatch.setattr(session_module, "init_db", lambda: None)

    yield engine
    engine.dispose()


@pytest.fixture
def app(_isolated_db):
    """Fresh FastAPI app with isolated DB."""
    from api import create_app
    return create_app()


@pytest.fixture
def api_client(_isolated_db):
    """Synchronous TestClient for non-streaming tests."""
    from fastapi.testclient import TestClient
    from api import app as _app
    with TestClient(_app, raise_server_exceptions=True) as client:
        yield client


@pytest.fixture
async def async_client(app):
    """Async HTTPX client for async API tests."""
    import httpx
    from httpx import ASGITransport
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest.fixture
def _require_gemini_key():
    """Skip test if AGENT_GEMINI_API_KEY is not configured."""
    from config.settings import get_settings
    s = get_settings()
    if not s.gemini_api_key:
        pytest.skip("AGENT_GEMINI_API_KEY not set in .env")
