"""Console login / logout — a dedicated door so staff never touch the Django
admin login. Same views serve both the /manage/ and /portal/ mounts."""
import time

from django.contrib.auth import get_user_model
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect, render

from django.utils.http import url_has_allowed_host_and_scheme

from apps.security import mfa
from apps.security.models import ConsoleMfaDevice
from apps.security.utils import log_event, rate_limit, rate_limit_exceeded

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


PREAUTH_TTL = 300


def _render_login(request, *, error="", nxt="", device=None):
    stage = "password"
    secret = ""
    uri = ""
    if device is not None:
        stage = "otp" if device.confirmed else "setup"
        secret = device.secret if not device.confirmed else ""
        uri = mfa.provisioning_uri(device.user, device.secret) if secret else ""
    return render(request, "manage/login.html", {
        "error": error, "next": nxt, "stage": stage,
        "mfa_secret": secret, "mfa_uri": uri,
    })


def _preauth_user(request):
    data = request.session.get("console_preauth") or {}
    if data.get("namespace") != _ns(request):
        return None, ""
    if time.time() - float(data.get("started", 0)) > PREAUTH_TTL:
        request.session.pop("console_preauth", None)
        return None, ""
    user = get_user_model().objects.filter(pk=data.get("user_id"), is_active=True).first()
    if user is None or not _allowed(request, user):
        request.session.pop("console_preauth", None)
        return None, ""
    return user, _safe_next(request, data.get("next", ""))


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
        if request.POST.get("stage") == "otp":
            user, saved_next = _preauth_user(request)
            if user is None:
                return _render_login(request, error="That sign-in expired. Start again.", nxt=nxt)
            device = ConsoleMfaDevice.objects.filter(user=user).first()
            if device is None:
                request.session.pop("console_preauth", None)
                return _render_login(
                    request, error="That sign-in expired. Start again.", nxt=saved_next,
                )
            if rate_limit_exceeded("console_mfa_account", user.pk, limit=6, window=300):
                log_event(request, "login_failed", detail=f"MFA rate limit for {user.get_username()}")
                return _render_login(
                    request, error="Too many verification attempts. Try again in five minutes.",
                    nxt=saved_next, device=device,
                )
            if mfa.verify_and_consume(device, request.POST.get("code")):
                request.session.pop("console_preauth", None)
                auth_login(request, user)
                return redirect(saved_next or f"{ns}:dashboard")
            log_event(request, "login_failed", detail=f"bad MFA code for '{user.get_username()}' on {ns}")
            return _render_login(
                request, error="That verification code is not valid.",
                nxt=saved_next, device=device,
            )

        attempted = (request.POST.get("username") or "").strip()[:150]
        if rate_limit_exceeded(
                "console_login_account", attempted.casefold() or "blank", limit=10, window=900):
            log_event(request, "login_failed", detail=f"account rate limit on {ns}")
            return _render_login(
                request, error="Too many sign-in attempts. Try again in fifteen minutes.", nxt=nxt,
            )
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if _allowed(request, user):
                device, _ = ConsoleMfaDevice.objects.get_or_create(
                    user=user, defaults={"secret": mfa.new_secret()}
                )
                request.session["console_preauth"] = {
                    "user_id": user.pk, "namespace": ns,
                    "next": nxt, "started": time.time(),
                }
                return _render_login(request, nxt=nxt, device=device)
            # Correct password, wrong door: worth recording — it is either a
            # staff member confused about which console, or a portal account
            # probing the owner side.
            log_event(request, "login_failed",
                      detail=f"valid creds, no {ns} access: {user.get_username()}")
            error = "This account doesn't have access to this console."
        else:
            log_event(request, "login_failed", detail=f"bad credentials for '{attempted[:60]}' on {ns}")
            error = "Incorrect username or password."
    return _render_login(request, error=error, nxt=nxt)


def logout_view(request):
    ns = _ns(request)
    auth_logout(request)
    response = redirect(f"{ns}:login")
    response["Clear-Site-Data"] = '"cache", "cookies", "storage"'
    return response
