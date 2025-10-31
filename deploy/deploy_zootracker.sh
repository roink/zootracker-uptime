#!/usr/bin/env bash
# deploy/deploy_zootracker.sh
# ——————————————————————————————
# Run from your project root. Pushes the code & config to the remote VM,
# sets up Python, builds & deploys frontend, configures systemd/nginx, and
# obtains a Let's Encrypt cert.

set -euo pipefail

REMOTE_HOST="${1:?Usage: $0 <remote-ip> <domain>}"
DOMAIN="${2:?Usage: $0 <remote-ip> <domain>}"

REMOTE_USER="philipp"
SSH_TARGET="${REMOTE_USER}@${REMOTE_HOST}"
APP_DIR="/opt/zoo_tracker"
WEB_ROOT="/var/www/zootracker"
DEPLOY_SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "${DEPLOY_SCRIPTS_DIR}")"

echo "➤ Installing system packages on remote…"
ssh "${SSH_TARGET}" <<'EOF'
  sudo apt update -y
  sudo apt install -y nginx postgresql postgresql-contrib \
                      python3-venv python3-pip \
                      nodejs npm certbot python3-certbot-nginx openssl rsync
EOF

echo "➤ Generating DB credentials locally…"
DB_PASS=$(openssl rand -base64 24)
SECRET_KEY=$(openssl rand -hex 32)

echo "➤ Creating database & user on remote…"
ssh "${SSH_TARGET}" <<EOF
  sudo -u postgres psql <<PSQL
  CREATE USER zoo_user WITH PASSWORD '${DB_PASS}';
  CREATE DATABASE zoo_db OWNER zoo_user;
  PSQL
EOF

echo "➤ Rsync project to remote ${APP_DIR}…"
# Exclude venv, .git, node_modules, caches, tests, logs
rsync -a --delete \
  --exclude 'venv' \
  --exclude '.git' \
  --exclude 'frontend/node_modules' \
  --exclude '__pycache__' \
  --exclude 'app.log' \
  --exclude 'tests' \
  "${PROJECT_ROOT}/" \
  "${SSH_TARGET}:${APP_DIR}/"

echo "➤ Setting up Python environment on remote…"
ssh "${SSH_TARGET}" <<EOF
  cd "${APP_DIR}"
  sudo chown -R ${REMOTE_USER}:${REMOTE_USER} "${APP_DIR}"
  python3 -m venv venv
  venv/bin/pip install --upgrade pip
  venv/bin/pip install -r requirements.txt
EOF

echo "➤ Pushing .env to remote…"
TMP_ENV=\$(mktemp)
cat > "\${TMP_ENV}" <<ENV
DATABASE_URL=postgresql+psycopg_async://zoo_user:${DB_PASS}@localhost:5432/zoo_db
SECRET_KEY=${SECRET_KEY}
ENV
scp "\${TMP_ENV}" "${SSH_TARGET}:${APP_DIR}/.env"
ssh "${SSH_TARGET}" "sudo chown root:www-data ${APP_DIR}/.env && sudo chmod 640 ${APP_DIR}/.env"
rm "\${TMP_ENV}"

echo "➤ Building frontend locally…"
pushd "${PROJECT_ROOT}/frontend" >/dev/null
npm install
npm run build
popd >/dev/null

echo "➤ Uploading frontend to ${WEB_ROOT}…"
ssh "${SSH_TARGET}" "sudo mkdir -p ${WEB_ROOT} && sudo chown www-data:www-data ${WEB_ROOT}"
rsync -a --delete "${PROJECT_ROOT}/frontend/dist/" "${SSH_TARGET}:${WEB_ROOT}/"
ssh "${SSH_TARGET}" "sudo chown -R www-data:www-data ${WEB_ROOT}"

echo "➤ Copying systemd & nginx configs…"
scp "${DEPLOY_SCRIPTS_DIR}/zoo_tracker.service" "${SSH_TARGET}:/etc/systemd/system/zoo_tracker.service"
scp "${DEPLOY_SCRIPTS_DIR}/zoo_tracker.nginx"  "${SSH_TARGET}:/etc/nginx/sites-available/zoo_tracker"

echo "➤ Enabling and restarting services on remote…"
ssh "${SSH_TARGET}" <<EOF
  sudo systemctl daemon-reload
  sudo systemctl enable --now zoo_tracker
  sudo ln -sf /etc/nginx/sites-available/zoo_tracker /etc/nginx/sites-enabled/
  sudo nginx -t && sudo systemctl reload nginx
  sudo certbot --non-interactive --agree-tos --nginx -d ${DOMAIN} -m admin@${DOMAIN}
EOF

echo "✅ Deployment complete!"
echo "   • DB password: ${DB_PASS}"
echo "   • SECRET_KEY:  ${SECRET_KEY}"

