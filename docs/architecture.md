# Servatory — архитектура продукта

Статус: **дизайн зафиксирован, код не начат.**
Этот документ описывает продукт целиком: что это, из чего состоит, как хранит
данные, как разграничивает права и как устанавливается.

Схема: `diagrams/architecture.svg` (и `.png`).

---

## 1. Что это

```
Servatory — панель управления домашними сервисами.
Показывает всё, что запущено, и даёт управлять этим из одного места.
```

Не заменяет Docker, не оркестратор, не CI/CD. Слой над Docker и systemd:
обзор, действия, права, уведомления, вход.

Принципы:

```
один вход для человека        веб и бот
один источник правды          база хаба; метки — способ объявления
ничего не зашито в код        сервисы, роли, маршруты — данные
безопасные изменения          бэкап → проверка → откат → журнал
переносимость                 всё состояние в /data
```

---

## 2. Зафиксированные решения

| Пункт | Решение |
|---|---|
| Аутентификация | локальные учётки + TOTP; интерфейс провайдера входа под OIDC в 1.1 |
| Фронтенд | Vue 3 + Vite + Naive UI + vue-i18n + Pinia |
| Тома | гибрид: именованные тома по умолчанию, хост-каталоги только в `/data/services/*` |
| Удалённые хосты | Docker API по TLS в 1.0, свой агент в 1.1 |
| Лицензия | Apache 2.0 |
| Языки | ru + en с первого дня, en по умолчанию |
| Секреты | шифрованное хранилище + режим «внешний файл» |

Обоснование — `decisions.md`.

---

## 3. Компоненты

```
core    API, реестр, провайдеры, проверки, действия, права, журнал, генерация
web     SPA, отдаётся core
bot     Telegram-клиент core
jobs    расписание, алерты, поиск обновлений; отдельный процесс
agent   опциональный демон на удалённом хосте (1.1)
```

Правила доступа:

```
только core имеет доступ к Docker и базе на запись
web и bot — клиенты API, ничего не знают о Docker
jobs читает базу только на чтение и шлёт уведомления напрямую
```

---

## 4. Топология и режимы

```
контейнер (основной)
  hub      :8080    api + web
  jobs     —        расписание
  caddy    :80/443  опционально
  agent    :9443    опционально

нативно
  hub.service, jobs.service, install.sh, venv
  caddy — системный или контейнер
```

Compose-профили: `core` (обязательный), `ingress` (caddy), `agent`, `metrics`.

---

## 5. Данные

`/data` — единственный каталог состояния:

```
/data/config.yaml      bootstrap: порт, режим TLS, домен, язык
/data/hub.db           SQLite (WAL)
/data/key              ключ шифрования секретов, права 600
/data/backups/         копии базы и экспорт
/data/services/<name>/ хост-каталоги сервисов, если выбраны
/data/logs/            журналы
```

Схема (SQLAlchemy 2 + Alembic):

```
users             id, login, password_hash, totp_secret, status, created_at
roles             id, name, builtin
permissions       code
role_permissions  role_id, permission
user_roles        user_id, role_id
service_grants    user_id, service_id, permission
sessions          id, user_id, expires_at, ip, user_agent
api_tokens        id, user_id, token_hash, scopes, expires_at
providers         id, kind, name, config_encrypted, status
services          id, provider_id, external_id, name, compose_json,
                  domain, health_url, policy_json, state, updated_at
service_labels    service_id, key, value
checks            id, service_id, kind, target, interval
check_results     check_id, at, ok, latency_ms, message
groups            id, name, weight, icon
settings          key, value
audit             id, at, user_id, action, object, result, details
alert_rules       id, kind, condition_json, severity, targets
backups           id, service_id, at, path, size, status
operations        id, kind, service_id, status, started_at, finished_at, log
```

`schema_version` хранится в `settings`; миграции применяются при старте,
откат — из копии базы в `/data/backups`.

---

## 6. Аутентификация и права

Вход: локальные учётки, argon2, TOTP по желанию, блокировка после N попыток.

```
веб      сессия (httpOnly, Secure, SameSite) + CSRF-токен
API      Bearer-токен со scopes
бот      привязка telegram_id → user_id, те же права
```

Роли по умолчанию:

```
admin      всё
operator   просмотр + действия + обновления + бэкапы
viewer     только просмотр
custom     произвольный набор
```

