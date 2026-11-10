"use strict";

const statusLabels = {
  todo: "К выполнению",
  in_progress: "В работе",
  done: "Готово",
};
const form = document.getElementById("task-form");
const titleInput = document.getElementById("task-title");
const descriptionInput = document.getElementById("task-description");
const statusInput = document.getElementById("task-status");
const saveButton = document.getElementById("save-task");
const cancelButton = document.getElementById("cancel-edit");
const filter = document.getElementById("status-filter");
const refreshButton = document.getElementById("refresh-board");
const feedback = document.getElementById("feedback");
const errorMessage = document.getElementById("error-message");
const board = document.getElementById("board");
const boardHeading = document.getElementById("board-heading");
const cardTemplate = document.getElementById("task-card-template");
let tasks = [];
let editingId = null;
let activeFilter = "";
let busy = false;

function clearMessages() {
  feedback.textContent = "";
  errorMessage.textContent = "";
  errorMessage.hidden = true;
}

function showError(message) {
  feedback.textContent = "";
  errorMessage.textContent = message;
  errorMessage.hidden = false;
}

function setBusy(value) {
  busy = value;
  form.querySelector("fieldset").disabled = value;
  filter.disabled = value;
  refreshButton.disabled = value;
  board.setAttribute("aria-busy", String(value));
  board.querySelectorAll("button, select").forEach((control) => {
    control.disabled = value;
  });
}

function readableError(status) {
  if (status === 404) {
    return "Задача больше не найдена. Нажмите «Обновить», чтобы получить актуальный список.";
  }
  if (status === 422) {
    return "Проверьте данные: название — от 1 до 200 символов, описание — до 5000, статус — из списка.";
  }
  return "Сервер не смог выполнить действие. Попробуйте ещё раз.";
}

async function apiRequest(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      ...options,
      headers: { "Content-Type": "application/json", ...options.headers },
    });
  } catch {
    throw new Error("Не удалось связаться с сервером. Проверьте соединение и обновите доску перед повтором действия.");
  }
  if (!response.ok) {
    throw new Error(readableError(response.status));
  }
  return response.status === 204 ? null : response.json();
}

function resetForm() {
  editingId = null;
  form.reset();
  document.getElementById("form-heading").textContent = "Новая задача";
  saveButton.textContent = "Добавить задачу";
  cancelButton.hidden = true;
}

function beginEdit(task) {
  if (busy) return;
  clearMessages();
  editingId = task.id;
  titleInput.value = task.title;
  descriptionInput.value = task.description;
  statusInput.value = task.status;
  document.getElementById("form-heading").textContent = "Редактирование задачи";
  saveButton.textContent = "Сохранить изменения";
  cancelButton.hidden = false;
  titleInput.focus();
}

function focusTaskControl(taskId, action) {
  const control = board.querySelector(`[data-task-id="${taskId}"] [data-action="${action}"]`);
  (control || boardHeading).focus();
}

