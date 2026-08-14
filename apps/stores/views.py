import json
import math

from django.conf import settings
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
    return render(request, _theme_template(request, "home.html"),
                  {"active_category": slug, "preload_hero": True})


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
            # Currency follows the storefront's market, not a hardcoded CAD —
            # a US buyer seeing CAD in the rich result is a conversion killer.
            "priceCurrency": request.site.currency or "CAD",
            "availability": avail,
            "url": url,
            "eligibleRegion": {
                "@type": "Country", "name": request.site.country_name,
            },
            # Google reads this to show a delivery estimate in Shopping results.
            # It has to match the 10–15 days we tell the buyer on-page.
            "shippingDetails": {
                "@type": "OfferShippingDetails",
                "deliveryTime": {
                    "@type": "ShippingDeliveryTime",
                    "transitTime": {
                        "@type": "QuantitativeValue",
                        "minValue": request.site.shipping_min_days,
                        "maxValue": request.site.shipping_max_days,
                        "unitCode": "DAY",
                    },
                },
            },
        },
    }
    if product.is_discounted:
        product_ld["offers"]["priceSpecification"] = {
            "@type": "UnitPriceSpecification",
            "price": str(product.list_price),
            "priceCurrency": request.site.currency or "CAD",
            "priceType": "https://schema.org/ListPrice",
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
            "preload_hero": True,
        },
    )


def policy(request, slug):
    """Shipping, returns, privacy and terms — built per site and per market.

    These are also what a payment processor asks for during onboarding, which is
    the other reason their absence was blocking.
    """
    _require_site(request)
    from . import policies
    doc = policies.get(slug, request.site)
    if doc is None:
        raise Http404("No such policy.")
    return render(request, _theme_template(request, "policy.html"), {
        "policy": doc,
        "policy_nav": policies.nav(request.site),
    })


def region_page(request, slug):
    """
    Regional landing page — /research-peptides/<region>/.

    A site only serves regions in its own market: the .ca domains serve Canadian
    provinces, the .com domains serve US states. Serving both from one domain
    would be the doorway-page pattern these pages are written to avoid.
    """
    _require_site(request)
    from . import regions
    r = regions.get(slug)
    # Ownership, not just market. Every region page lives on exactly one domain,
    # so there is exactly one canonical URL for it across the network.
    if r is None or r.get("owner") != request.site.domain:
        raise Http404("No such region for this storefront.")

    base = _base_url(request)
    url = f"{base}/research-peptides/{slug}/"
    ld = [{
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": base + "/"},
        ],
    }]
    if r.get("parent"):
        p = regions.get(r["parent"])
        if p:
            ld[0]["itemListElement"].append({
                "@type": "ListItem", "position": 2, "name": p["name"],
                "item": f"{base}/research-peptides/{p['slug']}/"})
    ld[0]["itemListElement"].append({
        "@type": "ListItem", "position": len(ld[0]["itemListElement"]) + 1,
        "name": r["name"], "item": url})
    if r.get("faqs"):
        ld.append({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": f["q"],
                 "acceptedAnswer": {"@type": "Answer", "text": f["a"]}}
                for f in r["faqs"]
            ],
        })
    # Only this storefront's own regions — linking to a page that 404s here
    # would be an internal broken link on every one of them.
    siblings = [x for x in regions.for_site(request.site) if x["slug"] != slug
                and not x.get("parent")]
    # City pages hang off a province page. Linking both directions makes the
    # hierarchy explicit to a reader and to a crawler, and keeps the city pages
    # from being orphans reachable only from the sitemap.
    parent = regions.get(r["parent"]) if r.get("parent") else None
    children = regions.cities_of(slug)
    return render(request, _theme_template(request, "region.html"), {
        "region": r,
        "siblings": siblings,
        "parent": parent,
        "children": children,
        "featured": Product.objects.filter(is_active=True)
                           .select_related("category")[:4],
        "jsonld": json.dumps(ld),
    })


def calculator(request):
    _require_site(request)
    return render(request, _theme_template(request, "calculator.html"), {})


