from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

log = structlog.get_logger()


@asynccontextmanager
async def _lifespan(app: FastAPI):
    from db.session import init_db
    from config.settings import get_settings
    init_db()
    # Ensure upload directory exists
    upload_dir = Path(get_settings().upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    log.info("startup_complete", upload_dir=str(upload_dir))
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Data Analysis Agent", version="0.1.0", lifespan=_lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from api import health
    from api.sessions import router as sessions_router
    from api.upload import router as upload_router
    from api.query import router as query_router

    app.include_router(health.router)
    app.include_router(sessions_router)
    app.include_router(upload_router)
    app.include_router(query_router)

    # Serve the built Next.js static export at /app
    frontend_out = Path(__file__).resolve().parent.parent.parent / "frontend" / "out"
    if frontend_out.exists():
        app.mount("/app", StaticFiles(directory=str(frontend_out), html=True), name="frontend")

    return app


app = create_app()
