"""Independent contract checks for adversarial input and database invariants."""

import sqlite3

import httpx
import pytest


@pytest.mark.parametrize("field", ["title", "description", "status"])
def test_null_patch_rejects_entire_update_without_losing_existing_data(client, field):
    original = client.post(
        "/api/tasks", json={"title": "Keep me", "description": "Original", "status": "done"}
    ).json()
    payload = {"description": "Should not be saved", field: None}
    response = client.patch(f"/api/tasks/{original['id']}", json=payload)
    assert response.status_code == 422
    assert client.get(f"/api/tasks/{original['id']}").json() == original


@pytest.mark.parametrize("extra", [{"id": 999}, {"unexpected": "ignored?"}])
def test_unknown_fields_are_rejected_on_create_and_update(client, extra):
    response = client.post("/api/tasks", json={"title": "Attempt", **extra})
    assert response.status_code == 422
    assert client.get("/api/tasks").json() == []

    original = client.post("/api/tasks", json={"title": "Original"}).json()
    response = client.patch(f"/api/tasks/{original['id']}", json={"title": "Not saved", **extra})
    assert response.status_code == 422
    assert client.get(f"/api/tasks/{original['id']}").json() == original


@pytest.mark.parametrize("title", ["x", "Я" * 200, "🤖" * 200])
def test_title_length_is_validated_after_trimming_on_create_and_update(client, title):
    padded = f"\t \n{title}\n \t"
    response = client.post("/api/tasks", json={"title": padded})
    assert response.status_code == 201
    original = response.json()
    assert original["title"] == title

    updated = client.patch(f"/api/tasks/{original['id']}", json={"title": padded})
    assert updated.status_code == 200
    assert updated.json()["title"] == title


@pytest.mark.parametrize("title", ["", "\t \n", "\u2003\u00a0", "Я" * 201])
def test_invalid_title_cannot_create_or_partially_modify_a_task(client, title):
    assert client.post("/api/tasks", json={"title": title}).status_code == 422
    original = client.post("/api/tasks", json={"title": "Keep", "status": "done"}).json()
    response = client.patch(f"/api/tasks/{original['id']}", json={"title": title, "status": "todo"})
    assert response.status_code == 422
    assert client.get(f"/api/tasks/{original['id']}").json() == original


def test_description_preserves_text_at_limit_and_rejects_atomic_overflow(client):
    description = " \n<b>обычный текст</b>\n".ljust(5000, "Я")
    response = client.post("/api/tasks", json={"title": "Original", "description": description})
    assert response.status_code == 201
    original = response.json()
    assert original["description"] == description
    overflow = description + "x"
    assert (
        client.post("/api/tasks", json={"title": "Overflow", "description": overflow}).status_code
        == 422
    )
    response = client.patch(
        f"/api/tasks/{original['id']}", json={"title": "Not saved", "description": overflow}
    )
    assert response.status_code == 422
    assert client.get(f"/api/tasks/{original['id']}").json() == original
    assert client.get("/api/tasks").json() == [original]


@pytest.mark.parametrize("status", ["", "TODO", "archived", "todo,done"])
def test_invalid_status_filter_is_an_error_instead_of_unfiltered_results(client, status):
    original = client.post("/api/tasks", json={"title": "Existing"}).json()
    assert client.get("/api/tasks", params={"status": status}).status_code == 422
    assert client.get("/api/tasks").json() == [original]


@pytest.mark.parametrize("source", ["todo", "in_progress", "done"])
@pytest.mark.parametrize("target", ["todo", "in_progress", "done"])
def test_status_transitions_including_reverse_and_same_status_are_allowed(client, source, target):
    original = client.post(
        "/api/tasks", json={"title": "Transition", "description": "Preserve", "status": source}
    ).json()
    response = client.patch(f"/api/tasks/{original['id']}", json={"status": target})
    assert response.status_code == 200
    assert response.json() == {**original, "status": target}
    assert client.get("/api/tasks", params={"status": target}).json() == [response.json()]
    if target != source:
        assert client.get("/api/tasks", params={"status": source}).json() == []


def test_unknown_task_id_has_consistent_errors_and_does_not_modify_existing_task(client):
    original = client.post("/api/tasks", json={"title": "Existing"}).json()
    missing_url = f"/api/tasks/{original['id'] + 1}"
    responses = [
        client.get(missing_url),
        client.patch(missing_url, json={"title": "Not saved"}),
        client.delete(missing_url),
    ]
    for response in responses:
        assert response.status_code == 404
        assert response.json() == {"detail": "Task not found"}
    assert client.get("/api/tasks").json() == [original]


@pytest.mark.integration
def test_database_constraints_reject_invalid_rows_without_api_validation(server_factory, tmp_path):
    database = tmp_path / "independent.sqlite3"
    with server_factory(database) as base_url:
        with httpx.Client(base_url=base_url, trust_env=False) as live_client:
            response = live_client.post("/api/tasks", json={"title": "Valid row"})
            assert response.status_code == 201
            original = response.json()
            with sqlite3.connect(database) as connection:
                invalid_rows = [
                    ("", "", "todo"),
                    ("x" * 201, "", "todo"),
                    ("Title", "x" * 5001, "todo"),
                    ("Title", "", "archived"),
                    (None, "", "todo"),
                    ("Title", None, "todo"),
                    ("Title", "", None),
                ]
                for row in invalid_rows:
                    with pytest.raises(sqlite3.IntegrityError):
                        connection.execute(
                            "INSERT INTO tasks (title, description, status) VALUES (?, ?, ?)", row
                        )
                    connection.rollback()
            assert live_client.get("/api/tasks").json() == [original]
