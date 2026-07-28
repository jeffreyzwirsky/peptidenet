from django.conf import settings
from django.db.models import Q

from apps.catalog.models import Category, Product, Review

from .cart import Cart

# Which hero image each theme actually renders. The base template used to
# preload a single hardcoded path (hero-vials.jpg) on every domain, so 7 of the
# 8 sites downloaded a large unused JPG at fetchpriority=high, competing with
# their real LCP image.
THEME_HERO = {
    "biolabs": "/static/hero/hero-vials.jpg",
    "neon": "/static/hero/hero-neon.jpg",
}
DEFAULT_HERO = "/static/hero/hero-vial-macro.jpg"

PAYMENT_METHOD_LABELS = {
    "interac": "Interac e-Transfer",
    "crypto": "Cryptocurrency",
    "alipay": "Alipay",
    "western_union": "Western Union",
}


def _payment_methods():
    """The methods offered at checkout, in configured order. Every one is
    confirmed by hand — none of them auto-capture."""
    return [
        {"value": m, "label": PAYMENT_METHOD_LABELS.get(m, m.replace("_", " ").title())}
        for m in getattr(settings, "PAYMENT_METHODS", [])
    ]


def storefront(request):
    """Inject the shared catalogue, the resolved site, and cart summary
    into every template so themes stay purely presentational."""
    site = getattr(request, "site", None)
    theme = getattr(request, "theme", "biolabs")
    cart = Cart(request)
    methods = _payment_methods()
    return {
        "site": site,
        "theme": theme,
        "categories": Category.objects.all(),
        # One card per compound, not one per strength.
        #
        # A compound sold in 5mg and 10mg is one product to a customer and two
        # SKUs to us. Listing both filled the grid with near-identical cards
        # differing only by a number in the size chip — the catalogue read as
        # padded rather than deep. Standalone products have no family and so
        # match the empty-string branch.
        "products": (Product.objects.filter(is_active=True)
                     .filter(Q(family="") | Q(is_family_default=True))
                     .select_related("category")),
        "cart_count": cart.count(),
        "cart_total": cart.total(),
        "cart_items": cart.items(),
        # Site-wide reviews (no product attached). Real rows only — the section
        # shows an honest empty state rather than invented testimonials.
        "site_reviews": Review.objects.filter(product__isnull=True, is_published=True)[:4],
        "hero_image": THEME_HERO.get(theme, DEFAULT_HERO),
        "payment_methods": methods,
        "payment_methods_label": ", ".join(m["label"] for m in methods),
    }
