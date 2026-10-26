# Инженерные правила

## Стек

```
python      3.12+
backend     FastAPI, uvicorn, SQLAlchemy 2, Alembic, httpx, pydantic v2
auth        argon2-cffi, pyotp, itsdangerous (сессии)
frontend    Vue 3, Vite, Naive UI, pinia, vue-i18n, vue-router
тесты       pytest, pytest-asyncio, respx (моки HTTP), testcontainers (docker)
линтеры     ruff, mypy (строгий для core), eslint + prettier
```

## Структура backend

```
app/
  main.py            сборка приложения, роутеры, lifespan
  config.py          настройки из env и config.yaml
  api/               v1: services, providers, users, roles, settings, events
  core/
    registry.py      CRUD сервисов, приоритет база/метки
    reconcile.py     сверка состояния
    actions.py       конвейер изменений
    operations.py    очередь и статусы операций
  providers/
    base.py          интерфейс провайдера
    docker_local.py
    docker_remote.py
    http_provider.py
  ingress/
    caddy.py         генерация, validate, load, rollback
  auth/
    sessions.py, tokens.py, rbac.py, totp.py
  jobs/
    runner.py, rules.py, notify.py
  db/
    models.py, session.py, migrations/
  notify/
    telegram.py
```

## Правила кода

```
типизация обязательна в core и providers
никаких «голых» except — только конкретные исключения
все внешние вызовы с таймаутом
логи структурированные: JSON с полями ts, level, event, объект
секреты никогда не попадают в логи и в ответы API
ошибки API — только через общий обработчик, без стеков наружу
```

## Логи

```
stdout в JSON
поля: ts, level, logger, event, service_id, operation_id, user_id, duration_ms
уровни: debug для разработки, info по умолчанию
маскирование: значения секретов заменяются на ****
```

## Тесты

```
unit          логика без Docker: rbac, registry, политики, парсеры
integration   провайдер против настоящего Docker (testcontainers)
api           httpx AsyncClient, без сети
e2e           поднятый hub + один тестовый контейнер, сценарий:
              добавить → проверить → обновить → удалить
```

Минимальные требования к PR:

```
покрытие core и auth ≥ 70%
есть тест на каждое новое разрешение
есть тест на откат в actions
```

## Git

```
ветки      main защищена; работа в feature/<короткое-имя>
коммиты    conventional commits: feat:, fix:, docs:, chore:
релизы     тег v1.0.0, changelog из коммитов
PR         описание, что меняется и как проверено; CI зелёный
```

## CI (GitServatory Actions)

```
lint      ruff, mypy, eslint
test      pytest, сборка фронта
build     docker buildx, amd64 + arm64
release   по тегу: push в ghcr, прикрепить changelog
```

## Производительность

```
старт hub       < 2 с до /health
список 500 сервисов  < 300 мс
события Docker  обработка пачками, не по одному запросу
база             WAL, индексы по state/provider_id
```

## Совместимость

```
Docker Engine   24+, API v1.43+
Caddy           2.7+
SQLite          3.40+
браузеры        последние Chrome, Firefox, Safari, мобильные
```

## Документация в репозитории

```
docs/quickstart.md
docs/api.md            (генерируется из openapi.yaml)
docs/labels.md
docs/roles.md
docs/security.md
docs/troubleshooting.md
```
