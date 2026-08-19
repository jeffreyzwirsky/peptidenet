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
./venv/bin/pip install --upgrade "pip==26.2.1"
./venv/bin/pip install --require-hashes -r requirements.txt

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
# The secrets file never needed to be readable by the service user: systemd
# reads EnvironmentFile as root before dropping privileges. 0644 (the default
# umask) put SECRET_KEY and the Postgres password in reach of every local
# account and of any file-read bug in the app itself.
chmod 600 "$APP/.env"
chown root:root "$APP/.env"
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
# Source and secrets are deployer-owned. The web worker can write only the two
# runtime locations it actually needs: the shared rate/cache directory and AI
# blog images. Recursive www-data ownership previously made an app compromise
# persistent by allowing it to rewrite both source and .env.
chown -R root:root "$APP"
chmod 600 "$APP/.env"
install -d -o www-data -g www-data -m 0700 /var/cache/peptidenet
install -d -o www-data -g www-data -m 0750 "$APP/static/blog"
chown -R www-data:www-data "$APP/static/blog"
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
ufw default deny incoming
ufw default allow outgoing
# 80/443 are opened to Cloudflare's published ranges only, never to the world.
# Rebuilding with `ufw allow 'Nginx Full'` is what silently reopened the
# Host-header bypass: the origin answers a request that carries a real Host
# header, so an attacker holding IP + hostname skips the WAF, the edge rate
# limits and the bot rules entirely. Closed on the live box 2026-08-15; this
# block is why a rebuild does not undo it.
#
# Fail-safe: if the range list cannot be fetched or looks truncated we fall
# back to the open rule and say so loudly. An unreachable site is a worse
# outcome than a reachable one that still needs hardening, and a silent
# half-applied allowlist is the worst of the three.
CF_IPS=/run/cf-ips.$$
{ curl -fsS -m 20 https://www.cloudflare.com/ips-v4; echo; \
  curl -fsS -m 20 https://www.cloudflare.com/ips-v6; echo; } \
  | tr -d '\r' | grep -E '^[0-9a-fA-F]' | sort -u > "$CF_IPS" || true
if [ "$(grep -c . "$CF_IPS" 2>/dev/null || echo 0)" -ge 20 ]; then
  while read -r cidr; do
    ufw allow proto tcp from "$cidr" to any port 80,443 comment 'cloudflare edge' >/dev/null || true
  done < "$CF_IPS"
  ufw delete allow 'Nginx Full' >/dev/null 2>&1 || true
  echo "==> ufw: 80/443 restricted to $(grep -c . "$CF_IPS") Cloudflare ranges"
  # Same list drives real_ip, so the two can never disagree. Without this file
  # every client IP the app records is a Cloudflare edge IP -- which breaks
  # rate limiting and lets a bot-trap ban take out an entire edge.
  { echo "# generated by deploy.sh -- do not hand-edit; re-run deploy.sh"
    sed 's/^/set_real_ip_from /; s/$/;/' "$CF_IPS"
    echo "real_ip_header CF-Connecting-IP;"; } > /etc/nginx/conf.d/01-cloudflare-realip.conf
else
  echo "!! Could not fetch Cloudflare ranges (got $(grep -c . "$CF_IPS" 2>/dev/null || echo 0), need >=20)." >&2
  echo "!! Refusing to open the origin to the world. Re-run deploy.sh when Cloudflare's list is reachable." >&2
  rm -f "$CF_IPS"
  yes | ufw enable || true
  exit 1
fi
rm -f "$CF_IPS"
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
install -d -m 0700 /var/backups/peptidenet
cat > /etc/cron.daily/peptidenet-backup <<EOF
#!/usr/bin/env bash
# pipefail matters: without it, a failing pg_dump piped into gzip still exits 0
# and leaves a perfectly valid gzip of a truncated/empty dump -- a "backup"
# that only fails you at restore time. Found 2026-08-10.
set -euo pipefail
# 0600, not 0644. The dump is the entire database; it was world-readable on the
# box until 2026-08-15 because this script ran at the default umask.
umask 077
TS="\$(date +%F)"
OUT="/var/backups/peptidenet/${DB_NAME}-\$TS.sql.gz"
rm -f "\$OUT.partial"
sudo -u postgres pg_dump ${DB_NAME} | gzip > "\$OUT.partial"
# Verify before it becomes the backup: valid gzip, and it actually contains a
# schema. grep -c (not -q) consumes the whole stream -- -q exits on first match
# and the resulting SIGPIPE reads as a failed pipeline under pipefail.
gzip -t "\$OUT.partial"
[ "\$(gzip -dc "\$OUT.partial" | grep -c 'CREATE TABLE')" -gt 0 ]
mv -f "\$OUT.partial" "\$OUT"
date -u +%FT%TZ > /var/backups/peptidenet/LAST_SUCCESS
find /var/backups/peptidenet -name '*.sql.gz' -mtime +14 -delete
find /var/backups/peptidenet -name '*.partial' -mtime +1 -delete
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
