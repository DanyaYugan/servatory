#!/usr/bin/env bash
# Установка Servatory из Docker Hub одной командой.
#
#   curl -fsSL https://raw.githubusercontent.com/DanyaYugan/servatory/v0.2.0-beta/deploy/docker/install-release.sh | bash
#
# Переменные:
#   SERVATORY_VERSION   тег без v, по умолчанию 0.2.0-beta
#   SERVATORY_DIR       каталог установки, по умолчанию ./servatory
#   SERVATORY_PORT      порт панели, по умолчанию 8090

set -euo pipefail

VERSION="${SERVATORY_VERSION:-0.2.0-beta}"
DIR="${SERVATORY_DIR:-$PWD/servatory}"
PORT="${SERVATORY_PORT:-8090}"
RAW="${SERVATORY_REPO_RAW:-https://raw.githubusercontent.com/DanyaYugan/servatory}"

log() { printf '[servatory] %s\n' "$*"; }
fail() { printf '[servatory] ошибка: %s\n' "$*" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || fail "нужен Docker"
docker compose version >/dev/null 2>&1 || fail "нужен docker compose v2"
[ -S /var/run/docker.sock ] || fail "не найден /var/run/docker.sock"

GID="$(stat -c '%g' /var/run/docker.sock)"
mkdir -p "$DIR"
cd "$DIR"

log "скачиваю compose для $VERSION"
curl -fsSL "$RAW/v$VERSION/deploy/docker/compose.release.yml" -o compose.release.yml

if [ -f .env ]; then
  log "оставляю существующий .env"
else
  curl -fsSL "$RAW/v$VERSION/deploy/docker/.env.release.example" -o .env
  sed -i "s/^SERVATORY_PORT=.*/SERVATORY_PORT=$PORT/" .env
  sed -i "s/^DOCKER_GID=.*/DOCKER_GID=$GID/" .env
fi

log "запускаю контейнер"
docker compose -f compose.release.yml up -d

log "жду ответ панели"
for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
    log "готово: http://$(hostname -I 2>/dev/null | awk '{print $1}'):$PORT/ui/"
    log "первый вход: admin / admin, сразу смени пароль"
    exit 0
  fi
  sleep 2
done

fail "панель не ответила за 60 секунд, проверьте: docker compose -f $DIR/compose.release.yml logs"