Разрешения:

```
service.read, service.create, service.update, service.delete
service.action.start|stop|restart|update|backup|restore
service.secret.read
users.manage, roles.manage
settings.read, settings.manage
integrations.manage
audit.read
```

Правила: доступ = роль + точечные grants; запрет важнее разрешения;
каждое действие пишется в `audit`.

---

## 7. API

REST, префикс `/api/v1`, JSON, ошибки с кодом и подсказкой.

```
GET    /health, /ready
GET    /api/v1/services?group=&state=&q=
POST   /api/v1/services
GET    /api/v1/services/{id}
PATCH  /api/v1/services/{id}
DELETE /api/v1/services/{id}?keep_volume=1
POST   /api/v1/services/{id}/actions/{action}
GET    /api/v1/services/{id}/logs?tail=
GET    /api/v1/services/{id}/backups
GET    /api/v1/providers ; POST /api/v1/providers
GET/POST/PATCH/DELETE /api/v1/users, /api/v1/roles
GET    /api/v1/state
GET    /api/v1/updates ; POST /api/v1/updates/apply
GET    /api/v1/audit
GET    /api/v1/events            SSE
GET/PATCH /api/v1/settings
GET    /api/v1/operations/{id}
```

Соглашения: `Idempotency-Key` для POST, `operation_id` для длительных действий,
пагинация `?limit=&cursor=`, версия API в пути.

---

## 8. Провайдеры и метки

Провайдеры:

```
docker-local    unix:///var/run/docker.sock
docker-remote   TLS (1.0), агент (1.1)
http            наблюдение без управления
systemd         через агент (позже)
```

Метки сервиса:

```yaml
hub.group: "Сервисы"
hub.name: "Miniflux"
hub.icon: "miniflux.png"
hub.href: "https://rss.example.com"
hub.check: "https://rss.example.com/health"
hub.backup: "volume:miniflux-db"
hub.update: "manual"           # manual | notify | auto
hub.route: "rss.example.com"
```

Приоритет: значения из базы важнее меток. Метки — предложение при импорте,
окончательное слово за UI.

Сверка:

```
факт = провайдеры.list()
желаемое = services
сравнить → running / stopped / missing / drift
записать check_results, обновить state, опубликовать событие
```

---

## 9. Действия

```
add        создать контейнер/стек
update     pull → пересоздать → проверка → откат
remove     остановить, удалить; том по выбору
backup     копия тома/базы по политике
restore    развернуть копию
apply      сгенерировать конфиги и маршруты, применить
```

Конвейер изменения:

```
1 права и подтверждение
2 зафиксировать состояние до (образ, конфиг, маршруты, база)
3 блокировка на сервис
4 выполнить
5 проверить health и домен
6 при ошибке откат, запись в audit
7 событие и уведомление
```

Тома: по умолчанию `hub-<service>-data`; хост-каталоги только
`/data/services/<name>`; произвольные пути — расширенный режим compose.

Бэкап томов — вспомогательным контейнером с `--volumes-from`,
не чтением `/var/lib/docker/volumes`.

---

## 10. Вход и Caddy

```
managed    хаб поднимает Caddy и пишет конфиг через admin API
external   правит конфиг внешнего Caddy по admin API
labels     маршруты задаются метками, хаб не пишет
none       за чужим прокси, только ссылки
```

Для `managed` и `external`:

```
сгенерировать JSON → validate → load с etag
хранить последний рабочий конфиг
при ошибке вернуть прежний и сообщить
не чаще одного применения в N секунд
```

Модель маршрута: домен → сервис, плюс опции `auth`, `headers`, `path`.

---

## 11. Обновления

```
поиск      digest образа, версия из метки или команды
политика   per-service: manual | notify | auto
окно       разрешённые часы для auto
применение бэкап → pull → recreate → health → откат
уведомление было → стало, кто и когда
```

---

## 12. Бот и уведомления

```
команды        статус, список, обновления, логи, обновить <сервис>
права          те же, что в вебе, через привязку telegram_id
подтверждения  inline-кнопки для опасных действий
алерты         от jobs напрямую в Telegram, не через core
каналы         telegram, webhook (позже), email (позже)
```

---

## 13. Jobs

```
правила    health, backup_age, disk, updates, ошибки
тишина     quiet hours, подавление дублей
эскалация  повтор через N, максимум M
watchdog   проверка самого core и jobs
```

