"""The agreed CRUD contract, database constraints and restart persistence."""

import sqlite3

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app

STATUSES = ["todo", "in_progress", "done"]


def test_crud_defaults_partial_update_and_delete(client):
    assert client.get("/api/tasks").json() == []
    response = client.post("/api/tasks", json={"title": "  Первая задача\n"})
    assert response.status_code == 201
    task = response.json()
    assert task == {"id": task["id"], "title": "Первая задача", "description": "", "status": "todo"}
    url = f"/api/tasks/{task['id']}"
    assert client.get(url).json() == task
    assert client.patch(url, json={}).json() == task

    response = client.patch(url, json={"description": "  описание\n", "status": "in_progress"})
    assert response.status_code == 200
    assert response.json() == {**task, "description": "  описание\n", "status": "in_progress"}
    assert client.patch(url, json={"description": ""}).json()["description"] == ""
    assert client.patch(url, json={"title": "  Новое  "}).json()["title"] == "Новое"
    deleted = client.delete(url)
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert client.get("/api/tasks").json() == []
    assert client.get(url).status_code == 404


def test_duplicates_sorting_and_filter(client):
    tasks = [
        client.post("/api/tasks", json={"title": "Одинаковое название", "status": status}).json()
        for status in reversed(STATUSES)
    ]
    assert client.get("/api/tasks").json() == sorted(tasks, key=lambda task: task["id"])
    for status in STATUSES:
        result = client.get("/api/tasks", params={"status": status})
        assert result.status_code == 200
        assert result.json() == [task for task in tasks if task["status"] == status]


@pytest.mark.parametrize("initial", STATUSES)
@pytest.mark.parametrize("updated", STATUSES)
def test_all_status_transitions(client, initial, updated):
    task = client.post("/api/tasks", json={"title": "Статус", "status": initial}).json()
    response = client.patch(f"/api/tasks/{task['id']}", json={"status": updated})
    assert response.status_code == 200
    assert response.json()["status"] == updated


@pytest.mark.parametrize("title", ["x", "x" * 200, " \n" + "x" * 200 + "\t ", "　Я　"])
def test_title_boundaries_and_strip_before_length(client, title):
    response = client.post("/api/tasks", json={"title": title})
    assert response.status_code == 201
    assert response.json()["title"] == title.strip()


def test_max_description_and_html_like_text_are_preserved(client):
    task = client.post(
        "/api/tasks", json={"title": "<script>alert(1)</script>", "description": "x" * 5000}
    )
    assert task.status_code == 201
    assert task.json()["description"] == "x" * 5000
    assert task.json()["title"] == "<script>alert(1)</script>"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"title": ""},
        {"title": " \n\t　"},
        {"title": "x" * 201},
        {"title": None},
        {"title": 12},
        {"title": "ok", "description": None},
        {"title": "ok", "description": 12},
        {"title": "ok", "description": "x" * 5001},
        {"title": "ok", "status": None},
        {"title": "ok", "status": "unknown"},
        {"title": "ok", "id": 9},
        {"title": "ok", "extra": True},
        [],
        None,
    ],
)
def test_invalid_create_is_rejected_without_writing(client, payload):
    assert client.post("/api/tasks", json=payload).status_code == 422
    assert client.get("/api/tasks").json() == []


@pytest.mark.parametrize(
    "payload",
    [
        {"title": None},
        {"description": None},
        {"status": None},
        {"title": ""},
        {"title": "\n\t　"},
        {"title": "x" * 201},
        {"description": "x" * 5001},
        {"status": "unknown"},
        {"id": 12},
        {"extra": True},
        {"title": 3},
        {"description": []},
        [],
        None,
    ],
)
def test_invalid_patch_does_not_change_existing_task(client, payload):
    task = client.post("/api/tasks", json={"title": "Исходная", "description": "Сохранить"}).json()
    url = f"/api/tasks/{task['id']}"
    assert client.patch(url, json=payload).status_code == 422
    assert client.get(url).json() == task