def rewards(request):
    _require_site(request)
    return render(request, _theme_template(request, "rewards.html"), {})


def _cart_payload(cart):
    return {
        "count": cart.count(),          # packs
        "vials": cart.vial_count(),     # vials — what actually ships
        "total": str(cart.total()),
        "subtotal": str(cart.subtotal()),
        "savings": str(cart.savings()),
        "items": [
            {
                **i,
                "price": str(i["price"]),
                "pack_price": str(i["pack_price"]),
                "per_vial": str(i["per_vial"]),
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


def _packs(value, default=1):
    """Coerce a client-supplied quantity to whole packs.

    The wire value is packs, not vials — every caller in store.js sends packs.
    Anything unparseable falls back to the default rather than 500ing, and the
    server never trusts the client to have enforced the minimum.

    Fractions round UP, and deliberately so. `int(0.4)` is 0, which the cart
    reads as "remove this line" — so a request for four vials of a ten-vial
    compound would have emptied the line instead of correcting it. A positive
    request means the customer wants some; the only quantity they can have is
    a whole pack.
    """
    try:
        n = float(value)
    except (TypeError, ValueError):
        return default
    if n <= 0:
        return 0
    return max(int(math.ceil(n)), 1)


@require_POST
def cart_add(request):
    data = _body(request)
    cart = Cart(request)
    # One pack is the minimum sellable unit, so a bare "add to cart" adds a
    # full pack — 10 vials for a compound, 1 bottle for a supply.
    cart.add(data.get("product_id"), max(_packs(data.get("qty", 1)), 1))
    return JsonResponse(_cart_payload(cart))


@require_POST
def cart_update(request):
    data = _body(request)
    cart = Cart(request)
    # 0 still means "remove"; anything else is clamped up to a whole pack so a
    # hand-crafted request can't buy 3 vials of a 10-vial compound.
    qty = _packs(data.get("qty", 0), default=0)
    cart.update(data.get("product_id"), qty if qty <= 0 else max(qty, 1))
    return JsonResponse(_cart_payload(cart))


@require_POST
@rate_limit("checkout", limit=12, window=60)
def checkout(request):
    """
    Create an order in the dropship flow.

    Every accepted payment method (Interac, crypto, Alipay, Western Union) is
    confirmed by a human, so nothing is captured here — the order lands in
    `payment_review` and a person marks it paid, which is what then releases the
    purchase order to the manufacturing partner.
    """
    _require_site(request)
    if is_bot_honeypot(request):
        return JsonResponse({"ok": True, "order_number": "—", "status": "ignored",
                             "message": "Received."})
    cart = Cart(request)
    items = cart.items()
    if not items:
        return JsonResponse({"ok": False, "error": "Your cart is empty."}, status=400)
    data = _body(request)

    # Research-use-only acknowledgement is a hard gate, not a nicety — it's the
    # record that the buyer was told what they were buying.
    if not data.get("ruo_ack"):
        return JsonResponse(
            {"ok": False,
             "error": "Please confirm these compounds are for research use only."},
            status=400,
        )

    shipping_address = (data.get("shipping_address") or "").strip()
    if not shipping_address:
        return JsonResponse(
            {"ok": False, "error": "A shipping address is required — the "
                                   "manufacturing partner ships direct to you."},
            status=400,
        )

    method = data.get("payment_method", "")
    valid = {m for m in getattr(settings, "PAYMENT_METHODS", [])}
    if method and method not in valid:
        method = ""

    order = Order.create_from_cart(
        site=request.site,
        items=items,
        total=cart.total(),
        email=data.get("email", ""),
        name=data.get("name", ""),
        payment_method=method,
        shipping_address=shipping_address,
    )
    cart.clear()
    try:
        from apps.mailer import mailer
        mailer.order_confirmation(order)
    except Exception:  # email must never break checkout
        pass
    return JsonResponse({
        "ok": True,
        "order_number": order.number,
        "status": order.status,
        "status_url": f"/order/{order.number}/",
        "message": order.confirmation_message,
    })


@rate_limit("order_status", limit=30, window=60)
def order_status(request, number):
    """
    Customer-facing order status.

    Rate-limited: the only thing protecting one customer's name, address and
    order contents from another is an 8-digit order number, which is well
    inside brute-force range for an unthrottled endpoint.

    Before this, the entire post-purchase experience was a toast that
    auto-dismissed after 2.6 seconds — on a 10–15 day delivery that is the
    single biggest driver of "where is my order" support calls.
    """
    _require_site(request)
    order = get_object_or_404(Order, number=number, site=request.site)
    steps = [
        ("payment_review", "Payment received", "We're confirming your payment."),
        ("paid", "Payment confirmed", "Your order is being placed with our manufacturing partner."),
        ("po_sent", "Ordered", "Your order has gone to our manufacturing partner."),
        ("supplier_shipped", "Shipped", "Your order is on its way."),
        ("delivered", "Delivered", "Your order has arrived."),
    ]
    order_of = {s: i for i, s in enumerate(
        ["pending_payment", "payment_review", "paid", "po_sent",
         "supplier_shipped", "in_transit", "delivered"]
    )}
    current = order_of.get(order.status, 0)
    timeline = [
        {"key": key, "label": label, "note": note,
         "done": order_of.get(key, 99) <= current}
        for key, label, note in steps
    ]
    window = order.expected_delivery_range
    return render(request, _theme_template(request, "order_status.html"), {
        "order": order,
        "timeline": timeline,
        "expected_from": window[0] if window else None,
        "expected_to": window[1] if window else None,
    })


@require_POST
@rate_limit("contact", limit=8, window=60)
def contact(request):
    _require_site(request)
    if is_bot_honeypot(request):
        return JsonResponse({"ok": True, "message": "Thanks — we'll be in touch."})
    data = _body(request)
    lead = Lead.objects.create(
        site=request.site,
        name=data.get("name", ""),
        email=data.get("email", ""),
        phone=(data.get("phone") or "").strip()[:20],
        message=data.get("message", ""),
        rating=data.get("rating") or None,
        kind=data.get("kind", "contact"),
    )
    try:  # SMS dual opt-in capture → immutable consent audit (real client IP)
        raw_phone = (data.get("phone") or "").strip()
        if raw_phone:
            from apps.comms import consent as _consent
            from apps.comms import phone as _cphone
            from apps.comms import sms as _csms
            e164 = _cphone.normalize(raw_phone)
            if e164:
                _csms.resolve_contact(e164, site=request.site,
                                      name=data.get("name", ""), email=data.get("email", ""))
                if data.get("sms_optin_transactional"):
                    _consent.log_consent(e164, "opt_in", category="transactional",
                                         source="contact_form", request=request,
                                         site=request.site, note="Contact form opt-in")
                if data.get("sms_optin_marketing"):
                    _consent.log_consent(e164, "opt_in", category="marketing",
                                         source="contact_form", request=request,
                                         site=request.site, note="Contact form opt-in")
    except Exception:
        pass
    try:
        from apps.mailer import mailer
        mailer.lead_alert(lead)
    except Exception:
        pass
    return JsonResponse({"ok": True, "message": "Thanks — we'll be in touch."})


def coa(request, slug):
    _require_site(request)
    product = get_object_or_404(Product, slug=slug, is_active=True)
    return JsonResponse({
        "product": product.name,
        "coa_url": product.coa_url or "",
        # No COA is promised. This endpoint used to answer "available on request",
        # which is a commitment we cannot keep for any compound in the catalogue.
        "message": ("No certificate of analysis is held for this product."
                    if not product.coa_url else ""),
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
    site = getattr(request, "site", None)
    brand = site.brand_name if site else "Research Compounds"
    host = request.get_host()
    lines = [
        # Per-site header — every domain serves its own robots file, not one
        # network-wide copy.
        f"# robots.txt — {brand} ({host})",
        f"# RSS: {base}/blog/feed/",
        f"# Security contact: {base}/.well-known/security.txt",
        "",
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
        f"# LLM full map: {base}/llms-full.txt",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")


@require_GET
def security_txt(request):
    """RFC 9116 /.well-known/security.txt — per-site contact for security
    researchers. Expires is dynamic (regenerated per request) so the file can
    never quietly go stale, which is the classic security.txt failure."""
    from datetime import timedelta

    from django.utils import timezone

    base = _base_url(request)
    site = getattr(request, "site", None)
    contact = (site.contact_email if site and site.contact_email
               else "jeff@smashscrap.ca")
    expires = (timezone.now() + timedelta(days=180)).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        f"Contact: mailto:{contact}",
        f"Expires: {expires}",
        f"Canonical: {base}/.well-known/security.txt",
        "Preferred-Languages: en",
        f"Policy: {base}/terms/",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")


@require_GET
def sitemap_xml(request):
    base = _base_url(request)
    from apps.blog.models import BlogPost
    from . import policies, regions
    site = getattr(request, "site", None)
    # (loc, changefreq, priority, lastmod-or-None). lastmod is what actually
    # gets a changed page recrawled — Google largely ignores changefreq/priority
    # but trusts an accurate lastmod.
    posts = (list(BlogPost.objects.filter(site=site, status="published"))
             if site else [])
    latest_post = max((p.updated_at for p in posts), default=None)
    urls = [(base + "/", "daily", "1.0", latest_post),
            (base + "/blog/", "daily", "0.7", latest_post),
            (base + "/calculator/", "monthly", "0.6", None),
            (base + "/rewards/", "monthly", "0.5", None)]
    for c in Category.objects.all():
        urls.append((f"{base}/category/{c.slug}/", "weekly", "0.7", None))
    for p in Product.objects.filter(is_active=True):
        urls.append((f"{base}/product/{p.slug}/", "weekly", "0.8",
                     p.price_updated_at))
    if site:
        # Only this site's own market. A .com listing Canadian provinces would
        # be the doorway pattern these pages are written to avoid.
        for r in regions.for_site(site):
            urls.append((f"{base}/research-peptides/{r['slug']}/", "monthly",
                         "0.6", None))
        for post in posts:
            urls.append((f"{base}/blog/{post.slug}/", "monthly", "0.6",
                         post.updated_at))
    for slug in policies.POLICY_SLUGS:
        urls.append((f"{base}/{slug}/", "yearly", "0.3", None))
    body = ['<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, freq, pri, lastmod in urls:
        lm = (f"<lastmod>{lastmod.strftime('%Y-%m-%d')}</lastmod>"
              if lastmod else "")
        body.append(f"<url><loc>{loc}</loc>{lm}<changefreq>{freq}</changefreq>"
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
        f"Research-compound (peptide) store serving "
        f"{site.country_name if site else 'Canada'}. All products are for laboratory "
        "and in-vitro research use only — not for human or veterinary use. We hold no "
        "certificate of analysis, purity result or identity confirmation for these "
        "compounds and make no testing claim; treat the material as uncharacterised.",
        "",
        "## Key pages",
        f"- [Home]({base}/): storefront and full catalogue",
        f"- [Reconstitution & dosage calculator]({base}/calculator/): concentration, "
        "volume-to-draw, units, doses per vial",
        f"- [Rewards & bulk pricing]({base}/rewards/): automatic bulk tiers, first-order code",
        f"- [Shipping & delivery]({base}/shipping/): delivery window, customs, tracking",
        f"- [Returns & refunds]({base}/returns/): damage, non-delivery, cancellation",
        f"- [Privacy]({base}/privacy/) · [Terms of sale]({base}/terms/)",
        f"- [Blog]({base}/blog/): research notes and educational articles",
        f"- [Full LLM map]({base}/llms-full.txt): complete catalogue with specs + FAQs",
        f"- [Sitemap]({base}/sitemap.xml): all indexable URLs",
        "",
        "## Products",
    ]
    for p in Product.objects.filter(is_active=True).select_related("category")[:60]:
        out.append(f"- [{p.name}]({base}/product/{p.slug}/): {p.category.name}, "
                   f"${p.price}/vial — {p.description}")
    # No origin claim: goods ship direct from the manufacturing partner, and the
    # "free express / free priority" promises were never true under dropship.
    window = f"{site.shipping_min_days}\u2013{site.shipping_max_days}" if site else "10\u201315"
    out += ["", "## Ordering",
            f"- Orders ship directly from our manufacturing partner; allow {window} days "
            "for delivery. Shipments may be subject to customs clearance.",
            "- Payment: Interac e-Transfer, cryptocurrency, Alipay or Western Union. "
            "Every payment is confirmed manually.",
            "- For research use only. Age 21+."]
    return HttpResponse("\n".join(out), content_type="text/plain; charset=utf-8")


@require_GET
def llms_full_txt(request):
    """The llms-full.txt convention — a complete, single-file content map with
    full product specs, research context, and FAQs for LLM ingestion."""
    from apps.blog.models import BlogPost

    site = getattr(request, "site", None)
    base = _base_url(request)
    brand = site.brand_name if site else "Research Compounds"
    window = f"{site.shipping_min_days}\u2013{site.shipping_max_days}" if site else "10\u201315"
    market = site.country_name if site else "Canada"
    out = [
        f"# {brand} — Full Content Map",
        "",
        f"> Complete, machine-readable reference for this research-compound "
        f"(peptide) store serving {market}. FOR RESEARCH USE ONLY \u2014 not for human or "
        "veterinary use. All figures are laboratory reference data.",
        "",
        f"Orders ship directly from our manufacturing partner; allow {window} days for "
        "delivery. No analytical documentation is held for any compound: no certificate "
        "of analysis, no purity result, no identity confirmation. Age 21+.",
        "",
        "## Catalogue",
    ]
    for p in Product.objects.filter(is_active=True).select_related("category"):
        out += [
            "",
            f"### {p.name}",
            f"- URL: {base}/product/{p.slug}/",
            f"- Category: {p.category.name}",
            f"- Price: ${p.price} CAD per vial ({p.pack_price} per {p.vials_per_pack}-vial pack)",
            f"- Sizes: {', '.join(p.sizes) if p.sizes else 'n/a'}",
            f"- Stock: {p.stock_state_label}",
        ]
        if p.cas_number:
            out.append(f"- CAS number: {p.cas_number}")
        if p.molecular_formula:
            out.append(f"- Molecular formula: {p.molecular_formula}")
        if p.molecular_weight:
            out.append(f"- Molecular weight: {p.molecular_weight} g/mol")
        if p.sequence:
            out.append(f"- Sequence / structure: {p.sequence}")
        if p.half_life:
            out.append(f"- Reported half-life: {p.half_life}")
        if p.storage:
            out.append(f"- Storage: {p.storage}")
        if p.solubility:
            out.append(f"- Solubility: {p.solubility}")
        if p.research_area:
            out.append(f"- Research context: {p.research_area}")
        for f in p.auto_faqs():
            out.append(f"- FAQ: {f['q']} — {f['a']}")

    out += ["", "## Research library"]
    if site:
        posts = BlogPost.objects.filter(site=site, status="published")
        if posts:
            for post in posts:
                out.append(f"- [{post.title}]({base}/blog/{post.slug}/): {post.excerpt}")
        else:
            out.append("- (Articles are being prepared.)")
    out += [
        "",
        "## Bulk pricing",
        "- 3+ vials: 5% off. 5+ vials: 10% off. 10+ vials: 15% off. Applied automatically in cart.",
        "",
        "## Compliance",
        "- Research use only. Not for human or veterinary use. Age 21+.",
        "- Reference data compiled from public chemical databases and the peer-reviewed literature.",
    ]
    return HttpResponse("\n".join(out), content_type="text/plain; charset=utf-8")


def _body(request):
    if request.content_type and "application/json" in request.content_type:
        try:
            return json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return {}
    return request.POST.dict()
