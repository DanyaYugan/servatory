# Servatory

Панель управления домашними сервисами: показывает контейнеры на локальном
Docker-хосте, позволяет устанавливать, обновлять и удалять их из браузера.

Версия: **0.2.0-beta**.
Правила версий — [docs/plan/versioning.md](docs/plan/versioning.md).

## Что уже есть

```
docs/          архитектура, решения, спецификации, план 1.0, словарь,
               user-guide.md и чек-лист приёмки
assets/brand/  логотип и фирменный стиль
assets/        схема архитектуры (svg, png)
backend/       FastAPI: /health, /ready, /meta, /api/v1/containers
frontend/      Vue 3 + Vite: верхняя панель, обзор, сервис, установка, настройки
deploy/        Dockerfile, compose, systemd, install.sh
```

## Что уже работает

```
вход, сессии, роли и пользователи
обзор, карточки, группы, поиск
установка из формы и YAML, обновление, действия
бэкапы томов и восстановление
журнал действий, проверки по HTTP, логи
TLS через Caddy из настроек
```

API защищено сессией, ролями и CSRF; список берётся через сокет Docker,
контейнеру нужна группа docker (`DOCKER_GID` в `.env`,
узнать: `stat -c '%g' /var/run/docker.sock`).

## Быстрый старт (после установки зависимостей)

```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
python -m app.cli          # порт и логин берутся из config.toml
```

```bash
cd frontend
npm install
npm run dev
```

```bash
curl http://127.0.0.1:8090/health
curl http://127.0.0.1:8090/api/v1/meta
```

## Установка из Docker Hub

```bash
docker run -d --name servatory --restart unless-stopped \
  -p 8090:8090 \
  -e SERVATORY_PORT=8090 \
  -v servatory-data:/data \
  -v servatory-backups:/backups \
  -v /var/run/docker.sock:/var/run/docker.sock \
  --group-add "$(stat -c '%g' /var/run/docker.sock)" \
  danyayugan/servatory:0.2.0-beta
```

Или через compose, когда репозиторий опубликован:

```bash
mkdir servatory && cd servatory
curl -fsSLO https://raw.githubusercontent.com/danyayugan/servatory/v0.2.0-beta/deploy/docker/compose.release.yml
curl -fsSL https://raw.githubusercontent.com/danyayugan/servatory/v0.2.0-beta/deploy/docker/.env.release.example -o .env
nano .env
docker compose up -d
```

## Запуск из исходников

```bash
cd deploy/docker
cp .env.example .env      # порт, домен, каталог проекта
docker compose up -d --build
```

Панель: `http://<host>:8090`. Установка и TLS — в [docs/admin-guide.md](docs/admin-guide.md).

Образ для GHCR собирается workflow `.github/workflows/release.yml`:

```bash
git tag v0.2.0-beta
git push origin v0.2.0-beta
# ghcr.io/<owner>/servatory:0.2.0-beta
```


## Настройки

Все параметры — в `config.toml` в каталоге данных (`/data/config.toml`
в контейнере, `/var/lib/servatory/config.toml` при нативной установке).
Файл создаётся при первом старте.

```toml
[server]
host = "0.0.0.0"
port = 8090

[auth]
login = "admin"
password = "admin"
role = "superadmin"     # главный администратор

[ui]
language = "ru"
theme = "dark"

[logging]
level = "info"

[features]
demo = false
```

Переменные окружения перекрывают файл: `SERVATORY_PORT`, `SERVATORY_HOST`,
`SERVATORY_ADMIN_LOGIN`, `SERVATORY_ADMIN_PASSWORD`, `SERVATORY_DATA`,
`SERVATORY_LOG_LEVEL`, `SERVATORY_DEMO`.

Пример — [deploy/docker/config.example.toml](deploy/docker/config.example.toml).
Пароль первого администратора берётся отсюда только при пустой базе.
После правки файла панель нужно перезапустить.

## Состав 1.0

Подробно — [docs/plan/v1.0.md](docs/plan/v1.0.md). Коротко:

```
ядро + веб, один администратор
несколько Docker-хостов: локальный сокет и удалённый по TLS
главная: все сервисы, группы, порядок
установка, удаление, обновление с откатом
бэкапы: создание и хранение (без восстановления)
состояние контейнера: работает или нет
```

Чего нет в 1.0: бот, роли, домены, метрики, логи,
SSE, перетаскивание, английский, HTTP-проверки, стеки compose, Proxmox.

Пользовательское описание всех функций — [docs/user-guide.md](docs/user-guide.md).

## Структура

```
servatory/
├── backend/
│   ├── app/
│   │   ├── main.py        приложение FastAPI
│   │   ├── config.py      настройки из окружения
│   │   └── version.py     версия продукта
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   ├── index.html
│   └── package.json
├── deploy/
│   ├── docker/            Dockerfile, compose, .env.example
│   ├── systemd/           сервис и уведомление о падении
│   └── install.sh
├── docs/
│   ├── architecture.md
│   ├── decisions.md
│   ├── glossary.md
│   ├── roadmap.md
│   ├── spec/              контракты: данные, API, роли, вход, бэкапы
│   ├── plan/              план 1.0, версионирование, задачи, риски
│   ├── environment/       текущий стенд и переход
│   └── handoff/           заметки для следующей сессии
├── assets/
│   ├── brand/             логотип, цвета, правила
│   └── architecture.*     схема
└── .github/workflows/ci.yml
```

## Лицензия

Apache License 2.0 — см. [LICENSE](LICENSE) и [NOTICE](NOTICE).

## Статус

```
0.1.0-alpha.1   каркас: /health, конфиг, версия, сборка, CI
далее           провайдер Docker, список контейнеров, установка и удаление
```