@pytest.mark.parametrize("status", ["", "unknown", "TODO", "null"])
def test_unknown_filter_is_rejected(client, status):
    assert client.get("/api/tasks", params={"status": status}).status_code == 422


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_missing_task(client, method):
    kwargs = {"json": {"title": "Нет"}} if method == "patch" else {}
    response = getattr(client, method)("/api/tasks/999999", **kwargs)
    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found"}


@pytest.mark.parametrize(
    "field,value",
    [
        ("title", ""),
        ("title", "x" * 201),
        ("description", "x" * 5001),
        ("status", "unknown"),
        ("title", None),
        ("description", None),
        ("status", None),
    ],
)
def test_database_enforces_constraints(tmp_path, field, value):
    path = tmp_path / "constraints.sqlite3"
    with TestClient(create_app(path)):
        with sqlite3.connect(path) as connection:
            task = {"title": "valid", "description": "", "status": "todo", field: value}
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    "INSERT INTO tasks (title, description, status) VALUES (?, ?, ?)",
                    (task["title"], task["description"], task["status"]),
                )


def test_database_defaults_and_reopening_preserve_data(tmp_path):
    path = tmp_path / "nested" / "persistent.sqlite3"
    application = create_app(path)
    assert not path.parent.exists()
    with TestClient(application):
        with sqlite3.connect(path) as connection:
            connection.execute("INSERT INTO tasks (title) VALUES (?)", ("Сохранённая",))
    with TestClient(create_app(path)) as reopened:
        tasks = reopened.get("/api/tasks").json()
        assert len(tasks) == 1
        assert tasks[0] == {
            "id": tasks[0]["id"],
            "title": "Сохранённая",
            "description": "",
            "status": "todo",
        }


def test_explicit_path_overrides_environment_without_creation_on_factory(tmp_path, monkeypatch):
    ignored = tmp_path / "ignored" / "environment.sqlite3"
    explicit = tmp_path / "explicit" / "chosen.sqlite3"
    monkeypatch.setenv("TASK_BOARD_DB_PATH", str(ignored))
    application = create_app(explicit)
    assert application.state.db_path == explicit
    assert not explicit.parent.exists()
    assert not ignored.parent.exists()
    with TestClient(application) as test_client:
        assert test_client.get("/api/tasks").json() == []
    assert explicit.exists()
    assert not ignored.exists()


def test_environment_path_and_relative_paths_are_resolved_from_project_root(tmp_path, monkeypatch):
    project = tmp_path / "project"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.setattr("app.db.PROJECT_ROOT", project)
    monkeypatch.chdir(elsewhere)
    monkeypatch.setenv("TASK_BOARD_DB_PATH", "custom/tasks.sqlite3")
    application = create_app()
    with TestClient(application) as test_client:
        assert test_client.get("/api/tasks").json() == []
        assert test_client.get("/").status_code == 200
    assert (project / "custom/tasks.sqlite3").exists()
    monkeypatch.delenv("TASK_BOARD_DB_PATH")
    default_application = create_app()
    assert default_application.state.db_path == project / "data/task_board.sqlite3"
    assert not (project / "data").exists()


@pytest.mark.integration
def test_real_http_crud_filter_and_restart(server_factory, tmp_path):
    path = tmp_path / "real-http.sqlite3"
    with server_factory(path) as url, httpx.Client(base_url=url, trust_env=False) as client:
        created = client.post(
            "/api/tasks", json={"title": "Через HTTP", "description": "Сохранить"}
        )
        assert created.status_code == 201
        task = created.json()
        route = f"/api/tasks/{task['id']}"
        updated = client.patch(route, json={"status": "done"})
        assert updated.status_code == 200
        assert client.get("/api/tasks", params={"status": "done"}).json() == [updated.json()]
        assert client.get("/api/tasks", params={"status": "todo"}).json() == []
    with server_factory(path) as url, httpx.Client(base_url=url, trust_env=False) as client:
        assert client.get(route).json() == {**task, "status": "done"}
        assert client.delete(route).status_code == 204
        assert client.get("/api/tasks").json() == []
