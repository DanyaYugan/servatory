#!/usr/bin/env bash
# Установка Servatory нативно: пользователь, каталоги, venv, systemd.
# Использование: sudo ./deploy/install.sh [--upgrade|--uninstall]

set -euo pipefail

APP_DIR="/opt/servatory"
DATA_DIR="/var/lib/servatory"
SERVICE_USER="servatory"
PYTHON_BIN="${PYTHON_BIN:-python3}"
UNIT_DIR="/etc/systemd/system"

log() { printf '[install] %s\n' "$*"; }
fail() { printf '[install] ошибка: %s\n' "$*" >&2; exit 1; }

require_root() {
  [ "$(id -u)" -eq 0 ] || fail "запустите через sudo"
}

check_env() {
  command -v "$PYTHON_BIN" >/dev/null || fail "нужен $PYTHON_BIN"
  "$PYTHON_BIN" -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)' \
    || fail "нужен Python 3.12+"
  command -v systemctl >/dev/null || fail "нужен systemd"
  command -v docker >/dev/null || log "предупреждение: docker не найден"
}

create_user() {
  if ! id "$SERVICE_USER" >/dev/null 2>&1; then
    useradd --system --home "$DATA_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
    log "создан пользователь $SERVICE_USER"
  fi
  if getent group docker >/dev/null; then
    usermod -aG docker "$SERVICE_USER" || true
  fi
}

install_files() {
  mkdir -p "$APP_DIR" "$DATA_DIR" /etc/servatory
  chown -R "$SERVICE_USER":root "$DATA_DIR"
  chmod 750 "$DATA_DIR"
  if command -v docker >/dev/null; then
    docker volume create servatory-backups >/dev/null 2>&1 || true
  fi
  log "каталоги готовы"
}

install_python() {
  if [ ! -d "$APP_DIR/.venv" ]; then
    "$PYTHON_BIN" -m venv "$APP_DIR/.venv"
    log "venv создан"
  fi
  "$APP_DIR/.venv/bin/pip" install --upgrade pip >/dev/null
  "$APP_DIR/.venv/bin/pip" install "$APP_DIR/backend" >/dev/null
  log "зависимости установлены"
}

install_units() {
  install -m 644 "$APP_DIR/deploy/systemd/servatory.service" "$UNIT_DIR/servatory.service"
  install -m 644 "$APP_DIR/deploy/systemd/servatory-failure@.service" "$UNIT_DIR/servatory-failure@.service"
  install -m 755 "$APP_DIR/deploy/servatory-notify-failure.sh" /usr/local/bin/servatory-notify-failure
  systemctl daemon-reload
  systemctl enable --now servatory.service
  log "служба включена"
}

upgrade() {
  systemctl stop servatory.service || true
  "$APP_DIR/.venv/bin/pip" install "$APP_DIR/backend" >/dev/null
  systemctl start servatory.service
  log "обновление завершено"
}

uninstall() {
  systemctl disable --now servatory.service 2>/dev/null || true
  rm -f "$UNIT_DIR/servatory.service" "$UNIT_DIR/servatory-failure@.service"
  systemctl daemon-reload
  log "служба удалена; данные в $DATA_DIR оставлены"
}

main() {
  require_root
  case "${1:---install}" in
    --upgrade) check_env; upgrade ;;
    --uninstall) uninstall ;;
    *)
      check_env
      create_user
      install_files
      install_python
      install_units
      log "готово: http://$(hostname -I | awk '{print $1}'):8090"
      ;;
  esac
}

main "$@"
