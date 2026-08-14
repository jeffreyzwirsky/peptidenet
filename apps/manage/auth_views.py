"""Console login / logout — a dedicated door so staff never touch the Django
admin login. Same views serve both the /manage/ and /portal/ mounts."""
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect, render

from django.utils.http import url_has_allowed_host_and_scheme

from apps.security.utils import log_event, rate_limit

from .access import admin_allowed, portal_allowed


def _safe_next(request, raw):
    """Only ever redirect back into this host.

    Django's own LoginView validates `next`; this hand-rolled view did not, so
    `/manage/login/?next=https://lookalike.tld/manage/login/` sent the owner —
    after a genuine, successful login on the real domain — to a copy of the
    login page asking him to sign in again. Every phishing tell (host, path,
    TLS) was legitimate.
    """
    if raw and url_has_allowed_host_and_scheme(
            raw, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return raw
    return ""


def _ns(request):
    return getattr(request.resolver_match, "namespace", "") or "manage"


def _allowed(request, user):
    return admin_allowed(user) if _ns(request) == "manage" else portal_allowed(user)


# The console door is the most valuable target on the network — behind it sit
# every customer's order and address, supplier costs, and the ability to spend
# money on SMS and calls. It had no rate limit and no audit trail: an attacker
# could try passwords all day and leave nothing in the Security page to see.
# 10 attempts per 5 minutes per IP, and every failure is recorded.
@rate_limit("console_login", limit=10, window=300)
def login_view(request):
    ns = _ns(request)
    nxt = _safe_next(request, request.POST.get("next") or request.GET.get("next") or "")
    if request.user.is_authenticated and _allowed(request, request.user):
        return redirect(nxt or f"{ns}:dashboard")
    error = ""
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if _allowed(request, user):
                auth_login(request, user)
                return redirect(nxt or f"{ns}:dashboard")
            # Correct password, wrong door: worth recording — it is either a
            # staff member confused about which console, or a portal account
            # probing the owner side.
            log_event(request, "login_failed",
                      detail=f"valid creds, no {ns} access: {user.get_username()}")
            error = "This account doesn't have access to this console."
        else:
            attempted = (request.POST.get("username") or "")[:60]
            log_event(request, "login_failed", detail=f"bad credentials for '{attempted}' on {ns}")
            error = "Incorrect username or password."
    return render(request, "manage/login.html", {"error": error, "next": nxt})


def logout_view(request):
    ns = _ns(request)
    auth_logout(request)
    return redirect(f"{ns}:login")
