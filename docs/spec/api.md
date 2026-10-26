# API v1

Базовый путь `/api/v1`. JSON, UTF-8. Время — unix seconds (UTC).

## Аутентификация

```
веб      Cookie: hub_session=<id>; CSRF-заголовок X-CSRF-Token для POST/PATCH/DELETE
API      Authorization: Bearer <token>
бот      внутренний вызов core (без HTTP) либо Bearer-токен с scope bot
```

## Соглашения

```
коды ошибок     400 валидация, 401 нет входа, 403 нет прав, 404 не найдено,
                409 конфликт/блокировка, 422 бизнес-правило, 500 внутренняя
формат ошибки   {"error": {"code": "service_locked", "message": "...",
                          "hint": "дождитесь завершения операции"}}
пагинация       ?limit=50&cursor=<opaque>; ответ: {"items": [...], "next": "..."}
идемпотентность POST/PATCH принимает Idempotency-Key, повтор возвращает тот же результат
операции        длительные действия возвращают 202 {"operation_id": "..."}
события         GET /events — SSE, событие {"type": "...", "at": 123, "data": {...}}
```

## Эндпоинты

### Служебные

```
GET /health       200 {"status":"ok","version":"1.0.0"}
GET /ready        200 если БД и хотя бы один провайдер доступны
GET /api/v1/meta  {"version":"1.0.0","schema":3,"locale":"ru"}
```

### Сервисы

```
GET /api/v1/services?group=&state=&q=&source=
```

Ответ:

```json
{
  "items": [
    {
      "id": "8f3c...",
      "name": "miniflux",
      "title": "Miniflux",
      "group": "Сервисы",
      "state": "running",
      "source": "label",
      "domain": "rss.example.com",
      "health": {"ok": true, "latency_ms": 12, "checked_at": 1792590000},
      "provider": {"id": "p1", "kind": "docker-local"},
      "update": {"available": true, "current": "2.3.4", "new": "2.3.5",
                  "policy": "notify"},
      "backup": {"last_at": 1792500000, "size": 21595677, "status": "ok"}
    }
  ],
  "next": null
}
```

```
POST /api/v1/services
```

Запрос:

```json
{
  "name": "uptime-kuma",
  "provider_id": "p1",
  "title": "Uptime Kuma",
  "group": "Сервисы",
  "domain": "status.example.com",
  "runtime": {
    "image": "louislam/uptime-kuma:1",
    "ports": ["3001:3001"],
    "volumes": [{"type": "named", "source": "hub-uptime-kuma-data",
                  "target": "/app/data"}],
    "env": {"TZ": "Asia/Yekaterinburg"},
    "secrets": ["UPTIME_KUMA_ADMIN_PASSWORD"],
    "restart": "unless-stopped"
  },
  "check": {"kind": "http", "target": "http://127.0.0.1:3001", "interval": 60},
  "policy": {"update": "notify", "backup": {"enabled": true, "keep": 5}}
}
```

Ответ: `202 {"operation_id": "..."}`

```
GET    /api/v1/services/{id}                 полная карточка + метки + проверки
PATCH  /api/v1/services/{id}                 частичное изменение, 202
DELETE /api/v1/services/{id}?keep_volume=1   удаление, 202
POST   /api/v1/services/{id}/actions/{action}
       action: start|stop|restart|update|backup|restore|recreate
       тело: {"backup_id": "..."} для restore, {"confirm": true} для опасных
GET    /api/v1/services/{id}/logs?tail=200   текст, не JSON
GET    /api/v1/services/{id}/backups         список backups
GET    /api/v1/services/{id}/checks          результаты проверок
```

### Провайдеры

```
GET  /api/v1/providers
POST /api/v1/providers
     {"kind":"docker-local","name":"local","config":{}}
     {"kind":"docker-remote","name":"ai","config":{"url":"tcp://<host>:2376",
       "ca":"...","cert":"...","key":"..."}}
POST /api/v1/providers/{id}/test → {"ok":true,"docker_version":"27.3"}
```

### Пользователи и роли

```
GET    /api/v1/users
POST   /api/v1/users        {"login":"user","password":"...","roles":["admin"]}
PATCH  /api/v1/users/{id}   {"password":"...","status":"disabled","roles":[...]}
DELETE /api/v1/users/{id}
GET    /api/v1/roles        список с разрешениями
POST   /api/v1/roles        {"name":"ops","permissions":["service.read",...]}
PATCH  /api/v1/roles/{id}
POST   /api/v1/services/{id}/grants   {"user_id":"...","permission":"...","allow":false}
```

### Состояние и обновления

```
GET  /api/v1/state     сводка: counts, problems, drift, updates, jobs_last_run
GET  /api/v1/updates   список доступных обновлений
POST /api/v1/updates/apply  {"services":["id1","id2"],"confirm":true}
```

### Настройки и интеграции

```
GET   /api/v1/settings
PATCH /api/v1/settings  {"tls_mode":"managed","domain":"hub.example.com",
                         "locale_default":"ru"}
POST  /api/v1/integrations/telegram/test   {"token":"...","chat_id":"..."}
POST  /api/v1/integrations/caddy/apply     принудительно применить маршруты
```

### Аудит и операции

```
GET /api/v1/audit?from=&to=&user=&action=
GET /api/v1/operations/{id}    {"status":"running","log":"..."}
GET /api/v1/events             SSE
```

## Коды ошибок (минимум)

```
auth_required         нет сессии или токена
permission_denied     роли/гранты не дают прав
service_locked        по сервису идёт другая операция
provider_unavailable  Docker недоступен
validation_failed     поля не прошли проверку
conflict              дубль имени или порта
operation_failed      действие завершилось ошибкой (смотреть operations)
not_implemented       функция не включена в этой сборке
```

## SSE

```
event: service.updated
data: {"id":"...","state":"running","at":1792590000}

event: service.added | service.removed | operation.finished
event: update.available | alert.raised
```

Соединение требует авторизации; при 401 клиент переподключается после логина.
