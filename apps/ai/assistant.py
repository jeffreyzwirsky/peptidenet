"""Storefront support-assistant knowledge + an offline (no-API-key) responder.
When a real key is set the LLM uses this same context as its system prompt; with
no key, the heuristic responder still gives useful, catalogue-grounded answers."""
from apps.catalog.models import Product

DISCLAIMER = ("All products are for laboratory and in-vitro research use only — "
              "not for human or veterinary use.")


def _window(site):
    """Delivery window as a plain string. Single source of truth for anything the
    assistant says about timing."""
    if site is None:
        return "10\u201315"
    return f"{site.shipping_min_days}\u2013{site.shipping_max_days}"


def system_prompt(site):
    brand = site.brand_name if site else "our store"
    lines = [
        f"You are the support assistant for {brand}, a research-compound store.",
        "Answer concisely and helpfully about products, purity, COAs, shipping and ordering.",
        "NEVER give medical, dosing, or human-use advice. Always keep a research-use-only framing.",
        "Orders ship directly from our manufacturing partner; delivery takes "
        f"{_window(site)} days. NEVER state or imply which country goods ship from \u2014 "
        "we make no origin claim. If asked, say orders ship from our manufacturing "
        "partner and quote the delivery window.",
        "Every batch is third-party HPLC/MS tested to \u226599% purity with a COA available.",
        "Catalogue (name — category — $price/vial — sizes):",
    ]
    for p in Product.objects.filter(is_active=True).select_related("category")[:40]:
        lines.append(f"- {p.name} — {p.category.name} — ${p.price} — {', '.join(p.sizes)}")
    lines.append("Close with a brief research-use-only note when relevant.")
    return "\n".join(lines)


def stub_answer(question, site):
    q = (question or "").lower()
    brand = site.brand_name if site else "our store"
    products = list(Product.objects.filter(is_active=True).select_related("category"))

    # product match
    for p in products:
        if p.name.lower() in q or p.slug.replace("-", " ") in q:
            stock = "in stock" if p.stock_state == "in" else ("low stock" if p.stock_state == "low" else "out of stock")
            return (f"{p.name} ({p.category.name}) is ${p.price}/vial in {', '.join(p.sizes)}, "
                    f"released at {p.purity} purity and currently {stock}. {p.description} "
                    f"A COA is available on request. {DISCLAIMER}")
    if any(w in q for w in ["ship", "delivery", "arrive", "how long", "track"]):
        return (f"Orders ship directly from our manufacturing partner \u2014 allow "
                f"{_window(site)} days for delivery, in plain, discreet, tracked packaging. "
                "Shipments may be subject to customs clearance, which can affect timing. "
                f"{DISCLAIMER}")
    if any(w in q for w in ["coa", "test", "purity", "quality", "hplc", "lab"]):
        return ("Every batch is independently third-party tested by HPLC and mass spec to a "
                f"≥99% purity threshold, and a batch-specific COA is available for any product. {DISCLAIMER}")
    if any(w in q for w in ["pay", "checkout", "order", "return", "refund", "code", "discount"]):
        promo = getattr(site, "promo_code", "") if site else ""
        extra = f" Use code {promo} for 10% off." if promo else ""
        return (f"Add items to your cart and check out on-site.{extra} Questions about an order? "
                f"Reach our team from the Contact section. {DISCLAIMER}")
    cats = sorted({p.category.name for p in products})
    return (f"Happy to help. {brand} carries research compounds across {', '.join(cats)}. "
            f"Ask about a specific compound, purity/COAs, or shipping and I'll point you the right way. {DISCLAIMER}")
