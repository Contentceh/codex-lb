#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
IMPORTER="$SCRIPT_DIR/session_importer_from_har.py"
SESSIONS_DIR="$SCRIPT_DIR/sessions"

mkdir -p "$SESSIONS_DIR"

if [[ $# -gt 0 ]]; then
  exec "$PYTHON_BIN" "$IMPORTER" "$@"
fi

echo "Импорт сессии для codex-lb"
echo "1) HAR файл"
echo "2) JSON с https://chatgpt.com/api/auth/session"
read -r -p "Выбор [1/2] (по умолчанию 1): " choice
choice=${choice:-1}

case "$choice" in
  1)
    read -r -p "Путь к HAR (Enter = единственный *.har в ./sessions): " fpath
    if [[ -n "${fpath:-}" ]]; then
      exec "$PYTHON_BIN" "$IMPORTER" "$fpath"
    else
      exec "$PYTHON_BIN" "$IMPORTER"
    fi
    ;;
  2)
    read -r -p "Путь к JSON (Enter = единственный *.json кроме auth_*.json в ./sessions): " fpath
    if [[ -n "${fpath:-}" ]]; then
      exec "$PYTHON_BIN" "$IMPORTER" --from-session-json "$fpath"
    else
      exec "$PYTHON_BIN" "$IMPORTER" --from-session-json
    fi
    ;;
  *)
    echo "Неизвестный выбор: $choice" >&2
    exit 1
    ;;
esac
