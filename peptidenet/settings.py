"""
Django settings for the peptidenet multi-site peptide platform.

One codebase serves every peptide domain, routed by Host header — mirrors the
SMASH lead-gen network (Django + gunicorn + nginx + ALLOWED_HOSTS on a
DigitalOcean droplet). Adding a domain = add a Site row (admin or `add_site`),
then regenerate nginx + hosts (`emit_nginx`, `emit_hosts`).
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env(key, default=None):
    return os.environ.get(key, default)


def env_bool(key, default=False):
    return str(env(key, default)).lower() in ("1", "true", "yes", "on")


SECRET_KEY = env("PEPTIDENET_SECRET_KEY", "dev-insecure-change-me-in-prod")
DEBUG = env_bool("PEPTIDENET_DEBUG", True)

# ALLOWED_HOSTS: in prod, set PEPTIDENET_HOSTS from `python manage.py emit_hosts`
# (comma-separated). Localhost is always allowed; DEBUG allows everything so
# host-routing can be tested with a Host header locally.
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]", "testserver"]
_extra_hosts = env("PEPTIDENET_HOSTS", "")
if _extra_hosts:
    ALLOWED_HOSTS += [h.strip() for h in _extra_hosts.split(",") if h.strip()]
if DEBUG:
    ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.catalog",
    "apps.stores",
    "apps.orders",
    "apps.leads",
    "apps.manage",
    "apps.comms",
    "apps.ai",
    "apps.security",
    "apps.blog",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Hardening headers (CSP etc.) + bot-trap logging:
    "apps.security.middleware.SecurityHeadersMiddleware",
    # Resolves request.site + request.theme from the Host header:
    "apps.stores.middleware.SiteMiddleware",
]

ROOT_URLCONF = "peptidenet.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.stores.context_processors.storefront",
            ],
        },
    },
]

WSGI_APPLICATION = "peptidenet.wsgi.application"

# SQLite for local dev; Postgres in prod (same as the lead system) via env.
if env("PEPTIDENET_DB_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("PEPTIDENET_DB_NAME", "peptidenet"),
            "USER": env("PEPTIDENET_DB_USER", "doadmin"),
            "PASSWORD": env("PEPTIDENET_DB_PASSWORD", ""),
            "HOST": env("PEPTIDENET_DB_HOST"),
            "PORT": env("PEPTIDENET_DB_PORT", "25060"),
            "OPTIONS": {"sslmode": env("PEPTIDENET_DB_SSLMODE", "require")},
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-ca"
TIME_ZONE = "America/Winnipeg"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Payment processor is intentionally stubbed until a provider is connected.
# When PEPTIDENET_PAYMENTS_LIVE flips on, wire the real gateway in
# apps/orders/payments.py. Orders are created as "pending" until then.
PAYMENTS_LIVE = env_bool("PEPTIDENET_PAYMENTS_LIVE", False)

# The theme used when a Site has no theme set, or for an unknown host in DEBUG.
DEFAULT_THEME = "biolabs"

# --- AI ---
# Storefront assistant + AI helpers. Inert (uses grounded stub answers) until
# AI_LIVE=1 and an Anthropic/OpenAI key is set. Every call is ledgered (AgentRun).
AI_LIVE = env_bool("PEPTIDENET_AI_LIVE", False)

# --- Security hardening ---
# Number of trusted reverse proxies in front (nginx=1, +Cloudflare=2). Used for
# spoof-resistant client-IP resolution (like the SMASH consent-IP fix).
TRUSTED_PROXY_COUNT = int(env("PEPTIDENET_TRUSTED_PROXIES", "0") or "0")
CONTENT_SECURITY_POLICY = env(
    "PEPTIDENET_CSP",
    "default-src 'self'; img-src 'self' data:; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'",
)
# In-process cache backs the rate limiter (fine for dev/single worker). Use Redis
# in production so limits are shared across gunicorn workers.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("PEPTIDENET_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
    if TRUSTED_PROXY_COUNT:
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# --- Comms / telephony (mirrors the SMASH Twilio + OpenAI + ElevenLabs stack) ---
# Everything is inert until COMMS_LIVE=1 AND the relevant provider key is set.
# Nothing sends texts, places calls, or spends money before then.
COMMS_LIVE = env_bool("PEPTIDENET_COMMS_LIVE", False)
TWILIO_ACCOUNT_SID = env("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = env("TWILIO_AUTH_TOKEN", "")
TWILIO_DEFAULT_FROM = env("TWILIO_DEFAULT_FROM", "")
OPENAI_API_KEY = env("OPENAI_API_KEY", "")          # Whisper transcription
ELEVENLABS_API_KEY = env("ELEVENLABS_API_KEY", "")  # TTS voice greetings
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", "")    # AI-drafted SMS replies
TELEPHONY_PUBLIC_HOST = env("PEPTIDENET_TELEPHONY_HOST", "")

SESSION_COOKIE_NAME = "peptidenet_sessionid"
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in env("PEPTIDENET_CSRF_ORIGINS", "").split(",") if o.strip()
]

# Admin lives at a non-default path in prod (set PEPTIDENET_ADMIN_PATH) so the
# default /admin/ scanner target isn't exposed. Always has a trailing slash and
# no leading slash. Defaults to "admin/" for local dev.
ADMIN_PATH = (env("PEPTIDENET_ADMIN_PATH", "admin/") or "admin/").strip("/") + "/"
