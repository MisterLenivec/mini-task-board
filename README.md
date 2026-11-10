# Mini Task Board

Личный учебный проект: небольшая локальная доска задач и практика агентной разработки в Codex.

## Текущее состояние

Разработка в dev через feature-ветки. Личный GitHub подключён; main сохраняет начальную инициализацию до отдельного разрешения выпуска. Foundation добавляет запускаемый каркас, реальные HTTP-проверки и CI. API с SQLite реализован; интерфейс добавляется в feature/board-ui, перетаскивание — следующей feature.

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

Из корня проекта подготовьте окружение (первый запуск):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Запуск из корня проекта:

```bash
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Адрес для браузера Windows: http://localhost:8000.

Команды проверок:

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
PLAYWRIGHT_BROWSERS_PATH=0 .venv/bin/python -m pytest
```

API, UI и браузерные сценарии проверяются по мере их реализации. Неприменимые проверки не считаются выполненными.

## API и данные

Документация API доступна на http://localhost:8000/docs. API использует /api/tasks. SQLite-файл — data/task_board.sqlite3 относительно корня проекта. Переменная TASK_BOARD_DB_PATH задаёт альтернативный путь. Перезапуск сохраняет данные. Не удаляйте файл БД ради обновления приложения. Тесты используют только временные SQLite-файлы.

Для браузерных тестов один раз скачайте Chromium внутри .venv:

```bash
PLAYWRIGHT_BROWSERS_PATH=0 .venv/bin/python -m playwright install chromium
```

CI устанавливает браузер и Linux-зависимости автоматически. Локальным проверкам нужен доступ к loopback-сокетам; в ограниченном sandbox Codex может потребоваться разрешённый запуск проверок вне изоляции.
