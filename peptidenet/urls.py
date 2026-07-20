from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from apps.stores import views

urlpatterns = [
    # Admin path is configurable (PEPTIDENET_ADMIN_PATH) to avoid the default
    # /admin/ scanner target in production. Defaults to "admin/" for dev.
    path(settings.ADMIN_PATH, admin.site.urls),
    # One super-admin control panel for orders + inventory across every site.
    path("manage/", include("apps.manage.urls")),
    # Twilio SMS/voice webhooks (configure each number to point here).
    path("webhooks/twilio/", include("apps.comms.urls")),
    # AI support assistant.
    path("ai/", include("apps.ai.urls")),
    # Per-site blog (host-routed).
    path("blog/", include("apps.blog.urls")),
    # SEO / discovery (per-site, host-aware).
    path("robots.txt", views.robots_txt, name="robots_txt"),
    path("sitemap.xml", views.sitemap_xml, name="sitemap_xml"),
    path("llms.txt", views.llms_txt, name="llms_txt"),
    path("llms-full.txt", views.llms_full_txt, name="llms_full_txt"),
    # Storefront (host-routed to the right theme by SiteMiddleware)
    path("", views.home, name="home"),
    path("category/<slug:slug>/", views.home, name="category"),
    path("product/<slug:slug>/", views.product_detail, name="product_detail"),
    path("calculator/", views.calculator, name="calculator"),
    path("rewards/", views.rewards, name="rewards"),
    # Cart + checkout (shared backend for every site)
    path("cart/", views.cart_state, name="cart_state"),
    path("cart/add/", views.cart_add, name="cart_add"),
    path("cart/update/", views.cart_update, name="cart_update"),
    path("checkout/", views.checkout, name="checkout"),
    path("contact/", views.contact, name="contact"),
    path("coa/<slug:slug>/", views.coa, name="coa"),
    path("healthz/", views.healthz, name="healthz"),
]
