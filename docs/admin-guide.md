# Руководство администратора

Версия: `0.2.0-beta`.

## 1. Что нужно

```
Linux с Docker 24+
2 ГБ ОЗУ, 2 ядра, 10 ГБ диска
свободные порты 8090 (панель), 80 и 443 (Caddy, если включаете TLS)
доступ к /var/run/docker.sock
```

## 2. Установка

### 2.1. Образ из Docker Hub

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

Или compose:

```bash
mkdir servatory && cd servatory
curl -fsSLO https://raw.githubusercontent.com/danyayugan/servatory/v0.2.0-beta/deploy/docker/compose.release.yml
curl -fsSL https://raw.githubusercontent.com/danyayugan/servatory/v0.2.0-beta/deploy/docker/.env.release.example -o .env
nano .env
docker compose up -d
```

В `.env`:

```
SERVATORY_IMAGE=danyayugan/servatory:0.2.0-beta
SERVATORY_PORT=8090
DOCKER_GID=112
```

GID сокета:

```bash
stat -c '%g' /var/run/docker.sock
```

### 2.2. Из исходников

```bash
git clone <репозиторий> servatory
cd servatory/deploy/docker
cp .env.example .env
nano .env
docker compose up -d --build
```

Первый вход: `admin` / `admin`. Смените пароль в
«Настройки → Безопасность» сразу после входа.

## 3. Нативная установка

```bash
sudo ./deploy/install.sh
```

Ставит venv, systemd-службу и каталоги `/opt/servatory`, `/var/lib/servatory`.

## 4. Настройки

```
/data/config.toml        основной файл
/data/servatory.db       база
/data/caddy/Caddyfile    конфигурация Caddy
/backups                 архивы
```

Переменные окружения перекрывают файл:

```
SERVATORY_PORT
SERVATORY_DATA
SERVATORY_ADMIN_LOGIN
SERVATORY_ADMIN_PASSWORD
SERVATORY_SESSION_HOURS
SERVATORY_DOCKER_SOCKET
SERVATORY_BACKUP_DIR
SERVATORY_BACKUP_VOLUME
SERVATORY_BACKUP_KEEP
SERVATORY_LOG_LEVEL
```

## 5. Пользователи и роли

```
superadmin  всё, включая пользователей и журнал
admin       сервисы, действия, бэкапы, группы, TLS, журнал
operator    просмотр и действия: старт, стоп, перезапуск, обновление
viewer      только просмотр
```

Своя роль не меняется даже у superadmin — чтобы не потерять доступ.
Своя учётная запись и пароль: «Настройки → Безопасность».

## 6. Домены и TLS

«Настройки → Домены и TLS».

```
домен       panel.example.com
почта       admin@example.com
TLS         да
```

Панель:

```
скачивает caddy:2-alpine
создаёт контейнер servatory-caddy
пишет /data/caddy/Caddyfile
пробрасывает 80 и 443
```

Требования:

```
домен указывает A-записью на сервер
порты 80 и 443 свободны
исходящий доступ к Let's Encrypt
```

Для `localhost` и IP используется внутренний CA Caddy — браузер
предупредит о самоподписанном сертификате.

Панель остаётся доступна напрямую на 8090. Это запасной вход,
если Caddy не запустился.

После включения TLS cookie сессии становятся `Secure`, потому что
Caddy передаёт `X-Forwarded-Proto: https`, а uvicorn доверяет прокси.

## 7. Обновление

```bash
cd servatory
git pull
cd deploy/docker
docker compose up -d --build
```

Миграции базы применяются автоматически при старте: `PRAGMA user_version`,
таблица `settings`, версия схемы видна в «Настройки → Общие».

Перед обновлением:

```bash
docker exec servatory tar czf /backups/before-update.tar.gz -C /data .
docker cp servatory:/backups/before-update.tar.gz ./before-update.tar.gz
```

## 8. Резервные копии

Копии сервисов лежат в томе `servatory-backups`, интерфейс — вкладка
«Бэкапы» на странице сервиса. Копия базы панели:

```bash
docker exec servatory tar czf /backups/panel.tar.gz -C /data .
docker cp servatory:/backups/panel.tar.gz .
```

Восстановление панели:

```bash
docker compose stop servatory
docker run --rm -v servatory_servatory-data:/data -v "$PWD":/backup alpine \
  sh -c 'rm -rf /data/* && tar xzf /backup/panel.tar.gz -C /data'
docker compose up -d
```

## 9. Диагностика

```bash
docker compose logs -f servatory
docker exec servatory curl -fsS http://127.0.0.1:8090/health
docker exec servatory curl -fsS http://127.0.0.1:8090/ready
docker ps --filter name=servatory
```

Частые причины:

```
401 на все запросы       истекла сессия, войдите заново
403                      нет права или неверный CSRF
Docker недоступен        проверьте DOCKER_GID и сокет
Caddy не стартует        заняты 80/443 или домен не указывает на сервер
```

## 10. Безопасность

```
пароли PBKDF2-SHA256, 200 000 итераций
cookie HttpOnly, SameSite=Lax, Secure при HTTPS
CSRF-заголовок на изменяющих запросах
журнал действий
роли и права
```

Что ещё стоит сделать вне панели:

```
закрыть 8090 файрволом, оставить только 80/443
не давать сокет Docker посторонним
обновлять образы
хранить копии вне сервера
```

## 11. Для сопровождающего

Образ публикуется в Docker Hub:

```
danyayugan/servatory:0.2.0-beta
danyayugan/servatory:latest
```

Секреты GitHub Actions:

```
DOCKERHUB_USERNAME=danyayugan
DOCKERHUB_TOKEN=токен с Read & Write
```

Релиз:

```bash
git tag v0.2.0-beta
git push origin v0.2.0-beta
```

Workflow соберёт amd64 и обновит теги в Docker Hub.

