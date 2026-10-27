#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="${0:A:h}"
PROJECT_DIR="${SCRIPT_DIR:h}"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"
TEMPLATE="$PROJECT_DIR/launchd/com.hhcopilot.backend.plist.template"
TARGET="$HOME/Library/LaunchAgents/com.hhcopilot.backend.plist"
DOMAIN="gui/$(id -u)"
SERVICE="$DOMAIN/com.hhcopilot.backend"

if [[ ! -x "$VENV_PYTHON" ]]; then
  print -u2 "Не найден $VENV_PYTHON. Сначала создайте .venv и установите проект."
  exit 1
fi

mkdir -p "$PROJECT_DIR/runtime/logs" "$HOME/Library/LaunchAgents"
sed \
  -e "s|__PROJECT_DIR__|$PROJECT_DIR|g" \
  -e "s|__PYTHON__|$VENV_PYTHON|g" \
  "$TEMPLATE" > "$TARGET"

launchctl bootout "$SERVICE" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$TARGET"
launchctl enable "$SERVICE"

for _ in {1..20}; do
  if curl --silent --fail --max-time 1 http://127.0.0.1:8765/health >/dev/null; then
    print "HH Copilot установлен и работает: http://127.0.0.1:8765/health"
    exit 0
  fi
  sleep 0.5
done

print -u2 "Сервис установлен, но health check пока не отвечает."
print -u2 "Проверьте runtime/logs/launchd.stderr.log"
exit 1
