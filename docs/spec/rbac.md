# Роли, разрешения и доступ

## Модель

```
пользователь → роли → разрешения
пользователь → гранты на конкретный сервис (разрешить или запретить)
итог: объединение ролей, затем гранты; запрет побеждает
```

## Роли по умолчанию

| Роль | Что может |
|---|---|
| `admin` | всё, включая пользователей, интеграции и настройки |
| `operator` | просмотр, действия с сервисами, обновления, бэкапы |
| `viewer` | только просмотр списка и деталей |
| `custom` | любой набор разрешений |

## Разрешения

```
service.read
service.create
service.update
service.delete
service.action.start
service.action.stop
service.action.restart
service.action.update
service.action.backup
service.action.restore
service.secret.read
service.grants.manage
users.manage
roles.manage
settings.read
settings.manage
integrations.manage
audit.read
events.read
```

## Матрица по умолчанию

| Разрешение | admin | operator | viewer |
|---|---|---|---|
| service.read | ✓ | ✓ | ✓ |
| service.create | ✓ | ✓ | — |
| service.update | ✓ | ✓ | — |
| service.delete | ✓ | — | — |
| service.action.start/stop/restart | ✓ | ✓ | — |
| service.action.update/backup/restore | ✓ | ✓ | — |
| service.secret.read | ✓ | — | — |
| service.grants.manage | ✓ | — | — |
| users.manage, roles.manage | ✓ | — | — |
| settings.read | ✓ | ✓ | ✓ |
| settings.manage | ✓ | — | — |
| integrations.manage | ✓ | — | — |
| audit.read | ✓ | ✓ | — |

Удаление сервиса доступно только администратору: это единственное действие,
которое может привести к потере данных.

## Гранты

```
POST /api/v1/services/{id}/grants
{"user_id": "...", "permission": "service.action.update", "allow": true}
{"user_id": "...", "permission": "service.read", "allow": false}
```

Пример: оператор видит все сервисы, но не может обновлять `portainer`:

```
grant: user=ivan, service=portainer, permission=service.action.update, allow=0
```

## Аутентификация

```
веб      POST /api/v1/auth/login {login,password,totp?} → Set-Cookie hub_session
         POST /api/v1/auth/logout
         GET  /api/v1/auth/me
API      Authorization: Bearer <token>
бот      привязка /link <code> в Telegram; код генерируется в профиле
```

Политика паролей: минимум 12 символов, проверка по списку частых, argon2id.
Блокировка: 5 неудач за 10 минут → пауза 15 минут, запись в audit.

## Сессии

```
cookie: httpOnly, Secure, SameSite=Lax, Path=/
CSRF:   заголовок X-CSRF-Token, значение из /auth/me
срок:   7 дней, продление при активности, отзыв при смене пароля
```

## Токены API

```
создание: POST /api/v1/users/{id}/tokens {name, scopes, expires_at}
хранение: только sha256, показывается один раз при создании
scopes:  подмножество разрешений пользователя
```

## Бот

```
telegram_id → user_id (таблица user_links)
каждая команда проверяет разрешение, как веб
опасные действия требуют нажатия inline-кнопки подтверждения
если пользователь отключён — бот отвечает «нет доступа» и пишет в audit
```

## Аудит

Пишутся: входы и выходы, смена пароля и 2FA, создание/изменение/удаление
сервисов, действия, изменения ролей и грантов, применение конфигов Caddy.
Формат: кто, что, над чем, результат, IP, время. Хранится 90 дней.
