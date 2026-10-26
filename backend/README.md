# Servatory backend

API на FastAPI. Запуск для разработки:

```bash
python -m venv .venv
. .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m app.cli           # порт и логин из config.toml
```

Проверки:

```bash
pytest
ruff check app tests
```

Основные модули:

```
app/main.py        приложение, сессии, статика
app/config.py      чтение config.toml и переменных окружения
app/db.py          SQLite: группы, ссылки, сессии
app/providers/     Docker API: список, действия, установка, обновление
app/backups.py     копии томов и восстановление
app/images.py      поиск образов на Docker Hub
app/api/           HTTP-эндпоинты
```
