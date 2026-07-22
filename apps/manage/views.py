from decimal import Decimal

from django.contrib import messages
from .access import console_required
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


@console_required
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


@console_required
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


@console_required
def order_detail(request, pk):
    order = get_object_or_404(Order.objects.select_related("site"), pk=pk)
    if request.method == "POST":
        new_status = request.POST.get("status")
        if new_status in dict(Order.STATUS):
            order.status = new_status
            order.save(update_fields=["status"])
            messages.success(request, f"Order {order.number} → {order.get_status_display()}.")
        return redirect(f"{request.resolver_match.namespace}:order_detail", pk=pk)
    return render(request, "manage/order_detail.html", {
        "nav": "orders", "order": order, "items": order.items.all(), "statuses": Order.STATUS,
    })


@console_required
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


@console_required
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


@console_required
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
            elif action == "email" and body and selected.email:
                from apps.mailer import mailer
                subject = request.POST.get("subject") or "A note from SmashFat BioLabs"
                mailer.customer_message(selected.email, subject, body, site=selected.site)
                messages.success(request, f"Email sent to {selected.email}.")
                return redirect(f"{request.path}?contact={selected.pk}")
    for c in contacts:
        c.last = c.messages.last()
    return render(request, "manage/messages.html", {
        "nav": "messages", "contacts": contacts, "selected": selected,
        "thread": thread, "draft": draft,
    })


@console_required
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


@console_required
def numbers(request):
    from django.conf import settings as _settings

    from apps.comms.models import PhoneNumber as _PN
    if request.method == "POST":
        n = get_object_or_404(_PN, pk=request.POST.get("number_id"))
        old_greeting = n.greeting
        n.label = request.POST.get("label", n.label)[:80]
        n.greeting = request.POST.get("greeting", n.greeting)[:1000]
        n.sms_enabled = request.POST.get("sms_enabled") == "1"
        n.voice_enabled = request.POST.get("voice_enabled") == "1"
        n.ivr_enabled = request.POST.get("ivr_enabled") == "1"
        n.ai_intake = request.POST.get("ai_intake") == "1"
        n.is_active = request.POST.get("is_active") == "1"
        greeting_changed = n.greeting != old_greeting
        if greeting_changed:
            # The pre-generated ElevenLabs mp3 is now stale — drop it so calls use
            # the neural Polly voice until it's regenerated.
            n.greeting_audio = ""
        n.save()
        msg = f"Saved settings for {n.display_phone}."
        if greeting_changed:
            msg += " Greeting changed — run generate_greeting_audio to refresh the ElevenLabs voice."
        messages.success(request, msg)
        return redirect(request.path)
    return render(request, "manage/numbers.html", {
        "nav": "numbers",
        "numbers": PhoneNumber.objects.select_related("site").all(),
        "optouts": OptOut.objects.filter(action="opt_out")[:100],
        "live": _settings.COMMS_LIVE,
    })


@console_required
def emails(request):
    from django.conf import settings as _settings

    from apps.mailer.models import EmailLog
    qs = EmailLog.objects.select_related("site").all()
    kind = request.GET.get("kind", "")
    if kind:
        qs = qs.filter(kind=kind)
    return render(request, "manage/emails.html", {
        "nav": "emails", "logs": qs[:300], "count": qs.count(),
        "kinds": EmailLog.KIND, "kind": kind, "live": _settings.MAIL_LIVE,
        "stub_count": EmailLog.objects.filter(status="stub").count(),
        "sent_count": EmailLog.objects.filter(status="sent").count(),
        "failed_count": EmailLog.objects.filter(status="failed").count(),
    })


@console_required
def team(request):
    """Owner-only staff management: invite, resend set-password link, and
    activate/deactivate walled portal users — no console needed."""
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group
    from django.contrib.auth.tokens import default_token_generator
    from django.urls import reverse
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    from apps.manage.access import PORTAL_GROUP
    from apps.mailer import mailer

    if not request.user.is_superuser:
        messages.error(request, "Only the owner can manage staff.")
        return redirect(f"{request.resolver_match.namespace}:dashboard")

    User = get_user_model()
    group, _ = Group.objects.get_or_create(name=PORTAL_GROUP)

    def _link(u):
        uid = urlsafe_base64_encode(force_bytes(u.pk))
        token = default_token_generator.make_token(u)
        return request.build_absolute_uri(reverse("password_reset_confirm", args=[uid, token]))

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "invite":
            username = (request.POST.get("username") or "").strip()
            email = (request.POST.get("email") or "").strip()
            if not username or not email:
                messages.error(request, "Username and email are both required.")
            else:
                u, made = User.objects.get_or_create(username=username, defaults={"email": email})
                u.is_staff = False
                u.is_superuser = False
                u.email = email or u.email
                if made:
                    u.set_unusable_password()
                u.save()
                u.groups.add(group)
                mailer.send_invite(u, _link(u), invited_by=request.user.get_username())
                messages.success(request, f"Invited {username}. Set-password link: {_link(u)}")
            return redirect(request.path)
        u = get_object_or_404(User, pk=request.POST.get("user_id"))
        if action == "reset":
            mailer.send_invite(u, _link(u), invited_by=request.user.get_username())
            messages.success(request, f"Set-password link for {u.get_username()}: {_link(u)}")
        elif action == "deactivate":
            u.is_active = False
            u.save(update_fields=["is_active"])
            messages.success(request, f"{u.get_username()} deactivated.")
        elif action == "activate":
            u.is_active = True
            u.save(update_fields=["is_active"])
            messages.success(request, f"{u.get_username()} reactivated.")
        elif action == "remove":
            u.groups.remove(group)
            messages.success(request, f"{u.get_username()} removed from the portal.")
        return redirect(request.path)

    staff = list(group.user_set.all().order_by("username"))
    return render(request, "manage/team.html", {"nav": "team", "staff": staff})


