import json

from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from apps.catalog.models import Category, Product
from apps.leads.models import Lead
from apps.orders.models import Order
from apps.security.utils import is_bot_honeypot, rate_limit

from .cart import Cart


def _theme_template(request, name):
    return f"themes/{getattr(request, 'theme', 'biolabs')}/{name}"


def _require_site(request):
    if request.site is None:
        raise Http404("No storefront is configured for this host.")


@ensure_csrf_cookie
def home(request, slug=None):
    _require_site(request)
    return render(request, _theme_template(request, "home.html"), {"active_category": slug})


def product_detail(request, slug):
    _require_site(request)
    product = get_object_or_404(Product, slug=slug, is_active=True)
    related = list(
        Product.objects.filter(category=product.category, is_active=True)
        .exclude(id=product.id)[:4]
    )
    if len(related) < 4:
        extra = Product.objects.filter(is_active=True).exclude(
            id__in=[product.id, *[r.id for r in related]]
        )[: 4 - len(related)]
        related += list(extra)

    faqs = product.auto_faqs()
    base = _base_url(request)
    url = f"{base}/product/{product.slug}/"
    avail = {
        "in": "https://schema.org/InStock",
        "low": "https://schema.org/LimitedAvailability",
        "out": "https://schema.org/OutOfStock",
    }.get(product.stock_state, "https://schema.org/InStock")

    product_ld = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product.name,
        "category": product.category.name,
        "brand": {"@type": "Brand", "name": request.site.brand_name},
        "description": (product.research_area or product.description or "")[:300],
        "offers": {
            "@type": "Offer",
            "price": str(product.price),
            "priceCurrency": "CAD",
            "availability": avail,
            "url": url,
        },
    }
    if product.cas_number:
        product_ld["additionalProperty"] = [
            {"@type": "PropertyValue", "name": "CAS Number", "value": product.cas_number}
        ]
    if product.rating_count:
        product_ld["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": str(product.rating_avg),
            "reviewCount": str(product.rating_count),
        }
    breadcrumb_ld = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": base + "/"},
            {"@type": "ListItem", "position": 2, "name": product.category.name,
             "item": f"{base}/category/{product.category.slug}/"},
            {"@type": "ListItem", "position": 3, "name": product.name, "item": url},
        ],
    }
    ld = [product_ld, breadcrumb_ld]
    if faqs:
        ld.append({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": f["q"],
                 "acceptedAnswer": {"@type": "Answer", "text": f["a"]}}
                for f in faqs
            ],
        })

    return render(
        request,
        _theme_template(request, "product.html"),
        {
            "product": product,
            "related": related,
            "reviews": product.review_qs[:6],
            "faqs": faqs,
            "jsonld": json.dumps(ld),
        },
    )


def calculator(request):
    _require_site(request)
    return render(request, _theme_template(request, "calculator.html"), {})


def rewards(request):
    _require_site(request)
    return render(request, _theme_template(request, "rewards.html"), {})


def _cart_payload(cart):
    return {
        "count": cart.count(),
        "total": str(cart.total()),
        "subtotal": str(cart.subtotal()),
        "savings": str(cart.savings()),
        "items": [
            {
                **i,
                "price": str(i["price"]),
                "unit_price": str(i["unit_price"]),
                "line_total": str(i["line_total"]),
                "line_gross": str(i["line_gross"]),
                "line_saved": str(i["line_saved"]),
            }
            for i in cart.items()
        ],
    }


@require_GET
def cart_state(request):
    return JsonResponse(_cart_payload(Cart(request)))


@require_POST
def cart_add(request):
    data = _body(request)
    cart = Cart(request)
    cart.add(data.get("product_id"), int(data.get("qty", 1)))
    return JsonResponse(_cart_payload(cart))


@require_POST
def cart_update(request):
    data = _body(request)
    cart = Cart(request)
    cart.update(data.get("product_id"), int(data.get("qty", 0)))
    return JsonResponse(_cart_payload(cart))


@require_POST
@rate_limit("checkout", limit=12, window=60)
def checkout(request):
    """Create a pending order. Payment is stubbed until a processor is wired
    (see apps/orders/payments.py) — nothing is charged."""
    _require_site(request)
    if is_bot_honeypot(request):
        return JsonResponse({"ok": True, "order_number": "—", "status": "ignored",
                             "message": "Received."})
    cart = Cart(request)
    items = cart.items()
    if not items:
        return JsonResponse({"ok": False, "error": "Your cart is empty."}, status=400)
    data = _body(request)
    order = Order.create_from_cart(
        site=request.site,
        items=items,
        total=cart.total(),
        email=data.get("email", ""),
        name=data.get("name", ""),
    )
    cart.clear()
    return JsonResponse({
        "ok": True,
        "order_number": order.number,
        "status": order.status,
        "message": order.confirmation_message,
    })