Отдельный процесс специально: если core упал, алерты продолжают идти.

---

## 14. Веб-интерфейс

```
/dashboard        сводка, проблемы, обновления
/services         список, фильтры, группы
/services/{id}    состояние, проверки, логи, бэкапы, действия
/groups           группы и порядок
/updates          список и применение
/users            пользователи, роли, grants
/integrations     провайдеры, Caddy, Telegram
/audit            журнал
/settings         вид, язык, темы, экспорт/импорт
/wizard           первый запуск
```

Требования: мобильная вёрстка, тёмная/светлая тема, клавиатурная навигация,
пустые состояния, i18n ru/en.

---

## 15. Секреты

```
хранилище      значения шифруются ключом /data/key
использование  в compose ${secret:name}, подстановка при применении
внешние файлы  режим «не хранить, взять из .env»
экспорт        только по явному выбору, зашифрованным архивом
```

---

## 16. Безопасность

```
Docker-сокет   только core; в контейнере — через socket-proxy по умолчанию
секреты        шифрование, права 600, не логировать
сессии         httpOnly, Secure, SameSite, CSRF
пароли         argon2, политика, блокировки
токены         хеш, scopes, срок
агент          mTLS или одноразовый токен (1.1)
аудит          входы, изменения, действия
```

---

## 17. Отказоустойчивость

| Что упало | Работает | Не работает |
|---|---|---|
| hub | сервисы, Caddy, jobs | веб, бот, управление |
| jobs | всё остальное | алерты |
| Caddy | сервисы по портам | домены |
| база | сервисы | управление до восстановления |

Защита: `Restart=always`, `OnFailure` с уведомлением, `hub status/rollback`,
ежедневная копия базы в `/data/backups`.

---

## 18. Репозиторий и CI

```
hub/
  backend/
    app/
      api/          ручки v1
      core/         реестр, сверка, действия
      providers/    docker, http, agent
      ingress/      caddy managed/external
      auth/         сессии, токены, RBAC
      jobs/         правила, расписание
      db/           модели, миграции
      notify/       telegram, webhook
    tests/
  frontend/         Vue 3 + Vite
  deploy/
    docker/         Dockerfile (multi-stage), compose.yml, entrypoint
    systemd/        hub.service, jobs.service, failure@.service
    install.sh
  docs/             quickstart, api, labels, roles, security
  examples/         compose-фрагменты сервисов
  .github/          ci: lint, test, образы amd64/arm64, релизы
```

CI: ruff, pytest, сборка фронта, два образа, публикация в ghcr по тегу.

---

## 19. Версии

```
semver        1.0.0; минорные добавляют, мажорные ломают
схема БД      Alembic, миграции вперёд, откат из бэкапа
API           /api/v1 стабилен, изменения только добавлением
образы        latest + фиксированные теги, мультиарх
```

---

## 20. Этапы

| Этап | Итог | Приёмка |
|---|---|---|
| 0 | репозиторий, лицензия, CI, каркас сборки | образ собирается, тесты проходят |
| 1 | скелет: БД, docker-провайдер, API чтения, страница | список и карточки, события, рестарт |
| 2 | пользователи, роли, сессии, аудит | вход, права проверяются |
| 3 | действия: add/remove/update/backup, откат | тестовый сервис, удаление без следов |
| 4 | Caddy managed, домены | сайт с TLS из UI |
| 5 | бот и уведомления | команды с правами |
| 6 | jobs отдельно, алерты | алерт при мёртвом хабе |
| 7 | wizard, обновления, миграции, demo | установка с нуля за 5 минут |
| 8 | docs, релиз 1.0 | сторонний проходит quickstart |

---

## 21. Открытые вопросы

1. **Socket-proxy** — ставить всегда или только рекомендовать? По умолчанию: ставить,
   с возможностью отключить.
2. **Политика обновлений по умолчанию** — `notify` или `manual`? По умолчанию: `notify`.
3. **Ретеншн бэкапов** — 7 дней и 5 последних копий на сервис? По умолчанию так.
4. **TOTP для администратора** — предлагать, не навязывать.
5. **Демо-режим** — флаг `DEMO=1`.

> Имена вида `hub.db`, `hub.service` и метки `hub.*` в спецификациях — исторические.
> В коде и на сервере используем `servatory.*`; при стабилизации заменим везде.
