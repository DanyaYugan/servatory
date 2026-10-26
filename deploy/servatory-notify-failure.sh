#!/bin/sh
# Уведомление о падении службы через Telegram напрямую.
# Вызывается из servatory-failure@.service, не зависит от панели.

set -eu

unit="${1:-unknown}"
state_dir="/var/lib/servatory"
state_file="$state_dir/last-failure"
now="$(date +%s)"
last="$(cat "$state_file" 2>/dev/null || echo 0)"

if [ $((now - last)) -lt 600 ]; then
  exit 0
fi

mkdir -p "$state_dir" 2>/dev/null || true
echo "$now" > "$state_file" 2>/dev/null || true

host="$(hostname)"
text="⚠️ ${host}: юнит ${unit} упал. Проверьте: systemctl status ${unit}"

if [ -z "${TG_TOKEN:-}" ] || [ -z "${TG_CHAT:-}" ]; then
  logger -t servatory-failure "нет TG_TOKEN/TG_CHAT: ${unit}"
  exit 0
fi

curl -fsS -o /dev/null \
  --data-urlencode "chat_id=${TG_CHAT}" \
  --data-urlencode "text=${text}" \
  "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
  || logger -t servatory-failure "не удалось отправить: ${unit}"
