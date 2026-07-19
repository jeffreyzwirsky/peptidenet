#!/usr/bin/env bash
# One-command launchable demo: migrate, seed everything, create admin, run server.
set -e
cd "$(dirname "$0")/.."
python manage.py migrate
python manage.py seed_catalog
python manage.py seed_sites
python manage.py seed_demo
python manage.py seed_comms_demo
python - <<'PY'
import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE","peptidenet.settings"); django.setup()
from django.contrib.auth import get_user_model
U=get_user_model()
if not U.objects.filter(username="admin").exists():
    U.objects.create_superuser("admin","admin@peptidenet.test","Test1234!")
    print("Created admin / Test1234!")
PY
echo
echo "================================================================"
echo " peptidenet is seeded. Starting server on http://127.0.0.1:8000"
echo "  Storefronts (send a Host header, or use ?site=<domain> in DEBUG):"
echo "    http://127.0.0.1:8000/?site=smashfat.ca   (or biolabs, neon, prairie…)"
echo "  Control panel:  http://127.0.0.1:8000/manage/   (admin / Test1234!)"
echo "  SEO:  /robots.txt  /sitemap.xml  /llms.txt"
echo "  Comms webhooks:  /webhooks/twilio/{sms,voice,recording}/"
echo "================================================================"
python manage.py runserver 127.0.0.1:8000
