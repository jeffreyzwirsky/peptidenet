"""Access control for the console.

The SAME views are mounted twice (see peptidenet/urls.py):
  * /manage/  → namespace "manage"  → OWNER (superuser) admin side.
  * /portal/  → namespace "portal"  → walled STAFF side.

`console_required` reads the current URL namespace and enforces the right rule,
so one decorator guards both mounts. Staff accounts are is_staff=False, so they
are automatically locked out of the Django admin — the portal is their only door.
"""
from functools import wraps

from django.shortcuts import redirect
from django.urls import reverse

PORTAL_GROUP = "Portal Staff"


def in_portal_group(user):
    return user.groups.filter(name=PORTAL_GROUP).exists()


def portal_allowed(user):
    """May use the STAFF portal (/portal/): superuser or Portal Staff group."""
    return bool(
        user.is_authenticated and user.is_active
        and (user.is_superuser or in_portal_group(user))
    )


def admin_allowed(user):
    """May use the OWNER admin (/manage/): superuser only."""
    return bool(user.is_authenticated and user.is_active and user.is_superuser)


def console_required(view):
    """Guard a console view based on which mount it was reached through."""
    @wraps(view)
    def _wrapped(request, *args, **kwargs):
        ns = getattr(request.resolver_match, "namespace", "") or "manage"
        allowed = admin_allowed if ns == "manage" else portal_allowed
        if not allowed(request.user):
            login_url = reverse(f"{ns}:login")
            return redirect(f"{login_url}?next={request.path}")
        return view(request, *args, **kwargs)

    return _wrapped
