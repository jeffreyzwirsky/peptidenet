"""Console login / logout — a dedicated door so staff never touch the Django
admin login. Same views serve both the /manage/ and /portal/ mounts."""
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect, render

from .access import admin_allowed, portal_allowed


def _ns(request):
    return getattr(request.resolver_match, "namespace", "") or "manage"


def _allowed(request, user):
    return admin_allowed(user) if _ns(request) == "manage" else portal_allowed(user)


def login_view(request):
    ns = _ns(request)
    nxt = request.POST.get("next") or request.GET.get("next") or ""
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
            error = "This account doesn't have access to this console."
        else:
            error = "Incorrect username or password."
    return render(request, "manage/login.html", {"error": error, "next": nxt})


def logout_view(request):
    ns = _ns(request)
    auth_logout(request)
    return redirect(f"{ns}:login")
