# Установка и первый запуск

## Контейнер (основной путь)

```bash
docker run -d --name hub \
  -p 8080:8080 \
  -v hub-data:/data \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /opt/homelab:/opt/homelab \
  -e HUB_TLS_MODE=none \
  ghcr.io/<owner>/hub:latest
```

Или compose (см. `templates/docker-compose.yml`):

```bash
git clone https://github.com/<owner>/hub.git
cd hub/deploy/docker
cp .env.example .env      # поправить домен и почту
docker compose up -d
```

После старта: `http://<host>:8080` → мастер.

### Монтирования

```
/data                    обязательный том состояния
/var/run/docker.sock     управление контейнерами (или socket-proxy)
/opt/homelab             исходный каталог проекта (если сервисы используют ./ пути)
```

Монтирование проекта **по тому же абсолютному пути**, что на хосте, —
иначе относительные пути в compose-файлах сервисов не найдут каталоги.

## Нативно

```bash
git clone https://github.com/<owner>/hub.git /opt/hub
cd /opt/hub
sudo ./deploy/install.sh          # создаёт пользователя, каталоги, venv, юнит
sudo systemctl enable --now hub
```

`install.sh` делает:

```
проверяет python3, docker, systemd
создаёт /etc/hub, /var/lib/hub (или /data)
создаёт пользователя hub, добавляет в группу docker
создаёт venv, ставит зависимости
копирует юнит, включает и запускает
печатает адрес и подсказку про мастер
```

## Переменные окружения

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `HUB_PORT` | 8080 | порт API и веба |
| `HUB_DATA` | `/data` | каталог состояния |
| `HUB_TLS_MODE` | `none` | managed / external / labels / none |
| `HUB_DOMAIN` | — | домен для managed Caddy |
| `HUB_ACME_EMAIL` | — | почта для сертификатов |
| `HUB_LOG_LEVEL` | `info` | debug / info / warning |
| `HUB_DEMO` | `0` | демо-режим без Docker |
| `HUB_SECRET_KEY_FILE` | `/data/key` | ключ шифрования |

## Каталоги

```
/data/config.yaml     bootstrap (создаётся мастером)
/data/hub.db          база
/data/key             ключ, 600
/data/backups/        копии
/data/cache/          кеш версий
/data/logs/           файлы логов (если не stdout)
```

## Мастер

```
1 проверка окружения
2 режим TLS и домен
3 администратор
4 Telegram (пропустить можно)
5 найденные сервисы
6 готово
```

Результат мастера: `config.yaml`, запись админа в базе, включённые провайдеры.

## Обновление hub

```
контейнер:  docker compose pull && docker compose up -d
нативно:    git pull && ./deploy/install.sh --upgrade
```

Перед обновлением:

```
копия hub.db в /data/backups/pre-upgrade-<version>.db
миграции Alembic при старте
при несовместимости — отказ и инструкция вернуться на прошлый тег
```

## Удаление

```
контейнер:  docker compose down; том /data удаляется отдельно
нативно:    ./deploy/install.sh --uninstall; /data остаётся
```

## Требования

```
Linux (amd64 или arm64)
Docker 24+ для управления контейнерами
2 ГБ RAM минимум, 1 ГБ диска + данные сервисов
порты 80/443 — только если managed Caddy
```
