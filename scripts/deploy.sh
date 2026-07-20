#!/usr/bin/env bash
#
# One-shot production deploy for peptidenet on a fresh Ubuntu 22.04/24.04 droplet.
# Installs Python + nginx + Postgres + gunicorn + certbot, sets up the app, and
# issues Let's Encrypt certs for every domain in the Site table.
#
# Run as root on the droplet AFTER the code is at /var/www/peptidenet AND the
# domains' DNS A-records point at this droplet's IP (certbot needs that).
#
#   sudo bash /var/www/peptidenet/scripts/deploy.sh you@email.com
#
set -euo pipefail
CERT_EMAIL="${1:-}"
APP=/var/www/peptidenet
DB_NAME=peptidenet
DB_USER=peptidenet
DB_PASS="$(openssl rand -hex 16)"
SECRET="$(openssl rand -hex 32)"
# Non-default admin path so /admin/ isn't a standing scanner target.
ADMIN_PATH="ops-$(openssl rand -hex 4)/"

echo "==> Swap (1GB droplet needs headroom for pip builds + Postgres)"
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 600 /swapfile; mkswap /swapfile; swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

echo "==> System packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3-venv python3-pip python3-dev build-essential \
    nginx postgresql postgresql-contrib libpq-dev certbot python3-certbot-nginx git curl

echo "==> OS security updates + automatic security patching (unattended-upgrades)"
apt-get install -y unattended-upgrades || true
# Apply any pending security updates now, then keep them coming automatically.
unattended-upgrade -d >/dev/null 2>&1 || true
systemctl enable --now unattended-upgrades || true

echo "==> Postgres database"
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';"
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"

echo "==> Python venv + deps"
cd "$APP"
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
./venv/bin/pip install "psycopg[binary]" gunicorn

echo "==> .env"
# ALLOWED_HOSTS is filled from the Site table after seeding (below).
cat > "$APP/.env" <<EOF
PEPTIDENET_DEBUG=0
PEPTIDENET_SECRET_KEY=$SECRET
PEPTIDENET_DB_HOST=127.0.0.1
PEPTIDENET_DB_NAME=$DB_NAME
PEPTIDENET_DB_USER=$DB_USER
PEPTIDENET_DB_PASSWORD=$DB_PASS
PEPTIDENET_DB_PORT=5432
PEPTIDENET_DB_SSLMODE=disable
PEPTIDENET_TRUSTED_PROXIES=1
PEPTIDENET_SSL_REDIRECT=1
PEPTIDENET_ADMIN_PATH=$ADMIN_PATH
EOF
set -a; source "$APP/.env"; set +a

echo "==> Migrate + seed"
./venv/bin/python manage.py migrate
./venv/bin/python manage.py seed_catalog
./venv/bin/python manage.py seed_sites
./venv/bin/python manage.py collectstatic --noinput

# Now that Sites exist, compute ALLOWED_HOSTS + CSRF origins and append.
HOSTS="$(./venv/bin/python manage.py emit_hosts)"
CSRF="$(echo "$HOSTS" | tr ',' '\n' | sed 's#^#https://#' | paste -sd, -)"
{ echo "PEPTIDENET_HOSTS=$HOSTS"; echo "PEPTIDENET_CSRF_ORIGINS=$CSRF"; } >> "$APP/.env"

echo "==> Security self-check (Django deploy checklist)"
set -a; source "$APP/.env"; set +a
./venv/bin/python manage.py check --deploy || \
  echo "!! 'check --deploy' reported items above — review before/after go-live."

echo "==> gunicorn service"
cp "$APP/deploy/gunicorn.service" /etc/systemd/system/peptidenet.service
chown -R www-data:www-data "$APP"
systemctl daemon-reload
systemctl enable --now peptidenet
systemctl restart peptidenet

echo "==> nginx"
./venv/bin/python manage.py emit_nginx > /etc/nginx/sites-available/peptidenet
ln -sf /etc/nginx/sites-available/peptidenet /etc/nginx/sites-enabled/peptidenet
rm -f /etc/nginx/sites-enabled/default
# Default-deny catch-all: the bare IP or any unknown Host gets nginx 444 (silent
# close) — the server reveals nothing. Standalone file so regenerating the
# per-site config can never create a duplicate default_server.
apt-get install -y ssl-cert >/dev/null 2>&1 || true
printf 'server{listen 80 default_server;listen [::]:80 default_server;server_name _;return 444;}\nserver{listen 443 ssl default_server;listen [::]:443 ssl default_server;server_name _;ssl_certificate /etc/ssl/certs/ssl-cert-snakeoil.pem;ssl_certificate_key /etc/ssl/private/ssl-cert-snakeoil.key;return 444;}\n' > /etc/nginx/conf.d/00-default-deny.conf
nginx -t && systemctl reload nginx

echo "==> firewall"
ufw allow OpenSSH || true
ufw allow 'Nginx Full' || true
yes | ufw enable || true

echo "==> fail2ban (SSH brute-force protection)"
apt-get install -y fail2ban || true
cat > /etc/fail2ban/jail.local <<'EOF'
[sshd]
enabled  = true
maxretry = 5
findtime = 10m
bantime  = 1h
EOF
systemctl enable --now fail2ban || true
systemctl restart fail2ban || true

echo "==> Daily Postgres backup (14-day retention)"
mkdir -p /var/backups/peptidenet
cat > /etc/cron.daily/peptidenet-backup <<EOF
#!/usr/bin/env bash
set -e
TS="\$(date +%F)"
sudo -u postgres pg_dump ${DB_NAME} | gzip > "/var/backups/peptidenet/${DB_NAME}-\$TS.sql.gz"
find /var/backups/peptidenet -name '*.sql.gz' -mtime +14 -delete
EOF
chmod +x /etc/cron.daily/peptidenet-backup

echo "==> TLS certs (Let's Encrypt) for every domain"
DOMAIN_ARGS="$(echo "$HOSTS" | tr ',' '\n' | sed 's#^#-d #' | paste -sd' ' -)"
if [ -n "$CERT_EMAIL" ]; then
  certbot --nginx --non-interactive --agree-tos -m "$CERT_EMAIL" \
    --redirect $DOMAIN_ARGS || \
    echo "!! certbot failed — check that all domains' DNS point here + have propagated, then re-run: certbot --nginx $DOMAIN_ARGS"
else
  echo "!! No email passed — skipping certbot. Run: certbot --nginx $DOMAIN_ARGS -m you@email.com --agree-tos"
fi

echo "==> DONE. App: gunicorn(127.0.0.1:8001) behind nginx."
echo "    ADMIN URL (custom path — save this): https://<yourdomain>/${ADMIN_PATH}"
echo "    Control panel: https://<yourdomain>/manage/"
echo "    Create your login:  cd $APP && ./venv/bin/python manage.py createsuperuser"
echo "    fail2ban: active (sshd) · DB backups: /var/backups/peptidenet (daily, 14d)"
