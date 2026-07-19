from decimal import Decimal

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, DecimalField, F, Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render

from apps.catalog.models import Category, Product
from apps.leads.models import Lead
from apps.orders.models import Order, OrderItem
from apps.stores.models import Site

# One place to change what "revenue" counts as.
REVENUE_STATUSES = ["paid", "fulfilled"]


def _money(x):
    return Decimal(x or 0)


@staff_member_required
def dashboard(request):
    orders = Order.objects.all()
    money = lambda qs, f: qs.aggregate(  # noqa: E731
        s=Coalesce(Sum(f), Decimal("0"), output_field=DecimalField())
    )["s"]
    realized = orders.filter(status__in=REVENUE_STATUSES)
    revenue = money(realized, "total")
    cogs = money(realized, "cost_total")
    gross_profit = revenue - cogs
    margin_pct = round(gross_profit / revenue * 100, 1) if revenue else 0
    pipeline = money(orders.filter(status="pending_payment"), "total")

    # Inventory valuation (on-hand) at cost and at retail.
    inv = Product.objects.filter(is_active=True)
    inv_cost = sum((p.stock_value_cost for p in inv), Decimal("0"))
    inv_retail = sum((p.stock_value_retail for p in inv), Decimal("0"))

    per_site = (
        Site.objects.annotate(
            n_orders=Count("orders"),
            gross=Coalesce(
                Sum("orders__total"), Decimal("0"), output_field=DecimalField()
            ),
        ).order_by("-gross")
    )

    low_stock = Product.objects.filter(
        track_inventory=True, is_active=True, stock_qty__lte=F("low_stock_threshold")
    ).order_by("stock_qty")

    ctx = {
        "nav": "dashboard",
        "kpi": {
            "orders": orders.count(),
            "pending": orders.filter(status="pending_payment").count(),
            "revenue": revenue,
            "cogs": cogs,
            "gross_profit": gross_profit,
            "margin_pct": margin_pct,
            "pipeline": pipeline,
            "inv_cost": inv_cost,
            "inv_retail": inv_retail,
            "products": Product.objects.filter(is_active=True).count(),
            "sites": Site.objects.filter(is_active=True).count(),
            "low_stock": low_stock.count(),
            "leads": Lead.objects.count(),
        },
        "per_site": per_site,
        "recent_orders": orders.select_related("site")[:8],
        "low_stock": low_stock[:8],
    }
    return render(request, "manage/dashboard.html", ctx)


@staff_member_required
def orders(request):
    qs = Order.objects.select_related("site").all()
    site = request.GET.get("site", "")
    status = request.GET.get("status", "")
    q = request.GET.get("q", "").strip()
    if site:
        qs = qs.filter(site__domain=site)
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(email__icontains=q) | Q(name__icontains=q))
    ctx = {
        "nav": "orders",
        "orders": qs[:300],
        "sites": Site.objects.all(),
        "statuses": Order.STATUS,
        "f": {"site": site, "status": status, "q": q},
        "count": qs.count(),
    }
    return render(request, "manage/orders.html", ctx)


@staff_member_required
def order_detail(request, pk):
    order = get_object_or_404(Order.objects.select_related("site"), pk=pk)
    if request.method == "POST":
        new_status = request.POST.get("status")
        if new_status in dict(Order.STATUS):
            order.status = new_status
            order.save(update_fields=["status"])
            messages.success(request, f"Order {order.number} → {order.get_status_display()}.")
        return redirect("manage:order_detail", pk=pk)
    return render(request, "manage/order_detail.html", {
        "nav": "orders", "order": order, "items": order.items.all(), "statuses": Order.STATUS,
    })


@staff_member_required
def inventory(request):
    if request.method == "POST":
        pid = request.POST.get("product_id")
        product = get_object_or_404(Product, pk=pid)
        action = request.POST.get("action")
        if action == "save":
            product.price = request.POST.get("price") or product.price
            product.unit_cost = request.POST.get("unit_cost") or product.unit_cost
            product.stock_qty = int(request.POST.get("stock_qty") or 0)
            product.low_stock_threshold = int(
                request.POST.get("low_stock_threshold") or product.low_stock_threshold
            )
            product.is_active = request.POST.get("is_active") == "on"
            product.save()
            messages.success(request, f"{product.name} updated.")
        elif action == "restock":
            add = int(request.POST.get("amount") or 0)
            Product.objects.filter(pk=pid).update(stock_qty=F("stock_qty") + add)
            messages.success(request, f"Restocked {product.name} (+{add}).")
        return redirect(f"{request.path}?cat={request.GET.get('cat', '')}")

    qs = Product.objects.select_related("category").all()
    cat = request.GET.get("cat", "")
    if cat:
        qs = qs.filter(category__slug=cat)
    # Units sold per product (paid/fulfilled) for a quick sell-through view.
    sold = {
        r["product_id"]: r["n"]
        for r in OrderItem.objects.filter(order__status__in=REVENUE_STATUSES)
        .values("product_id").annotate(n=Sum("qty"))
        if r["product_id"]
    }
    products = list(qs)
    for p in products:
        p.units_sold = sold.get(p.id, 0)
    ctx = {
        "nav": "inventory",
        "products": products,
        "categories": Category.objects.all(),
        "cat": cat,
        "low_count": sum(1 for p in products if p.stock_state in ("low", "out")),
        "total_cost": sum((p.stock_value_cost for p in products), Decimal("0")),
        "total_retail": sum((p.stock_value_retail for p in products), Decimal("0")),
    }
    return render(request, "manage/inventory.html", ctx)


@staff_member_required
def leads(request):
    return render(request, "manage/leads.html", {
        "nav": "leads",
        "leads": Lead.objects.select_related("site")[:300],
    })


