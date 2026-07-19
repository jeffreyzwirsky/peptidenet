from apps.catalog.models import Category, Product

from .cart import Cart


def storefront(request):
    """Inject the shared catalogue, the resolved site, and cart summary
    into every template so themes stay purely presentational."""
    site = getattr(request, "site", None)
    cart = Cart(request)
    return {
        "site": site,
        "theme": getattr(request, "theme", "biolabs"),
        "categories": Category.objects.all(),
        "products": Product.objects.filter(is_active=True).select_related("category"),
        "cart_count": cart.count(),
        "cart_total": cart.total(),
        "cart_items": cart.items(),
    }
