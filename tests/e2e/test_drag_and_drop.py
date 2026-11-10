"""Native Chromium drag-and-drop behavior against the real task API."""

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def open_seeded_board(page, live_server, status="todo"):
    response = page.request.post(
        f"{live_server}/api/tasks",
        data={"title": "Переместить карточку", "description": "Сохранить детали", "status": status},
    )
    assert response.status == 201
    task = response.json()
    with page.expect_response(
        lambda response: response.url.endswith("/api/tasks") and response.request.method == "GET"
    ):
        page.goto(live_server)
    expect(page.locator("#save-task")).to_be_enabled()
    expect(page.locator(f'article[data-task-id="{task["id"]}"]')).to_be_visible()
    return task


def task_card(page, task):
    return page.locator(f'article[data-task-id="{task["id"]}"]')


def column(page, status):
    return page.locator(f'section[data-status="{status}"]')


def expect_task_in_column(page, task, status):
    expect(column(page, status).locator(f'article[data-task-id="{task["id"]}"]')).to_be_visible()
    expect(task_card(page, task).locator('[data-action="status"]')).to_have_value(status)


def test_native_drag_moves_forward_backward_and_persists_after_reload(page, live_server):
    task = open_seeded_board(page, live_server)
    for status in ["in_progress", "done", "todo"]:
        task_card(page, task).drag_to(column(page, status), source_position={"x": 20, "y": 20})
        expect_task_in_column(page, task, status)
        stored = page.request.get(f"{live_server}/api/tasks/{task['id']}").json()
        assert stored == {**task, "status": status}
    page.reload()
    expect_task_in_column(page, task, "todo")
    expect(task_card(page, task)).to_contain_text("Сохранить детали")


def test_dragging_out_of_active_filter_removes_card_and_preserves_server_update(page, live_server):
    task = open_seeded_board(page, live_server)
    with page.expect_response(lambda response: "/api/tasks?status=todo" in response.url):
        page.locator("#status-filter").select_option("todo")
    expect(page.locator("#save-task")).to_be_enabled()
    task_card(page, task).drag_to(column(page, "done"), source_position={"x": 20, "y": 20})
    expect(task_card(page, task)).to_have_count(0)
    for status in ["todo", "in_progress", "done"]:
        expect(column(page, status)).to_be_visible()
    assert page.request.get(f"{live_server}/api/tasks/{task['id']}").json()["status"] == "done"
    page.locator("#status-filter").select_option("")
    expect_task_in_column(page, task, "done")


def test_rejected_drag_keeps_confirmed_position_and_retry_succeeds(page, live_server):
    task = open_seeded_board(page, live_server)

    def reject_patch(route):
        if route.request.method == "PATCH":
            route.fulfill(status=503, json={"detail": "Temporary failure"})
        else:
            route.continue_()

    page.route("**/api/tasks/*", reject_patch)
    task_card(page, task).drag_to(column(page, "done"), source_position={"x": 20, "y": 20})
    expect(page.locator("#error-message")).to_be_visible()
    expect_task_in_column(page, task, "todo")
    assert page.request.get(f"{live_server}/api/tasks/{task['id']}").json() == task
    page.unroute("**/api/tasks/*", reject_patch)
    task_card(page, task).drag_to(column(page, "done"), source_position={"x": 20, "y": 20})
    expect_task_in_column(page, task, "done")
    assert page.request.get(f"{live_server}/api/tasks/{task['id']}").json()["status"] == "done"


def test_pending_drop_retains_old_state_and_blocks_duplicate_drag(page, live_server):
    task = open_seeded_board(page, live_server)
    held_patches = []

    def hold_patch(route):
        if route.request.method == "PATCH":
            held_patches.append(route)
        else:
            route.continue_()

    page.route("**/api/tasks/*", hold_patch)
    task_card(page, task).drag_to(column(page, "done"), source_position={"x": 20, "y": 20})
    expect(page.locator("#save-task")).to_be_disabled()
    expect_task_in_column(page, task, "todo")
    expect(task_card(page, task).locator('[data-action="status"]')).to_be_disabled()
    assert page.request.get(f"{live_server}/api/tasks/{task['id']}").json() == task
    task_card(page, task).drag_to(column(page, "in_progress"), source_position={"x": 20, "y": 20})
    assert len(held_patches) == 1
    response = page.request.patch(f"{live_server}/api/tasks/{task['id']}", data={"status": "done"})
    assert response.status == 200
    held_patches[0].fulfill(response=response)
    expect_task_in_column(page, task, "done")
    expect(page.locator("#save-task")).to_be_enabled()
    assert len(held_patches) == 1


def test_drop_in_same_column_does_not_write_or_lose_task(page, live_server):
    task = open_seeded_board(page, live_server, status="in_progress")
    patches = []
    page.on(
        "request", lambda request: patches.append(request) if request.method == "PATCH" else None
    )
    task_card(page, task).drag_to(column(page, "in_progress"), source_position={"x": 20, "y": 20})
    expect_task_in_column(page, task, "in_progress")
    assert patches == []
    assert page.request.get(f"{live_server}/api/tasks/{task['id']}").json() == task
    expect(page.locator("#save-task")).to_be_enabled()


def test_external_drag_payload_cannot_move_an_existing_task(page, live_server):
    task = open_seeded_board(page, live_server)
    transfer = page.evaluate_handle(
        "id => { const data = new DataTransfer(); data.setData('text/plain', String(id)); "
        "return data; }",
        task["id"],
    )
    target = column(page, "done")
    target.dispatch_event("dragover", {"dataTransfer": transfer})
    target.dispatch_event("drop", {"dataTransfer": transfer})
    expect_task_in_column(page, task, "todo")
    assert page.request.get(f"{live_server}/api/tasks/{task['id']}").json() == task
    task_card(page, task).drag_to(target, source_position={"x": 20, "y": 20})
    expect_task_in_column(page, task, "done")


def test_escape_cancels_native_drag_and_leaves_board_usable(page, live_server):
    task = open_seeded_board(page, live_server)
    card = task_card(page, task)
    card.scroll_into_view_if_needed()
    source = card.bounding_box()
    target = column(page, "done").bounding_box()
    assert source is not None and target is not None
    page.mouse.move(source["x"] + 20, source["y"] + 20)
    page.mouse.down()
    page.mouse.move(source["x"] + 40, source["y"] + 25, steps=5)
    page.mouse.move(target["x"] + 30, target["y"] + 30, steps=10)
    expect(page.locator("#board")).to_have_attribute("data-dragging", "true")
    page.keyboard.press("Escape")
    page.mouse.up()
    expect(page.locator(".is-dragging, .is-drop-target")).to_have_count(0)
    expect(page.locator("#board")).not_to_have_attribute("data-dragging", "true")
    expect_task_in_column(page, task, "todo")
    assert page.request.get(f"{live_server}/api/tasks/{task['id']}").json() == task
    card.locator('[data-action="status"]').select_option("done")
    expect_task_in_column(page, task, "done")