function makeCard(task) {
  const item = cardTemplate.content.firstElementChild.cloneNode(true);
  const card = item.querySelector("article");
  card.dataset.taskId = String(task.id);
  item.querySelector(".task-title").textContent = task.title;
  const description = item.querySelector(".task-description");
  description.textContent = task.description;
  description.hidden = task.description === "";

  const statusSelect = item.querySelector('[data-action="status"]');
  statusSelect.id = `task-status-${task.id}`;
  statusSelect.setAttribute("aria-label", `Статус задачи ${task.title}`);
  const statusLabel = item.querySelector(".task-status-label");
  statusLabel.htmlFor = statusSelect.id;
  statusLabel.textContent = `Статус задачи ${task.title}`;
  Object.entries(statusLabels).forEach(([value, label]) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    statusSelect.append(option);
  });
  statusSelect.value = task.status;
  statusSelect.addEventListener("change", () => {
    const nextStatus = statusSelect.value;
    // Keep the confirmed state visible until the server accepts the PATCH.
    statusSelect.value = task.status;
    if (busy || nextStatus === task.status) return;
    mutateTask(
      () => apiRequest(`/api/tasks/${task.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status: nextStatus }),
      }),
      "Статус задачи обновлён.",
      () => focusTaskControl(task.id, "status"),
    );
  });
  item.querySelector('[data-action="edit"]').addEventListener("click", () => beginEdit(task));
  item.querySelector('[data-action="delete"]').addEventListener("click", () => {
    if (busy || !window.confirm(`Удалить задачу «${task.title}»? Это действие нельзя отменить.`)) return;
    mutateTask(
      () => apiRequest(`/api/tasks/${task.id}`, { method: "DELETE" }),
      "Задача удалена.",
      () => boardHeading.focus(),
      () => { if (editingId === task.id) resetForm(); },
    );
  });
  return item;
}

function renderTasks() {
  Object.keys(statusLabels).forEach((status) => {
    const list = board.querySelector(`[data-testid="task-list-${status}"]`);
    list.replaceChildren();
    const columnTasks = tasks.filter((task) => task.status === status);
    board.querySelector(`[data-count="${status}"]`).textContent = String(columnTasks.length);
    if (columnTasks.length === 0) {
      const empty = document.createElement("li");
      empty.className = "empty-state";
      empty.textContent = "Здесь пока нет задач.";
      list.append(empty);
    } else {
      columnTasks.forEach((task) => list.append(makeCard(task)));
    }
  });
  document.getElementById("task-count").textContent = `Показано: ${tasks.length}`;
}

async function fetchTasks(selectedFilter = activeFilter) {
  const query = selectedFilter ? `?status=${encodeURIComponent(selectedFilter)}` : "";
  const freshTasks = await apiRequest(`/api/tasks${query}`);
  tasks = freshTasks;
  activeFilter = selectedFilter;
  renderTasks();
}

async function reloadBoard(selectedFilter = activeFilter) {
  if (busy) return;
  clearMessages();
  setBusy(true);
  feedback.textContent = "Загрузка задач…";
  try {
    await fetchTasks(selectedFilter);
    feedback.textContent = "";
  } catch (error) {
    filter.value = activeFilter;
    showError(error.message);
  } finally {
    setBusy(false);
  }
}

async function mutateTask(request, successMessage, focusAfter, onSaved = () => {}) {
  if (busy) return;
  clearMessages();
  setBusy(true);
  feedback.textContent = "Сохранение…";
  let saved = false;
  try {
    await request();
    saved = true;
    onSaved();
    try {
      await fetchTasks();
      feedback.textContent = successMessage;
    } catch {
      showError("Изменение сохранено, но не удалось обновить доску. Нажмите «Обновить».");
    }
  } catch (error) {
    showError(error.message);
  } finally {
    setBusy(false);
    if (saved && focusAfter) focusAfter();
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  if (busy) return;
  if (!titleInput.value.trim()) {
    showError("Введите название задачи.");
    titleInput.focus();
    return;
  }
  const taskId = editingId;
  const payload = {
    title: titleInput.value.trim(),
    description: descriptionInput.value,
    status: statusInput.value,
  };
  mutateTask(
    () => apiRequest(taskId === null ? "/api/tasks" : `/api/tasks/${taskId}`, {
      method: taskId === null ? "POST" : "PATCH",
      body: JSON.stringify(payload),
    }),
    taskId === null ? "Задача добавлена." : "Изменения сохранены.",
    () => titleInput.focus(),
    resetForm,
  );
});
cancelButton.addEventListener("click", () => {
  if (busy) return;
  clearMessages();
  resetForm();
  titleInput.focus();
});
filter.addEventListener("change", () => reloadBoard(filter.value));
refreshButton.addEventListener("click", () => reloadBoard());
renderTasks();
reloadBoard();