# ---- Communications (SMS / calls / voicemail) ----
from apps.comms import phone as _phone  # noqa: E402
from apps.comms import providers as _providers  # noqa: E402
from apps.comms import sms as _sms  # noqa: E402
from apps.comms.models import (  # noqa: E402
    Call, Contact, Message, OptOut, PhoneNumber, Voicemail,
)


@staff_member_required
def messages_inbox(request):
    # Threads = contacts that have any message, most-recent first.
    contacts = list(
        Contact.objects.filter(messages__isnull=False).distinct()
        .select_related("site")
    )
    contacts.sort(key=lambda c: c.messages.last().created_at if c.messages.exists() else c.created_at,
                  reverse=True)
    sel_id = request.GET.get("contact")
    selected = None
    thread = []
    draft = ""
    if sel_id:
        selected = get_object_or_404(Contact, pk=sel_id)
        thread = list(selected.messages.all())
        if request.method == "POST":
            action = request.POST.get("action")
            body = request.POST.get("body", "").strip()
            if action == "draft":
                draft = _providers.draft_reply(thread, selected.name)
            elif action == "send" and body:
                _sms.send_sms(selected.e164, body,
                              category=request.POST.get("category", "transactional"),
                              site=selected.site,
                              ai_generated=request.POST.get("ai") == "1")
                messages.success(request, "Message sent.")
                return redirect(f"{request.path}?contact={selected.pk}")
    for c in contacts:
        c.last = c.messages.last()
    return render(request, "manage/messages.html", {
        "nav": "messages", "contacts": contacts, "selected": selected,
        "thread": thread, "draft": draft,
    })


@staff_member_required
def calls(request):
    if request.method == "POST" and request.POST.get("mark_listened"):
        Voicemail.objects.filter(pk=request.POST["mark_listened"]).update(listened=True)
        return redirect(request.path)
    # Merge calls + voicemails into one feed.
    feed = []
    for c in Call.objects.select_related("site", "contact")[:150]:
        feed.append({"kind": "call", "obj": c, "when": c.created_at})
    for v in Voicemail.objects.select_related("site", "contact")[:150]:
        feed.append({"kind": "voicemail", "obj": v, "when": v.created_at})
    feed.sort(key=lambda x: x["when"], reverse=True)
    return render(request, "manage/calls.html", {
        "nav": "calls", "feed": feed[:200],
        "open_vm": Voicemail.objects.filter(listened=False).count(),
    })


@staff_member_required
def numbers(request):
    from django.conf import settings as _settings
    return render(request, "manage/numbers.html", {
        "nav": "numbers",
        "numbers": PhoneNumber.objects.select_related("site").all(),
        "optouts": OptOut.objects.filter(action="opt_out")[:100],
        "live": _settings.COMMS_LIVE,
    })


@staff_member_required
def ai_usage(request):
    from django.conf import settings as _settings

    from apps.ai.models import AgentRun
    runs = AgentRun.objects.all()
    by_purpose = runs.values("purpose").annotate(
        n=Count("id"),
        cost=Coalesce(Sum("cost_usd"), Decimal("0"), output_field=DecimalField()),
    ).order_by("-n")
    total_cost = runs.aggregate(
        s=Coalesce(Sum("cost_usd"), Decimal("0"), output_field=DecimalField()))["s"]
    return render(request, "manage/ai_usage.html", {
        "nav": "ai", "live": _settings.AI_LIVE, "runs": runs.select_related("site")[:100],
        "by_purpose": by_purpose, "total_cost": total_cost, "total": runs.count(),
    })


@staff_member_required
def blog(request):
    from django.utils import timezone

    from apps.blog import generator, guardrails, keywords
    from apps.blog.models import BlogPost
    from apps.stores.models import Site

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "generate":
            site = Site.objects.filter(domain=request.POST.get("site")).first()
            if site:
                kw = request.POST.get("keyword") or keywords.for_site(site)[0]
                p = generator.generate(site, kw)
                messages.success(request, f"Draft generated: “{p.title}” [{p.compliance_status}].")
        else:
            post = get_object_or_404(BlogPost, pk=request.POST.get("post_id"))
            if action == "publish":
                if post.can_publish:
                    post.status = "published"
                    post.published_at = post.published_at or timezone.now()
                    post.save()
                    messages.success(request, f"Published: {post.title}")
                else:
                    messages.error(request, "Blocked: fix the flagged compliance issues first.")
            elif action == "rescan":
                r = guardrails.review(post.body)
                post.body = r["text"]; post.compliance_status = r["status"]
                post.compliance_notes = r["notes"]; post.save()
                messages.success(request, "Re-scanned against guardrails.")
            elif action == "unpublish":
                post.status = "needs_review"; post.save()
                messages.success(request, "Moved back to review.")
            elif action == "archive":
                post.status = "archived"; post.save()
        return redirect(request.path)

    from apps.blog.models import BlogPost as BP
    posts = BP.objects.select_related("site").all()[:200]
    return render(request, "manage/blog.html", {
        "nav": "blog", "posts": posts,
        "sites": Site.objects.filter(is_active=True),
        "flagged": BP.objects.filter(compliance_status="flagged").count(),
        "review": BP.objects.filter(status="needs_review").count(),
        "published": BP.objects.filter(status="published").count(),
    })


@staff_member_required
def security(request):
    from apps.security.models import SecurityEvent
    events = SecurityEvent.objects.all()
    by_kind = events.values("kind").annotate(n=Count("id")).order_by("-n")
    return render(request, "manage/security.html", {
        "nav": "security", "events": events[:200], "by_kind": by_kind,
        "total": events.count(),
    })
