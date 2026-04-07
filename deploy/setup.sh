#!/bin/bash
set -euo pipefail

APP_DIR="/opt/poster_bot"

echo "=== Deploying poster dashboard ==="

apt update
apt install -y python3-venv python3-pip nginx curl

cd "$APP_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

mkdir -p data logs assets/products

cp deploy/nginx.conf /etc/nginx/sites-available/poster-dashboard
ln -sf /etc/nginx/sites-available/poster-dashboard /etc/nginx/sites-enabled/poster-dashboard
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

cp deploy/poster-dashboard.service /etc/systemd/system/poster-dashboard.service
systemctl daemon-reload
systemctl enable poster-dashboard
systemctl restart poster-dashboard

echo "=== Deployment complete ==="
echo "App directory: $APP_DIR"
echo "Visit: http://$(hostname -I | awk '{print $1}')/"
