"""Security helpers: spoof-resistant client IP, honeypot, rate limiting, audit."""
import functools
import json
import time

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse

from .models import SecurityEvent

# Hidden form field name. A real user never fills it; bots that fill every input do.
HONEYPOT_FIELD = "company_website"


def client_ip(request):
    """Real client IP. When behind N trusted proxies, take the (N+1)-th-from-right
    XFF entry so a spoofed left-most header can't win. Mirrors the SMASH consent-IP
    fix (record the customer's real IP, spoof-resistant)."""
    trusted = int(getattr(settings, "TRUSTED_PROXY_COUNT", 0) or 0)
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if trusted and xff:
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        idx = len(parts) - trusted
        if 0 <= idx < len(parts):
            return parts[idx]
    return request.META.get("REMOTE_ADDR")


def log_event(request, kind, detail="", ip=None):
    try:
        SecurityEvent.objects.create(
            kind=kind, ip=ip or client_ip(request),
            path=request.path[:300], detail=detail[:300],
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
        )
    except Exception:  # never let auditing break a request
        pass


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
