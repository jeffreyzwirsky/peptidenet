from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from apps.stores import views

urlpatterns = [
    # Admin path is configurable (PEPTIDENET_ADMIN_PATH) to avoid the default
    # /admin/ scanner target in production. Defaults to "admin/" for dev.
    path(settings.ADMIN_PATH, admin.site.urls),
    # The console is mounted twice from one codebase:
    #   /manage/ → OWNER admin side (superuser only)
    #   /portal/ → walled STAFF side (Portal Staff group; is_staff=False users)
    # apps.manage.access.console_required enforces the right rule per namespace.
    path("manage/", include(("apps.manage.urls", "manage"), namespace="manage")),
    path("portal/", include(("apps.manage.urls", "manage"), namespace="portal")),
    # Themed password-reset / set-password flow (Mailgun-backed). Single mount,
    # non-namespaced so Django's built-in reverse() calls resolve.
    path("account/", include("apps.mailer.auth_urls")),
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
    # Regional landing pages. A site only serves its own market's regions.
    path("research-peptides/<slug:slug>/", views.region_page, name="region"),
    # Policy pages. Clean top-level paths because these are the URLs a payment
    # processor is handed at onboarding, and buyers look for them by name.
    path("shipping/", views.policy, {"slug": "shipping"}, name="policy_shipping"),
    path("returns/", views.policy, {"slug": "returns"}, name="policy_returns"),
    path("privacy/", views.policy, {"slug": "privacy"}, name="policy_privacy"),
    path("terms/", views.policy, {"slug": "terms"}, name="policy_terms"),
    # Cart + checkout (shared backend for every site)
    path("cart/", views.cart_state, name="cart_state"),
    path("cart/add/", views.cart_add, name="cart_add"),
    path("cart/update/", views.cart_update, name="cart_update"),
    path("checkout/", views.checkout, name="checkout"),
    # Customer order tracking — a 10–15 day delivery needs somewhere to look.
    path("order/<str:number>/", views.order_status, name="order_status"),
    path("contact/", views.contact, name="contact"),
    path("coa/<slug:slug>/", views.coa, name="coa"),
    path("healthz/", views.healthz, name="healthz"),
]
