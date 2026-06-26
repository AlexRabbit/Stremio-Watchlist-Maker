#!/usr/bin/env bash
# Deploy Channel Organizer API on your VPS (isolated from other services).
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/stremio-channel-organizer}"
SERVICE_NAME="stremio-channel-organizer"
DEPLOY_USER="${DEPLOY_USER:-star}"

if [[ ! -f "${APP_DIR}/main.py" ]]; then
  echo "ERROR: ${APP_DIR}/main.py not found. Copy the project there first."
  exit 1
fi

echo "==> Stopping service if running..."
sudo systemctl stop "${SERVICE_NAME}" 2>/dev/null || true

echo "==> Python venv + dependencies..."
cd "${APP_DIR}"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

if [[ ! -f "${APP_DIR}/.env" ]]; then
  echo "==> Creating .env from deploy/env.example (edit BASE_URL before going live)"
  cp deploy/env.example "${APP_DIR}/.env"
fi

mkdir -p "${APP_DIR}/data" "${APP_DIR}/logs"

echo "==> Running tests..."
if [[ "${SKIP_TESTS:-0}" != "1" ]]; then
  PYTHONPATH=packages python -m pytest tests/ -q
else
  echo "SKIP_TESTS=1 — skipping pytest"
fi

echo "==> Installing systemd unit..."
sudo cp deploy/channel-organizer.service /etc/systemd/system/${SERVICE_NAME}.service
sudo sed -i "s|__APP_DIR__|${APP_DIR}|g" /etc/systemd/system/${SERVICE_NAME}.service
sudo sed -i "s|__DEPLOY_USER__|${DEPLOY_USER}|g" /etc/systemd/system/${SERVICE_NAME}.service
sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"
sleep 2
sudo systemctl --no-pager status "${SERVICE_NAME}" || true

echo ""
echo "==> Local health check (on the VPS):"
curl -fsS "http://127.0.0.1:7010/api/health" && echo "" || echo "Health check failed — see: journalctl -u ${SERVICE_NAME} -n 50"

echo ""
echo "Done. Point HTTPS reverse proxy at 127.0.0.1:7010 (see deploy/nginx-site.conf.example)."
