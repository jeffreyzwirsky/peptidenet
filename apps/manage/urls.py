from django.urls import path

from . import auth_views, views

app_name = "manage"

urlpatterns = [
    path("login/", auth_views.login_view, name="login"),
    path("logout/", auth_views.logout_view, name="logout"),
    path("", views.dashboard, name="dashboard"),
    path("orders/", views.orders, name="orders"),
    path("orders/<int:pk>/", views.order_detail, name="order_detail"),
    path("inventory/", views.inventory, name="inventory"),
    path("purchasing/", views.purchasing, name="purchasing"),
    path("pricing/", views.pricing, name="pricing"),
    path("leads/", views.leads, name="leads"),
    path("messages/", views.messages_inbox, name="messages"),
    path("calls/", views.calls, name="calls"),
    # Recording audio is PROXIED, never linked directly: api.twilio.com requires
    # HTTP Basic auth that a browser cannot send, so the old direct link showed
    # Twilio's 401 XML on every click. Row id in the URL, never a URL — a proxy
    # that fetches a caller-supplied URL is SSRF. See views.recording_audio.
    path("recording/<slug:kind>/<int:pk>/", views.recording_audio,
         name="recording_audio"),
    path("numbers/", views.numbers, name="numbers"),
    path("emails/", views.emails, name="emails"),
    path("compliance/", views.compliance, name="compliance"),
    path("team/", views.team, name="team"),
    path("ai/", views.ai_usage, name="ai_usage"),
    path("blog/", views.blog, name="blog"),
    path("security/", views.security, name="security"),
]
