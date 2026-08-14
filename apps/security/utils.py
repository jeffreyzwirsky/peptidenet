"""Security helpers: spoof-resistant client IP, honeypot, rate limiting, audit."""
import functools
import json
import logging
import time

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse

from .models import SecurityEvent

log = logging.getLogger("security")

# Hidden form field name. A real user never fills it; bots that fill every input do.
HONEYPOT_FIELD = "company_website"


def client_ip(request):
    """Real client IP, spoof-resistant.

    nginx sets X-Real-IP from $remote_addr, and nginx's realip module only
    rewrites $remote_addr when the connection actually came from a verified
    Cloudflare range (/etc/nginx/conf.d/01-cloudflare-realip.conf on the box).
    A client therefore cannot forge this value, even by hitting the origin IP
    directly. CF-Connecting-IP is deliberately NOT trusted here: it is an
    ordinary request header any caller can set, which previously allowed
    rate-limit bypass and audit-trail poisoning (found + fixed live in the
    2026-08-10 production audit; this is the backport).

    Fallback: when behind N trusted proxies, take the (N+1)-th-from-right XFF
    entry so a spoofed left-most header can't win.
    """
    real = request.META.get("HTTP_X_REAL_IP")
    if real:
        return real.strip().split(",")[0].strip()
    trusted = int(getattr(settings, "TRUSTED_PROXY_COUNT", 0) or 0)
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if trusted and xff:
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        idx = len(parts) - trusted
        if 0 <= idx < len(parts):
            return parts[idx]
    return request.META.get("REMOTE_ADDR")


def log_event(request, kind, detail="", ip=None):
    """Write a security audit row.

    Still never raises into the request — an audit failure must not take a page
    down — but it no longer fails *silently*. A bare `except: pass` here is how
    the whole trail went dead for three days without a single symptom: a column
    added to the production table by hand (`country`, NOT NULL) made every
    insert raise, and nobody could have known. Now the failure is logged loudly
    enough to be found.
    """
    try:
        SecurityEvent.objects.create(
            kind=kind, ip=ip or client_ip(request),
            path=request.path[:300], detail=detail[:300],
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
            # Cloudflare gives us the origin country for free; it is the single
            # most useful field for reading a wall of bot-trap hits.
            country=(request.META.get("HTTP_CF_IPCOUNTRY", "") or "")[:2].upper(),
        )
    except Exception:  # never let auditing break a request — but never hide it
        log.exception("SECURITY AUDIT WRITE FAILED (kind=%s) — the audit trail "
                      "is not recording", kind)


def is_bot_honeypot(request):
    """True if the honeypot field was filled (a bot). Handles both form-encoded
    and JSON bodies. Logs the trip."""
    if request.method != "POST":
        return False
    val = request.POST.get(HONEYPOT_FIELD)
    if not val and "application/json" in (request.content_type or ""):
        try:
            val = (json.loads(request.body or "{}") or {}).get(HONEYPOT_FIELD)
        except (ValueError, TypeError):
            val = None
    if val:
        log_event(request, "honeypot", detail="honeypot field filled")
        return True
    return False


def _rate_key(request, scope):
    return f"rl:{scope}:{client_ip(request)}"


def rate_limit(scope, limit=20, window=60):
    """Per-IP fixed-window limiter (cache-backed). Every public endpoint attaches
    its own — the SMASH platforms have no default API rate limit, so this is
    opt-in per view. On exceed: 429 + audit event."""
    def deco(view):
        @functools.wraps(view)
        def wrapped(request, *a, **kw):
            key = _rate_key(request, scope)
            now = time.time()
            bucket = cache.get(key)
            if not bucket or now - bucket["start"] >= window:
                bucket = {"start": now, "count": 0}
            bucket["count"] += 1
            cache.set(key, bucket, timeout=window)
            if bucket["count"] > limit:
                log_event(request, "ratelimit", detail=f"{scope} > {limit}/{window}s")
                if request.headers.get("Content-Type", "").startswith("application/json") \
                        or request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return JsonResponse({"ok": False, "error": "Too many requests."}, status=429)
                return HttpResponse("Too many requests.", status=429)
            return view(request, *a, **kw)
        return wrapped
    return deco