@require_POST
@rate_limit("contact", limit=8, window=60)
def contact(request):
    _require_site(request)
    if is_bot_honeypot(request):
        return JsonResponse({"ok": True, "message": "Thanks — we'll be in touch."})
    data = _body(request)
    Lead.objects.create(
        site=request.site,
        name=data.get("name", ""),
        email=data.get("email", ""),
        message=data.get("message", ""),
        rating=data.get("rating") or None,
        kind=data.get("kind", "contact"),
    )
    return JsonResponse({"ok": True, "message": "Thanks — we'll be in touch."})


def coa(request, slug):
    _require_site(request)
    product = get_object_or_404(Product, slug=slug, is_active=True)
    return JsonResponse({
        "product": product.name,
        "purity": product.purity,
        "coa_url": product.coa_url or "",
        "message": "COA available on request." if not product.coa_url else "",
    })


@require_GET
def healthz(request):
    return JsonResponse({"ok": True})


# ---------------- SEO / discovery (per-site, host-aware) ----------------
def _base_url(request):
    return f"{request.scheme}://{request.get_host()}"


@require_GET
def robots_txt(request):
    base = _base_url(request)
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /manage/",
        "Disallow: /admin/",
        "Disallow: /cart/",
        "Disallow: /checkout/",
        "Disallow: /webhooks/",
        "",
        # Let AI crawlers in explicitly + point them at llms.txt.
        "User-agent: GPTBot",
        "Allow: /",
        "User-agent: ClaudeBot",
        "Allow: /",
        "User-agent: PerplexityBot",
        "Allow: /",
        "",
        f"Sitemap: {base}/sitemap.xml",
        f"# LLM guide: {base}/llms.txt",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


@require_GET
def sitemap_xml(request):
    base = _base_url(request)
    from apps.blog.models import BlogPost
    urls = [(base + "/", "daily", "1.0"), (base + "/blog/", "daily", "0.7"),
            (base + "/calculator/", "monthly", "0.6"),
            (base + "/rewards/", "monthly", "0.5")]
    for c in Category.objects.all():
        urls.append((f"{base}/category/{c.slug}/", "weekly", "0.7"))
    for p in Product.objects.filter(is_active=True):
        urls.append((f"{base}/product/{p.slug}/", "weekly", "0.8"))
    if getattr(request, "site", None):
        for post in BlogPost.objects.filter(site=request.site, status="published"):
            urls.append((f"{base}/blog/{post.slug}/", "monthly", "0.6"))
    body = ['<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, freq, pri in urls:
        body.append(f"<url><loc>{loc}</loc><changefreq>{freq}</changefreq>"
                    f"<priority>{pri}</priority></url>")
    body.append("</urlset>")
    return HttpResponse("\n".join(body), content_type="application/xml")


@require_GET
def llms_txt(request):
    """The emerging llms.txt standard — a concise, LLM-friendly map of the site."""
    site = getattr(request, "site", None)
    base = _base_url(request)
    brand = site.brand_name if site else "Research Compounds"
    out = [
        f"# {brand}",
        "",
        f"> {getattr(site, 'meta_description', '') if site else ''}".rstrip(),
        "",
        "Canadian research-compound (peptide) store. All products are for laboratory "
        "and in-vitro research use only — not for human or veterinary use. Every batch "
        "is third-party HPLC/MS tested to ≥99% purity with a COA available.",
        "",
        "## Key pages",
        f"- [Home]({base}/): storefront and full catalogue",
        f"- [Blog]({base}/blog/): research notes and educational articles",
        f"- [Sitemap]({base}/sitemap.xml): all indexable URLs",
        "",
        "## Products",
    ]
    for p in Product.objects.filter(is_active=True).select_related("category")[:60]:
        out.append(f"- [{p.name}]({base}/product/{p.slug}/): {p.category.name}, "
                   f"${p.price}/vial, {p.purity} purity — {p.description}")
    out += ["", "## Ordering",
            f"- Ships from {getattr(site, 'ships_from', 'Canada') if site else 'Canada'}; "
            "free express over $200, free priority over $500.",
            "- For research use only. Age 21+."]
    return HttpResponse("\n".join(out), content_type="text/plain; charset=utf-8")


def _body(request):
    if request.content_type and "application/json" in request.content_type:
        try:
            return json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return {}
    return request.POST.dict()
