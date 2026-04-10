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

exec "$PYTHON_BIN" "$IMPORTER"
