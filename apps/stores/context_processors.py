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

# Hreflang is a relationship between equivalent localized pages, not between
# every URL that happens to live on a twinned domain. These routes are backed
# by the same catalogue/policy content in both markets. Blog posts, blog
# indexes and region pages are Site-owned and deliberately excluded: the same
# path on the twin is either different content or a 404.
HREFLANG_SHARED_VIEWS = frozenset({
    "home",
    "category",
    "product_detail",
    "policy_shipping",
    "policy_returns",
    "policy_privacy",
    "policy_terms",
})

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


def _footer_regions(site):
    """Top-level regions this storefront owns, for the footer.

    Province and state pages only — city pages are reached from their province
    page, which keeps the footer readable and the hierarchy meaningful rather
    than dumping every URL into every page.
    """
    if not site:
        return []
    from . import regions
    return [r for r in regions.for_site(site) if not r.get("parent")]


def storefront(request):
    """Inject the shared catalogue, the resolved site, and cart summary
    into every template so themes stay purely presentational."""
    site = getattr(request, "site", None)
    theme = getattr(request, "theme", "biolabs")
    cart = Cart(request)
    methods = _payment_methods()
    match = getattr(request, "resolver_match", None)
    view_name = getattr(match, "view_name", "")
    hreflang_alternates = (
        site.alternates()
        if site is not None and view_name in HREFLANG_SHARED_VIEWS
        else []
    )
    # Every localized version must emit the same hreflang set. Use the
    # Canadian storefront as the stable fallback for unmatched locales rather
    # than making x-default point to whichever version is currently rendering.
    hreflang_default = next(
        (alt for alt in hreflang_alternates if alt.country == "CA"),
        hreflang_alternates[0] if hreflang_alternates else None,
    )
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
        # Region pages were orphans: nothing on the site linked to them except
        # other region pages, so the only route in was the sitemap. Internal
        # links are how crawl priority and link equity actually reach a page,
        # and a location page nobody links to is a location page nobody ranks.
        "footer_regions": _footer_regions(site),
        "hreflang_alternates": hreflang_alternates,
        "hreflang_default": hreflang_default,
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
