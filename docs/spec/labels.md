# Метки сервиса

Метки — способ, которым контейнер объявляет себя. Они читаются при обнаружении
и становятся предложением для карточки. Окончательное слово — за базой:
изменение в интерфейсе важнее метки.

## Префикс

```
hub.*   единственный поддерживаемый префикс
```

## Поля

| Метка | Тип | Назначение | Пример |
|---|---|---|---|
| `hub.name` | string | отображаемое имя | `Miniflux` |
| `hub.group` | string | группа карточки | `Сервисы` |
| `hub.icon` | string | иконка (имя файла или URL) | `miniflux.png` |
| `hub.href` | string | ссылка для человека | `https://rss.example.com` |
| `hub.description` | string | подпись | `RSS-читалка` |
| `hub.weight` | int | порядок в группе | `10` |
| `hub.check` | string | адрес проверки | `https://rss.example.com/health` |
| `hub.check.kind` | string | `http` или `tcp` | `http` |
| `hub.check.interval` | int | период, секунды | `60` |
| `hub.route` | string | домен для Caddy | `rss.example.com` |
| `hub.route.port` | int | внутренний порт | `8080` |
| `hub.route.auth` | string | `none` или `basic` | `basic` |
| `hub.update` | string | `manual`, `notify`, `auto` | `notify` |
| `hub.update.cmd` | string | команда версии | `miniflux -i` |
| `hub.backup` | string | что копировать | `volume:miniflux-db` |
| `hub.backup.keep` | int | сколько хранить | `5` |
| `hub.secret.<NAME>` | string | имя секрета (не значение!) | `MINIFLUX_DB_PASSWORD` |
| `hub.hidden` | bool | скрыть из списка | `true` |

## Приоритет

```
1 база (изменения через UI)
2 метки (если в базе пусто)
3 значения по умолчанию
```

При конфликте метка не перезаписывает базу; в интерфейсе показывается
«в метке другое значение» с кнопкой «принять из метки».

## Пример compose

```yaml
services:
  miniflux:
    image: miniflux/miniflux:latest
    labels:
      hub.name: "Miniflux"
      hub.group: "Сервисы"
      hub.icon: "miniflux.png"
      hub.href: "https://rss.example.com"
      hub.check: "http://127.0.0.1:8081/health"
      hub.route: "rss.example.com"
      hub.route.port: "8080"
      hub.update: "notify"
      hub.update.cmd: "miniflux -i"
      hub.backup: "volume:hub-miniflux-db"
      hub.secret.MINIFLUX_DB_PASSWORD: "miniflux-db-password"
```

## Правила

```
значения меток не содержат секретов — только имена
неизвестные hub.* игнорируются и показываются в «расширенных»
контейнер без hub.* виден как «без меток», его можно привязать вручную
при удалении контейнера связанные метки и карточка уходят
```

## Служебные метки (внутренние, ставятся хабом)

```yaml
hub.managed: "true"          контейнер создан хабом
hub.service: "<uuid>"        связь с записью в базе
hub.version: "1.0.0"         версия хаба при создании
```
