#!/usr/bin/env bash
#
# Apply the latest code to the running site — safe to re-run any time.
#
# Usage (on the droplet, as root):
#   cd /var/www/peptidenet && git pull && bash scripts/update.sh you@email.com
#
# (git pull is done in the invocation, NOT here, so this script isn't rewritten
# underneath itself mid-run.)
#
set -euo pipefail
CERT_EMAIL="${1:-}"
APP=/var/www/peptidenet
cd "$APP"

echo "==> Python deps"
./venv/bin/pip install -r requirements.txt -q

echo "==> Load env + migrate + static"
set -a; source "$APP/.env"; set +a
./venv/bin/python manage.py migrate
./venv/bin/python manage.py collectstatic --noinput

echo "==> Regenerate nginx + ensure default-deny catch-all + re-apply TLS"
./venv/bin/python manage.py emit_nginx > /etc/nginx/sites-available/peptidenet
# Default-deny (bare IP / unknown Host -> nginx 444). Standalone file, idempotent.
apt-get install -y ssl-cert >/dev/null 2>&1 || true
printf 'server{listen 80 default_server;listen [::]:80 default_server;server_name _;return 444;}\nserver{listen 443 ssl default_server;listen [::]:443 ssl default_server;server_name _;ssl_certificate /etc/ssl/certs/ssl-cert-snakeoil.pem;ssl_certificate_key /etc/ssl/private/ssl-cert-snakeoil.key;return 444;}\n' > /etc/nginx/conf.d/00-default-deny.conf
# Re-issue/re-install certs per-domain so a domain whose DNS hasn't propagated
# yet is skipped instead of failing the whole batch. Existing valid certs are
# reused (no new issuance, no rate-limit hit) and their 443 block is re-injected.
if [ -n "$CERT_EMAIL" ]; then
  for d in $(./venv/bin/python manage.py emit_hosts | tr ',' ' '); do
    certbot --nginx --non-interactive --agree-tos -m "$CERT_EMAIL" --redirect \
      -d "$d" || echo "!! skipped $d (DNS not ready yet — re-run later)"
  done
fi

echo "==> Automatic OS security updates (unattended-upgrades)"
apt-get install -y unattended-upgrades >/dev/null 2>&1 || true
unattended-upgrade -d >/dev/null 2>&1 || true
systemctl enable --now unattended-upgrades >/dev/null 2>&1 || true

echo "==> Reload web stack"
nginx -t && systemctl reload nginx
systemctl restart peptidenet
echo "==> update.sh DONE."
