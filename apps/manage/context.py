"""Template context for the console — exposes the current namespace so one set
of templates renders correctly under both /manage/ and /portal/. Also exposes
the per-deploy asset version used to cache-bust CSS/JS URLs site-wide."""
from django.conf import settings


def console(request):
    ns = "manage"
    rm = getattr(request, "resolver_match", None)
    if rm and getattr(rm, "namespace", ""):
        ns = rm.namespace
    return {
        "cns": ns,                    # "manage" or "portal" — use in {% url cns|add:':x' %}
        "is_admin_console": ns == "manage",
        "is_staff_portal": ns == "portal",
        "asset_v": settings.ASSET_VERSION,   # ?v= cache-buster for CSS/JS
    }
