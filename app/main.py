"""Application entry point and static page delivery."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import sessionmaker

from app.db import resolve_db_path
from app.models import Base
from app.routes import router

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(db_path: str | Path | None = None) -> FastAPI:
    """Create an isolated application without opening or creating its database yet."""
    database_path = resolve_db_path(db_path)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        database_path.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(
            URL.create("sqlite", database=str(database_path)),
            connect_args={"check_same_thread": False},
        )
        try:
            Base.metadata.create_all(engine)
            application.state.session_factory = sessionmaker(engine, expire_on_commit=False)
            yield
        finally:
            engine.dispose()

    application = FastAPI(title="Mini Task Board", lifespan=lifespan)
    application.state.db_path = database_path
    application.include_router(router)

    @application.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return application


app = create_app()
