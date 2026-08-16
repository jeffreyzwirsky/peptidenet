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
# Default the cert email rather than allowing empty: update.sh regenerates the
# nginx config from emit_nginx (port-80 blocks only), and it is the certbot loop
# below that re-injects every 443 server block. Run with the email omitted and
# the loop is skipped — which took all eight sites down (Cloudflare 520s) for
# ~35 minutes on 2026-08-14 until re-run with the email. Never again.
CERT_EMAIL="${1:-jeff@smashscrap.ca}"
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

# --- Post-deploy verification -------------------------------------------
# Deliberately AFTER the restart and deliberately non-fatal: the code is
# already live, so failing the script here would only hide the report. What
# this buys is that nobody has to remember to run it, and a regression is
# named in the deploy output instead of being found days later by a human who
# happened to look. Every check here has caught something real.
echo "==> Post-deploy verification"
"$APP/venv/bin/python" manage.py compliance_check --quiet || \
    echo "!! compliance_check FAILED — see above. A claim may be live."
"$APP/venv/bin/python" manage.py rescan_posts | tail -2 || true
# What a CALLER actually hears — the one layer a code diff cannot show. A
# pre-generated greeting mp3 is played instead of <Say> and silently bypasses
# every text fix in voice.py, so "I changed the greeting" can be true and change
# nothing on the line.
"$APP/venv/bin/python" manage.py voice_check || \
    echo "!! voice_check FAILED — callers may not be hearing what the code says."
"$APP/venv/bin/python" manage.py healthcheck --quick --no-email | tail -15 || \
    echo "!! healthcheck FAILED — see above."

echo "==> update.sh DONE."
