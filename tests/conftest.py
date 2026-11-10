"""Isolated application clients and a real, temporary Uvicorn server."""

import os
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(db_path=tmp_path / "test.sqlite3")) as test_client:
        yield test_client


@pytest.fixture
def server_factory(tmp_path):
    """Yield start(db_path=None), also usable to restart against the same database."""

    @contextmanager
    def start(db_path=None):
        environment = os.environ.copy()
        environment["TASK_BOARD_DB_PATH"] = str(db_path or tmp_path / "server.sqlite3")
        with tempfile.TemporaryFile(mode="w+t") as log:
            # Pass the bound socket to Uvicorn, avoiding a free-port selection race.
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
                listener.bind(("127.0.0.1", 0))
                listener.listen(128)
                port = listener.getsockname()[1]
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "app.main:app",
                        "--fd",
                        str(listener.fileno()),
                        "--log-level",
                        "warning",
                    ],
                    cwd=PROJECT_ROOT,
                    env=environment,
                    pass_fds=(listener.fileno(),),
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )

            base_url = f"http://127.0.0.1:{port}"
            try:
                deadline = time.monotonic() + 15
                with httpx.Client(base_url=base_url, timeout=0.5, trust_env=False) as probe:
                    while time.monotonic() < deadline:
                        if process.poll() is not None:
                            break
                        try:
                            if probe.get("/").status_code == 200:
                                break
                        except httpx.HTTPError:
                            pass
                        time.sleep(0.05)
                    else:
                        raise RuntimeError("Uvicorn did not become ready within 15 seconds")

                if process.poll() is not None:
                    log.seek(0)
                    raise RuntimeError(f"Uvicorn exited during startup:\n{log.read()}")
                yield base_url
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)

    return start


@pytest.fixture
def live_server(server_factory):
    with server_factory() as base_url:
        yield base_url
