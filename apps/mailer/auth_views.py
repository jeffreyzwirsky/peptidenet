from django.contrib.auth.views import PasswordResetView
from django.http import HttpResponse, HttpResponseRedirect

from apps.security.utils import client_ip, log_event, rate_limit_exceeded


class ThrottledPasswordResetView(PasswordResetView):
    """Django's enumeration-safe reset flow with IP and account mail caps."""

    def dispatch(self, request, *args, **kwargs):
        if request.method == "POST" and rate_limit_exceeded(
                "password_reset_ip", client_ip(request), limit=5, window=900):
            log_event(request, "ratelimit", detail="password reset IP limit")
            return HttpResponse("Too many requests.", status=429)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        email = (form.cleaned_data.get("email") or "").strip().casefold()
        if rate_limit_exceeded(
                "password_reset_account", email or "blank", limit=3, window=3600):
            # Preserve Django's non-enumerating response: do not reveal whether
            # the address exists, just suppress another outbound email.
            log_event(self.request, "ratelimit", detail="password reset account limit")
            return HttpResponseRedirect(self.get_success_url())
        return super().form_valid(form)
