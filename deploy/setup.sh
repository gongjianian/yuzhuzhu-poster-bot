#!/bin/bash
set -euo pipefail

APP_DIR="/opt/poster_bot"
SERVICE_USER="ubuntu"
SERVICE_GROUP="ubuntu"
VENV_DIR="$APP_DIR/venv"
PIP_INDEX_URL="https://mirrors.cloud.tencent.com/pypi/simple"
NPM_REGISTRY="https://registry.npmmirror.com"
SERVICE_FILE="/etc/systemd/system/poster-dashboard.service"
NGINX_SITE="/etc/nginx/sites-available/poster-dashboard"
NGINX_ENABLED="/etc/nginx/sites-enabled/poster-dashboard"

if [ "$(id -u)" -ne 0 ]; then
  echo "Please run deploy/setup.sh as root."
  exit 1
fi

echo "=== Deploying poster dashboard ==="

apt update
apt install -y python3-venv python3-pip nodejs npm nginx curl

mkdir -p "$APP_DIR/data" "$APP_DIR/logs" "$APP_DIR/assets/products"
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$APP_DIR/data" "$APP_DIR/logs" "$APP_DIR/assets"

if [ ! -d "$VENV_DIR" ]; then
  sudo -u "$SERVICE_USER" python3 -m venv "$VENV_DIR"
fi

sudo -u "$SERVICE_USER" env PIP_INDEX_URL="$PIP_INDEX_URL" "$VENV_DIR/bin/pip" install --upgrade pip
sudo -u "$SERVICE_USER" env PIP_INDEX_URL="$PIP_INDEX_URL" "$VENV_DIR/bin/pip" install -r "$APP_DIR/requirements.txt"

if [ ! -f "$APP_DIR/static/index.html" ]; then
  echo "Static bundle missing, building frontend..."
  pushd "$APP_DIR/frontend" >/dev/null
  sudo -u "$SERVICE_USER" env npm_config_registry="$NPM_REGISTRY" npm install
  sudo -u "$SERVICE_USER" env npm_config_registry="$NPM_REGISTRY" npm run build
  popd >/dev/null
fi

if [ ! -f "$APP_DIR/.env" ]; then
  echo "Missing $APP_DIR/.env. Create it before running deployment."
  exit 1
fi
chmod 600 "$APP_DIR/.env"
chown "$SERVICE_USER:$SERVICE_GROUP" "$APP_DIR/.env"

touch "$APP_DIR/logs/systemd.log"
chown "$SERVICE_USER:$SERVICE_GROUP" "$APP_DIR/logs/systemd.log"

install -m 644 "$APP_DIR/deploy/poster-dashboard.service" "$SERVICE_FILE"
systemctl daemon-reload
systemctl enable poster-dashboard

install -m 644 "$APP_DIR/deploy/nginx.conf" "$NGINX_SITE"
ln -sfn "$NGINX_SITE" "$NGINX_ENABLED"
if [ -L /etc/nginx/sites-enabled/default ] || [ -f /etc/nginx/sites-enabled/default ]; then
  rm -f /etc/nginx/sites-enabled/default
fi
nginx -t
systemctl reload nginx

systemctl restart poster-dashboard

echo "=== Deployment complete ==="
echo "Visit: http://$(hostname -I | awk '{print $1}')/"
echo "Cron example:"
echo "0 8 * * * /opt/poster_bot/deploy/cron_trigger.sh >> /opt/poster_bot/logs/cron.log 2>&1"
