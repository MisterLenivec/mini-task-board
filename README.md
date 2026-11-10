# Mini Task Board

Личный учебный проект: небольшая локальная доска задач и практика агентной разработки в Codex.

## Текущее состояние

Этап 1: локальная инициализация. Есть документация, настройки инструментов, роли агентов и каркас каталогов. Приложение, API, интерфейс и тестовые сценарии ещё не реализованы. Зависимости не установлены. Удалённый репозиторий и GitHub Actions ещё не настроены.

## Согласованный MVP

- CRUD задач: название, описание, статус.
- Статусы `todo`, `in_progress`, `done`; три колонки.
- Фильтр статуса, выпадающий список и drag-and-drop.
- SQLite для сохранения между запусками.
- Python 3.12, FastAPI, SQLAlchemy 2, Pydantic v2, HTML/CSS/vanilla JavaScript.
- pytest, Ruff, pytest-playwright и Chromium для проверок.

## Документация

- [Архитектура](docs/architecture.md)
- [Контракт API](docs/api-contract.md)
- [Процесс разработки и контрольные точки](docs/development-workflow.md)
- [Инструкции агентам](AGENTS.md)

## Запуск и проверки

На этапе 1 приложение не запускается. `.venv` и `requirements.txt` появятся в `feature/project-foundation` после разрешения следующих этапов.

Планируемый запуск из корня проекта после реализации и установки зависимостей:

```bash
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Планируемый адрес для браузера Windows: http://localhost:8000. Доступность из Windows будет проверена при приёмке.

Будущие команды проверок:

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m pytest
```

До реализации и установки инструментов эти команды не являются выполненными проверками.
