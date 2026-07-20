import secrets

from django.conf import settings

from .utils import log_event

# Strict, XSS-resistant CSP for public pages. `{nonce}` is filled per request so
# inline <script> tags carry a matching nonce and script-src needs no
# 'unsafe-inline'. Styles keep 'unsafe-inline' (inline style="" attrs are used
# throughout the themes; the Lighthouse XSS audit only requires a locked-down
# script-src + object-src + base-uri).
CSP_STRICT = (
    "default-src 'self'; base-uri 'none'; object-src 'none'; "
    "img-src 'self' data:; "
    "style-src 'self' 'unsafe-inline'; "
    "font-src 'self'; "
    # Google's recommended strict CSP: modern browsers use the nonce +
    # strict-dynamic; 'https:' and 'unsafe-inline' are ignored fallbacks for
    # older browsers. Every <script> we emit carries the matching nonce.
    "script-src 'nonce-{nonce}' 'strict-dynamic' https: 'unsafe-inline'; "
    "connect-src 'self'; frame-ancestors 'none'; form-action 'self'; "
    "upgrade-insecure-requests"
)
# The authenticated control panel / admin use a few inline handlers; they're not
# indexed or Lighthouse-scored, so allow inline there.
CSP_RELAXED = (
    "default-src 'self'; base-uri 'self'; object-src 'none'; "
    "img-src 'self' data:; "
    "style-src 'self' 'unsafe-inline'; "
    "font-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "connect-src 'self'; frame-ancestors 'none'; form-action 'self'"
)

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

        # Per-request CSP nonce — available to templates as {{ request.csp_nonce }}.
        nonce = secrets.token_urlsafe(16)
        request.csp_nonce = nonce

        response = self.get_response(request)
        response.setdefault("X-Content-Type-Options", "nosniff")
        response.setdefault("X-Frame-Options", "DENY")
        response.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")

        admin_path = "/" + getattr(settings, "ADMIN_PATH", "admin/").strip("/")
        relaxed = p.startswith("/manage") or p.startswith(admin_path)
        csp = CSP_RELAXED if relaxed else CSP_STRICT.format(nonce=nonce)
        # Always set (override any inherited value) so the nonce matches this response.
        response["Content-Security-Policy"] = csp
        return response
