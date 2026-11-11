"""Independent browser checks against the real board and an isolated database."""

import re

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def open_board(page, live_server):
    with page.expect_response(
        lambda response: response.url.endswith("/api/tasks") and response.request.method == "GET"
    ):
        page.goto(live_server)
    expect(page.locator("#save-task")).to_be_enabled()


def card_named(page, title):
    return page.get_by_test_id("task-card").filter(
        has=page.get_by_role("heading", name=title, exact=True)
    )


def create_task(page, title, description="", status="todo"):
    form = page.locator("#task-form")
    form.locator('[name="title"]').fill(title)
    form.locator('[name="description"]').fill(description)
    form.locator('[name="status"]').select_option(status)
    with page.expect_response(lambda response: response.request.method == "POST") as response:
        page.locator("#save-task").click()
    assert response.value.status == 201
    card = card_named(page, title)
    expect(card).to_be_visible()
    return card


def fail_writes(route):
    if route.request.method in {"POST", "PATCH"}:
        route.fulfill(status=503, json={"detail": "Temporary test failure"})
    else:
        route.continue_()


def test_create_edit_cancel_and_delete_confirmation(page, live_server):
    open_board(page, live_server)
    original = create_task(page, "Первая задача", "Исходное описание")
    original.locator('[data-action="edit"]').click()
    page.locator('#task-form [name="title"]').fill("Отменённое изменение")
    page.locator("#cancel-edit").click()
    expect(original).to_be_visible()
    expect(card_named(page, "Отменённое изменение")).to_have_count(0)
    expect(page.locator('#task-form [name="title"]')).to_have_value("")

    original.locator('[data-action="edit"]').click()
    page.locator('#task-form [name="title"]').fill("Изменённая задача")
    page.locator('#task-form [name="description"]').fill("Новое описание")
    with page.expect_response(lambda response: response.request.method == "PATCH") as response:
        page.locator("#save-task").click()
    assert response.value.status == 200
    edited = card_named(page, "Изменённая задача")
    expect(edited).to_contain_text("Новое описание")
    expect(original).to_have_count(0)
    expect(page.locator("#cancel-edit")).to_be_hidden()

    page.once("dialog", lambda dialog: dialog.dismiss())
    edited.locator('[data-action="delete"]').click()
    expect(edited).to_be_visible()
    page.once("dialog", lambda dialog: dialog.accept())
    edited.locator('[data-action="delete"]').click()
    expect(page.get_by_test_id("task-card")).to_have_count(0)
    page.reload()
    expect(page.get_by_test_id("task-card")).to_have_count(0)


def test_status_select_filters_three_columns_and_reload_persistence(page, live_server):
    open_board(page, live_server)
    create_task(page, "Переходы", "Сохранить описание")
    for status in ["in_progress", "done", "todo"]:
        card_named(page, "Переходы").locator('[data-action="status"]').select_option(status)
        expect(
            page.get_by_test_id(f"task-list-{status}").get_by_test_id("task-card")
        ).to_have_count(1)
        expect(card_named(page, "Переходы").locator('[data-action="status"]')).to_have_value(status)
    create_task(page, "Готовая", status="done")
    for status, expected in [("todo", 1), ("in_progress", 0), ("done", 1)]:
        page.locator("#status-filter").select_option(status)
        expect(page.get_by_test_id("task-card")).to_have_count(expected)
        for column in ["todo", "in_progress", "done"]:
            expect(page.locator(f'section[data-status="{column}"]')).to_be_visible()
    page.locator("#status-filter").select_option("todo")
    card_named(page, "Переходы").locator('[data-action="status"]').select_option("done")
    expect(page.get_by_test_id("task-card")).to_have_count(0)
    page.locator("#status-filter").select_option("")
    expect(page.get_by_test_id("task-list-done").get_by_test_id("task-card")).to_have_count(2)
    page.reload()
    expect(card_named(page, "Переходы")).to_contain_text("Сохранить описание")
    expect(card_named(page, "Переходы").locator('[data-action="status"]')).to_have_value("done")


def test_html_like_user_text_remains_text_after_reload(page, live_server):
    open_board(page, live_server)
    title = '<img src=x onerror="window.__task_xss=1">'
    description = "<script>window.__task_xss=2</script>\n<b>Обычный текст</b>"
    create_task(page, title, description)
    page.reload()
    card = card_named(page, title)
    expect(card).to_contain_text(description)
    expect(card.locator("img, script, b")).to_have_count(0)
    assert page.evaluate("window.__task_xss === undefined")


