from django.conf import settings
from django.db.utils import OperationalError, ProgrammingError

from .models import Site

# Simple in-process cache of host -> Site id. Cleared on any Site save
# (see signals below) so newly added domains resolve without a restart.
_HOST_CACHE = {}


def _lookup_site(host):
    host = (host or "").split(":")[0].lower().strip()
    if not host:
        return None
    if host in _HOST_CACHE:
        cached = _HOST_CACHE[host]
        return Site.objects.filter(pk=cached).first() if cached else None

    site = Site.objects.filter(domain=host, is_active=True).first()
    if site is None:
        # Match aliases / www. variants.
        for s in Site.objects.filter(is_active=True):
            if host in [h.lower() for h in s.all_hostnames()]:
                site = s
                break
    _HOST_CACHE[host] = site.pk if site else None
    return site


def clear_host_cache(*args, **kwargs):
    _HOST_CACHE.clear()


class SiteMiddleware:
    """Resolve request.site + request.theme from the Host header."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.site = None
        request.theme = settings.DEFAULT_THEME
        try:
            site = _lookup_site(request.get_host())
        except (OperationalError, ProgrammingError):
            site = None  # DB not migrated yet
        if site is None and settings.DEBUG:
            # Dev convenience: ?site=<domain> to preview any store on localhost.
            # Sticky: remember the choice in the session so click-through stays on
            # the same store (prod uses the real Host header, so this never runs).
            override = request.GET.get("site")
            if override:
                site = Site.objects.filter(domain=override).first()
                if site:
                    request.session["dev_site"] = override
            if site is None and request.session.get("dev_site"):
                site = Site.objects.filter(domain=request.session["dev_site"]).first()
            if site is None:
                site = Site.objects.filter(is_active=True).first()
        if site is not None:
            request.site = site
            request.theme = site.theme or settings.DEFAULT_THEME
        return self.get_response(request)
