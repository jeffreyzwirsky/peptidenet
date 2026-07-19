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
nginx -t && systemctl reload nginx

echo "==> firewall"
ufw allow OpenSSH || true
ufw allow 'Nginx Full' || true
yes | ufw enable || true

echo "==> TLS certs (Let's Encrypt) for every domain"
DOMAIN_ARGS="$(echo "$HOSTS" | tr ',' '\n' | sed 's#^#-d #' | paste -sd' ' -)"
if [ -n "$CERT_EMAIL" ]; then
  certbot --nginx --non-interactive --agree-tos -m "$CERT_EMAIL" \
    --redirect $DOMAIN_ARGS || \
    echo "!! certbot failed — check that all domains' DNS point here + have propagated, then re-run: certbot --nginx $DOMAIN_ARGS"
else
  echo "!! No email passed — skipping certbot. Run: certbot --nginx $DOMAIN_ARGS -m you@email.com --agree-tos"
fi

echo "==> DONE. App: gunicorn(127.0.0.1:8001) behind nginx. Admin: /admin (create a superuser:)"
echo "    cd $APP && ./venv/bin/python manage.py createsuperuser"
