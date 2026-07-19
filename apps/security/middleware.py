from django.conf import settings

from .utils import log_event

# Common paths that only vulnerability scanners / bots request. Hitting one is a
# strong bot signal — log it (a fail2ban jail can tail these) and 404 fast.
TRAP_PREFIXES = (
    "/wp-login", "/wp-admin", "/xmlrpc.php", "/.env", "/.git",
    "/vendor/", "/phpmyadmin", "/administrator", "/.aws", "/config.php",
)


class SecurityHeadersMiddleware:
    """Adds hardening headers to every response + logs bot-trap hits.
    CSP is intentionally permissive enough for the inline styles/handlers used by
    the themes; tighten per deployment."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        p = request.path.lower()
        if any(p.startswith(x) for x in TRAP_PREFIXES):
            log_event(request, "bot_trap", detail=f"trap path {request.path}")

        response = self.get_response(request)
        response.setdefault("X-Content-Type-Options", "nosniff")
        response.setdefault("X-Frame-Options", "DENY")
        response.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if getattr(settings, "CONTENT_SECURITY_POLICY", ""):
            response.setdefault("Content-Security-Policy", settings.CONTENT_SECURITY_POLICY)
        return response
