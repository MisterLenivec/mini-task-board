"""File-path configuration and one database session per request."""

import os
from collections.abc import Iterator
from pathlib import Path

from fastapi import Request
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def resolve_db_path(db_path: str | Path | None) -> Path:
    configured = db_path if db_path is not None else os.environ.get("TASK_BOARD_DB_PATH")
    path = (
        Path(configured).expanduser() if configured is not None else Path("data/task_board.sqlite3")
    )
    return (path if path.is_absolute() else PROJECT_ROOT / path).resolve()


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session
