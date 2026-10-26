# Модель данных

СУБД: SQLite (WAL). ORM: SQLAlchemy 2, миграции Alembic.
Файл: `/data/hub.db`. Копия при старте и раз в сутки — `/data/backups/`.

## Правила

```
все временные метки — UTC, integer unix seconds
все идентификаторы — uuid4 в тексте (36 символов)
удаление сервиса — soft delete (deleted_at), чтобы сохранить историю
деньги/размеры — integer (байты), не float
json-поля — TEXT с JSON, валидируются pydantic при записи
```

## Таблицы

### users

```
id            TEXT PK
login         TEXT UNIQUE NOT NULL
password_hash TEXT NOT NULL          argon2
totp_secret   TEXT NULL              base32, шифруется
status        TEXT NOT NULL          active | disabled
locale        TEXT NOT NULL DEFAULT 'en'
created_at    INTEGER NOT NULL
last_login_at INTEGER NULL
```

### roles

```
id        TEXT PK
name      TEXT UNIQUE NOT NULL       admin | operator | viewer | custom
builtin   INTEGER NOT NULL DEFAULT 0
```

### permissions

```
code TEXT PK                          service.read, service.action.update, ...
```

### role_permissions

```
role_id    TEXT NOT NULL REFERENCES roles(id) ON DELETE CASCADE
permission TEXT NOT NULL REFERENCES permissions(code)
PRIMARY KEY (role_id, permission)
```

### user_roles

```
user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE
role_id TEXT NOT NULL REFERENCES roles(id) ON DELETE CASCADE
PRIMARY KEY (user_id, role_id)
```

### service_grants

```
user_id     TEXT NOT NULL
service_id  TEXT NOT NULL
permission  TEXT NOT NULL
allow       INTEGER NOT NULL DEFAULT 1   1 = разрешить, 0 = запретить
PRIMARY KEY (user_id, service_id, permission)
```

Правило вычисления: базово — объединение разрешений ролей; затем применяются
гранты, где `allow=0` имеет приоритет.

### sessions

```
id         TEXT PK                   хеш идентификатора
user_id    TEXT NOT NULL
created_at INTEGER NOT NULL
expires_at INTEGER NOT NULL
ip         TEXT
user_agent TEXT
csrf       TEXT NOT NULL
```

### api_tokens

```
id         TEXT PK
user_id    TEXT NOT NULL
name       TEXT NOT NULL
token_hash TEXT NOT NULL UNIQUE      sha256
scopes     TEXT NOT NULL             JSON-массив permission-кодов
expires_at INTEGER NULL
last_used  INTEGER NULL
created_at INTEGER NOT NULL
```

### providers

```
id         TEXT PK
kind       TEXT NOT NULL             docker-local | docker-remote | http | systemd
name       TEXT NOT NULL
config     TEXT NOT NULL             JSON, шифруется целиком
status     TEXT NOT NULL             ok | error | unknown
last_error TEXT NULL
created_at INTEGER NOT NULL
```

### services

```
id            TEXT PK
provider_id   TEXT NOT NULL REFERENCES providers(id)
external_id   TEXT NULL              id контейнера/юнита у провайдера
name          TEXT NOT NULL
group_id      TEXT NULL REFERENCES groups(id)
domain        TEXT NULL
health_url    TEXT NULL
icon          TEXT NULL
description   TEXT NULL
compose       TEXT NULL              JSON фрагмента
policy        TEXT NOT NULL          JSON: update, backup, window
state         TEXT NOT NULL          running | stopped | missing | drift | unknown
source        TEXT NOT NULL          ui | label | import
created_at    INTEGER NOT NULL
updated_at    INTEGER NOT NULL
deleted_at    INTEGER NULL
```

Индексы: `(provider_id)`, `(state)`, `(deleted_at)`, `UNIQUE(provider_id, external_id)`.

### service_labels

```
service_id TEXT NOT NULL
key        TEXT NOT NULL
value      TEXT NOT NULL
PRIMARY KEY (service_id, key)
```

### groups

```
id     TEXT PK
name   TEXT NOT NULL
weight INTEGER NOT NULL DEFAULT 100
icon   TEXT NULL
```

### checks

```
id         TEXT PK
service_id TEXT NOT NULL
kind       TEXT NOT NULL         http | tcp | container | none
target     TEXT NULL
interval   INTEGER NOT NULL      секунды
timeout    INTEGER NOT NULL
enabled    INTEGER NOT NULL DEFAULT 1
```

### check_results

```
id         INTEGER PK AUTOINCREMENT
check_id   TEXT NOT NULL
at         INTEGER NOT NULL
ok         INTEGER NOT NULL
latency_ms INTEGER NULL
message    TEXT NULL
```

Хранение: 7 дней детально, дальше агрегат. Чистка в jobs.

### settings

```
key   TEXT PK
value TEXT NOT NULL       JSON
```

Обязательные ключи: `schema_version`, `tls_mode`, `domain`, `locale_default`,
`update_policy_default`, `backup_retention`, `demo_mode`.

### audit

```
id        TEXT PK
at        INTEGER NOT NULL
user_id   TEXT NULL
action    TEXT NOT NULL       service.create, auth.login, ...
object    TEXT NULL           service id, user id
result    TEXT NOT NULL       ok | denied | error
details   TEXT NULL           JSON
ip        TEXT NULL
```

### alert_rules

```
id         TEXT PK
kind       TEXT NOT NULL      health | backup_age | disk | updates | custom
config     TEXT NOT NULL      JSON
severity   TEXT NOT NULL      info | warning | critical
targets    TEXT NOT NULL      JSON: telegram chats, webhooks
enabled    INTEGER NOT NULL DEFAULT 1
```

### backups

```
id         TEXT PK
service_id TEXT NOT NULL
at         INTEGER NOT NULL
path       TEXT NOT NULL
size       INTEGER NOT NULL
kind       TEXT NOT NULL      volume | database | config
status     TEXT NOT NULL      ok | failed | running
message    TEXT NULL
```

### operations

```
id          TEXT PK
kind        TEXT NOT NULL     add | remove | update | backup | restore | apply
service_id  TEXT NULL
status      TEXT NOT NULL     queued | running | ok | failed | rolled_back
started_at  INTEGER
finished_at INTEGER
log         TEXT              построчно
user_id     TEXT NULL
```

## Миграции

```
Alembic, каталог backend/app/db/migrations
при старте: upgrade до head; при несовместимости — отказ и сообщение
перед миграцией: копия hub.db в /data/backups/pre-migrate-<version>.db
откат: остановить hub, вернуть копию, запустить прошлую версию
```

## Экспорт и импорт

```
экспорт      JSON: users(без хешей), roles, services, groups, settings,
             providers(без секретов), alert_rules
             опционально: секреты — отдельным зашифрованным архивом
импорт       проверка schema_version → миграция → вставка с новыми id
             конфликты по именам: спросить «перезаписать / пропустить»
```