@console_required
def compliance(request):
    """SMS/telephony compliance hub — consent audit, STOP/HELP/START trail,
    opt-outs, editable keyword replies, and toll-free verification status."""
    import csv

    from django.http import HttpResponse as _Csv

    from apps.comms.models import (
        ComplianceConfig, OptOut, SmsConsent, SmsKeywordEvent, TwilioVerificationTracker,
    )
    cfg = ComplianceConfig.get_solo()
    for k in ("toll_free", "a2p_10dlc"):
        TwilioVerificationTracker.objects.get_or_create(kind=k)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "save_replies":
            cfg.business_name = request.POST.get("business_name", cfg.business_name)[:120]
            cfg.stop_reply = request.POST.get("stop_reply", cfg.stop_reply)[:300]
            cfg.help_reply = request.POST.get("help_reply", cfg.help_reply)[:300]
            cfg.start_reply = request.POST.get("start_reply", cfg.start_reply)[:300]
            cfg.save()
            messages.success(request, "Compliance replies saved.")
        elif action == "save_verification":
            t = get_object_or_404(TwilioVerificationTracker, pk=request.POST.get("tracker_id"))
            if request.POST.get("status") in dict(TwilioVerificationTracker.STATUS):
                t.status = request.POST["status"]
                t.number = request.POST.get("number", t.number)[:20]
                t.notes = request.POST.get("notes", t.notes)[:300]
                t.save()
                messages.success(request, "Verification status updated.")
        return redirect(request.path)

    export = request.GET.get("export")
    if export in ("consent", "keywords"):
        resp = _Csv(content_type="text/csv")
        resp["Content-Disposition"] = f"attachment; filename=sms_{export}.csv"
        w = csv.writer(resp)
        if export == "consent":
            w.writerow(["created_at", "phone", "event", "category", "source",
                        "ip_address", "message_sid", "note", "site"])
            for c in SmsConsent.objects.select_related("site")[:5000]:
                w.writerow([c.created_at.isoformat(), c.e164, c.event_type, c.category,
                            c.source, c.ip_address or "", c.message_sid, c.note,
                            getattr(c.site, "domain", "")])
        else:
            w.writerow(["created_at", "phone", "keyword", "raw_body", "receiving_number",
                        "reply_sent", "message_sid", "site"])
            for k in SmsKeywordEvent.objects.select_related("site")[:5000]:
                w.writerow([k.created_at.isoformat(), k.e164, k.keyword, k.raw_body,
                            k.receiving_number, k.reply_sent, k.message_sid,
                            getattr(k.site, "domain", "")])
        return resp

    return render(request, "manage/compliance.html", {
        "nav": "compliance", "cfg": cfg,
        "consents": SmsConsent.objects.select_related("site")[:200],
        "keywords": SmsKeywordEvent.objects.select_related("site")[:200],
        "optouts": OptOut.objects.filter(action="opt_out")[:200],
        "trackers": TwilioVerificationTracker.objects.all(),
        "n_optin": SmsConsent.objects.filter(event_type__in=["opt_in", "resubscribe"]).count(),
        "n_optout": SmsConsent.objects.filter(event_type="opt_out").count(),
        "n_keywords": SmsKeywordEvent.objects.count(),
    })


@console_required
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


@console_required
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
            elif action == "gen_image":
                from apps.ai import images
                accent = (post.site.palette or {}).get("accent", "#4f8ff7")
                img = images.generate_blog_image(
                    post.keyword or post.title, site=post.site, accent=accent, slug=post.slug)
                if img:
                    post.hero_image = img
                    post.save(update_fields=["hero_image"])
                    messages.success(request, "AI hero image generated.")
                else:
                    messages.error(
                        request,
                        "AI image generation is off. Set PEPTIDENET_AI_LIVE=1 + OPENAI_API_KEY "
                        "(and pip install openai) on the server to enable it.")
            elif action == "set_image":
                from apps.blog.models import BLOG_HERO_POOL
                img = request.POST.get("hero_image", "")
                # Allow the stock pool, an AI-generated /static/blog/ image, or blank (SVG).
                safe_ai = img.startswith("/static/blog/") and ".." not in img
                if img in BLOG_HERO_POOL or safe_ai or img == "":
                    post.hero_image = img
                    post.save(update_fields=["hero_image"])
                    messages.success(request, "Hero image updated." if img else "Reverted to SVG banner.")
        return redirect(request.path)

    from apps.blog.models import BLOG_HERO_POOL
    from apps.blog.models import BlogPost as BP
    posts = BP.objects.select_related("site").all()[:200]
    return render(request, "manage/blog.html", {
        "nav": "blog", "posts": posts, "hero_pool": BLOG_HERO_POOL,
        "sites": Site.objects.filter(is_active=True),
        "flagged": BP.objects.filter(compliance_status="flagged").count(),
        "review": BP.objects.filter(status="needs_review").count(),
        "published": BP.objects.filter(status="published").count(),
    })


@console_required
def security(request):
    from apps.security.models import SecurityEvent
    events = SecurityEvent.objects.all()
    by_kind = events.values("kind").annotate(n=Count("id")).order_by("-n")
    return render(request, "manage/security.html", {
        "nav": "security", "events": events[:200], "by_kind": by_kind,
        "total": events.count(),
    })