def test_failed_creation_retains_form_and_can_be_retried(page, live_server):
    open_board(page, live_server)
    page.route("**/api/tasks", fail_writes)
    form = page.locator("#task-form")
    form.locator('[name="title"]').fill("Повторить создание")
    form.locator('[name="description"]').fill("Не потерять текст")
    form.locator('[name="status"]').select_option("in_progress")
    page.locator("#save-task").click()
    expect(page.locator("#error-message")).to_be_visible()
    expect(form.locator('[name="title"]')).to_have_value("Повторить создание")
    expect(form.locator('[name="description"]')).to_have_value("Не потерять текст")
    expect(form.locator('[name="status"]')).to_have_value("in_progress")
    expect(page.get_by_test_id("task-card")).to_have_count(0)
    page.unroute("**/api/tasks", fail_writes)
    page.locator("#save-task").click()
    expect(card_named(page, "Повторить создание")).to_contain_text("Не потерять текст")


def test_failed_status_patch_retains_column_and_previous_select_value(page, live_server):
    open_board(page, live_server)
    create_task(page, "Оставить на месте")
    page.route("**/api/tasks/*", fail_writes)
    card_named(page, "Оставить на месте").locator('[data-action="status"]').select_option("done")
    expect(page.locator("#error-message")).to_be_visible()
    expect(page.get_by_test_id("task-list-todo").get_by_test_id("task-card")).to_have_count(1)
    expect(card_named(page, "Оставить на месте").locator('[data-action="status"]')).to_have_value(
        "todo"
    )
    expect(page.get_by_test_id("task-list-done").get_by_test_id("task-card")).to_have_count(0)
    page.unroute("**/api/tasks/*", fail_writes)
    card_named(page, "Оставить на месте").locator('[data-action="status"]').select_option("done")
    expect(page.get_by_test_id("task-list-done").get_by_test_id("task-card")).to_have_count(1)


def test_failed_edit_preserves_unsaved_input_and_stored_card(page, live_server):
    open_board(page, live_server)
    original = create_task(page, "Сохранённая", "Оригинал")
    original.locator('[data-action="edit"]').click()
    page.locator('#task-form [name="title"]').fill("Несохранённая")
    page.locator('#task-form [name="description"]').fill("Новый текст")
    page.route("**/api/tasks/*", fail_writes)
    page.locator("#save-task").click()
    expect(page.locator("#error-message")).to_be_visible()
    expect(page.locator('#task-form [name="title"]')).to_have_value("Несохранённая")
    expect(page.locator('#task-form [name="description"]')).to_have_value("Новый текст")
    expect(original).to_contain_text("Оригинал")
    expect(card_named(page, "Несохранённая")).to_have_count(0)
    tasks = page.request.get(f"{live_server}/api/tasks").json()
    assert [(task["title"], task["description"]) for task in tasks] == [("Сохранённая", "Оригинал")]


def test_loading_empty_state_and_pending_submission_blocks_duplicates(page, live_server):
    held_reads = []

    def hold_initial_read(route):
        held_reads.append(route)

    page.route("**/api/tasks", hold_initial_read)
    page.goto(live_server, wait_until="domcontentloaded")
    expect(page.locator("#feedback")).to_contain_text(re.compile("загруз", re.IGNORECASE))
    assert len(held_reads) == 1
    held_reads[0].fulfill(status=200, json=[])
    page.unroute("**/api/tasks", hold_initial_read)
    expect(page.locator("#save-task")).to_be_enabled()
    expect(page.get_by_test_id("task-card")).to_have_count(0)
    for status in ["todo", "in_progress", "done"]:
        expect(page.get_by_test_id(f"task-list-{status}")).to_contain_text(
            re.compile("задач", re.IGNORECASE)
        )

    held_writes = []

    def hold_write(route):
        if route.request.method == "POST":
            held_writes.append(route)
        else:
            route.continue_()

    page.route("**/api/tasks", hold_write)
    page.locator('#task-form [name="title"]').fill("Один запрос")
    page.locator("#save-task").click()
    expect(page.locator("#save-task")).to_be_disabled()
    assert len(held_writes) == 1
    created = page.request.post(f"{live_server}/api/tasks", data={"title": "Один запрос"})
    assert created.status == 201
    held_writes[0].fulfill(response=created)
    expect(card_named(page, "Один запрос")).to_be_visible()
    expect(page.locator("#save-task")).to_be_enabled()
    assert len(held_writes) == 1


def test_mobile_keyboard_submission_and_whitespace_validation(page, live_server):
    page.set_viewport_size({"width": 375, "height": 812})
    open_board(page, live_server)
    title = page.locator('#task-form [name="title"]')
    title.fill("   ")
    page.locator("#save-task").click()
    expect(page.locator("#error-message")).to_be_visible()
    expect(page.get_by_test_id("task-card")).to_have_count(0)
    title.fill("Задача с клавиатуры")
    title.press("Enter")
    expect(card_named(page, "Задача с клавиатуры")).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    for status in ["todo", "in_progress", "done"]:
        expect(page.locator(f'section[data-status="{status}"]')).to_be_visible()
