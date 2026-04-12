#!/bin/bash
set -euo pipefail

APP_DIR="/opt/poster_bot"
API_BASE="${API_BASE:-http://127.0.0.1:8000}"
TRIGGER_PATH="${TRIGGER_PATH:-/api/category-runs/trigger}"

cd "$APP_DIR"
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

LOGIN_PAYLOAD=$(python3 - <<'PY'
import json
import os

print(json.dumps({
    "username": os.getenv("DASHBOARD_ADMIN_USER", "admin"),
    "password": os.getenv("DASHBOARD_ADMIN_PASSWORD", ""),
}))
PY
)

TOKEN=$(curl -fsS -X POST "$API_BASE/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "$LOGIN_PAYLOAD" | python3 -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

curl -fsS -X POST "$API_BASE$TRIGGER_PATH" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"
