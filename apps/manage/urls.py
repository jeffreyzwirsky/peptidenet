from django.urls import path

from . import views

app_name = "manage"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("orders/", views.orders, name="orders"),
    path("orders/<int:pk>/", views.order_detail, name="order_detail"),
    path("inventory/", views.inventory, name="inventory"),
    path("leads/", views.leads, name="leads"),
    path("messages/", views.messages_inbox, name="messages"),
    path("calls/", views.calls, name="calls"),
    path("numbers/", views.numbers, name="numbers"),
    path("ai/", views.ai_usage, name="ai_usage"),
    path("blog/", views.blog, name="blog"),
    path("security/", views.security, name="security"),
]
