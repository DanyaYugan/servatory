# Вход: Caddy и маршруты

## Режимы

| Режим | Кто пишет конфиг | Когда использовать |
|---|---|---|
| `managed` | hub сам поднимает Caddy и пишет конфиг | по умолчанию, «всё в одной установке» |
| `external` | hub правит чужой Caddy по admin API | Caddy уже есть на хосте |
| `labels` | никто: маршруты задаются метками | используется caddy-docker-proxy |
| `none` | никто | за чужим прокси или без TLS |

Режим хранится в `settings.tls_mode`, меняется в мастере и в настройках.

## Адрес admin API

```
managed   http://caddy:2019        внутри compose-сети
external  http://127.0.0.1:2019    или https://caddy.example:2019
```

## Модель маршрута

```
service.domain  →  upstream  →  опции
```

Upstream выбирается по провайдеру:

```
docker-local    имя контейнера и порт:      miniflux:8080
docker-remote   имя контейнера на том хосте: miniflux:8080 (через endpoint)
http            не маршрутизируется, только ссылка
```

Опции маршрута: `auth` (пока `basic`), `headers`, `path`, `tls` (внутренний
или ACME).

## Генерация конфига

Собирается JSON в формате Caddy (не Caddyfile): так проще валидировать и
применять точечно.

```json
{
  "apps": {
    "http": {
      "servers": {
        "hub": {
          "listen": [":443"],
          "routes": [
            {
              "match": [{"host": ["rss.example.com"]}],
              "handle": [{
                "handler": "reverse_proxy",
                "upstreams": [{"dial": "miniflux:8080"}]
              }]
            }
          ]
        }
      }
    }
  }
}
```

## Применение

```
1 собрать желаемый конфиг из базы
2 получить текущий: GET /config/apps/http/servers/
3 validate: POST /load с ?validate=1 или отдельная проверка
4 load: POST /load с If-Match (etag текущего)
5 сохранить last_good в /data/caddy-last-good.json
6 при ошибке: POST /load с last_good, уведомление
```

Правила безопасности:

```
не чаще одного применения в 5 секунд
при конфликте etag — перечитать и повторить один раз
если Caddy недоступен — режим degraded, маршруты не меняются
все применения пишутся в audit
```

## Базовые маршруты хаба

```
hub.example.com          → hub:8080
hub.example.com/status   → статика из /data/public (если включено)
```

Маршруты хаба не удаляются при удалении сервисов: они в отдельной группе
`system`.

## Сертификаты

```
managed:  Caddy сам получает ACME, e-mail из настроек
external: сертификаты на стороне внешнего Caddy
none:     TLS снаружи, hub только отдаёт ссылки
```

При смене домена хаб предупреждает, что сертификат будет перевыпущен.

## Режим labels

```
в compose добавляется caddy-docker-proxy
маршруты задаются метками: caddy, caddy.reverse_proxy
hub только читает и показывает; кнопка «Применить» неактивна
```

## Диагностика

```
GET /api/v1/integrations/caddy/status
{"mode":"managed","reachable":true,"last_apply":"...","last_error":null,
 "routes":12,"last_good_at":"..."}
```
