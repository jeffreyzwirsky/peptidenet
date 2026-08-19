"""High-level email helpers. Every send is logged to EmailLog by the backend and
is completely safe when email isn't live yet (it just records a 'stub' row).

Callers should still wrap these in try/except so a mail hiccup never breaks a
checkout, a webhook, or a form submit.
"""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

log = logging.getLogger("mailer")


def _send(kind, subject, to, text, html=None, site=None, from_email=None, reply_to=None):
    to = [t for t in (to if isinstance(to, (list, tuple)) else [to]) if t]
    if not to:
        return False
    msg = EmailMultiAlternatives(
        subject=subject, body=text,
        from_email=from_email or settings.DEFAULT_FROM_EMAIL, to=to,
        reply_to=[reply_to] if reply_to else (settings.MAIL_REPLY_TO and [settings.MAIL_REPLY_TO] or None),
        headers={"X-Mail-Kind": kind},
    )
    if html:
        msg.attach_alternative(html, "text/html")
    msg.site = site
    try:
        return bool(msg.send(fail_silently=True))
    except Exception:
        log.exception("mailer send failed (%s)", kind)
        return False


def _alerts_to():
    return list(settings.MAIL_ALERTS_TO or [])


def _portal(path=""):
    return settings.PORTAL_BASE_URL.rstrip("/") + path


def _order_url(order):
    """Customer-facing status page, on the domain they actually bought from —
    not the portal host."""
    return f"https://{order.site.domain}/order/{order.public_token}/"


# ---- Transactional -------------------------------------------------------

def order_confirmation(order):
    """Customer confirmation + a new-order alert to staff."""
    lines = "\n".join(f"  {i.qty}x {i.product_name} — ${i.line_total}" for i in order.items.all())
    if order.email:
        # The delivery window has to be in the confirmation too, not just on the
        # site — this email is what the customer keeps and refers back to on
        # day 9 when they're wondering where the package is.
        window = order.promised_window
        status_url = _order_url(order)
        text = (
            f"Hi {order.name or 'there'},\n\n{order.confirmation_message}\n\n"
            f"Order {order.number}\n{lines}\nTotal: ${order.total}\n\n"
            f"DELIVERY: Your order ships directly from our manufacturing partner. "
            f"Allow {window} for delivery. Shipments may be subject to customs "
            f"clearance, which can affect timing. We'll email you a tracking "
            f"number as soon as it ships.\n\n"
            f"Track your order: {status_url}\n\n"
            "This is a research-use-only order. These compounds are supplied as "
            "laboratory reference materials and are not for human or veterinary "
            "use.\n\n"
            "— SmashFat BioLabs"
        )
        _send("order", f"Your SmashFat BioLabs order {order.number}", order.email, text,
              site=order.site)
    staff = (
        f"New order {order.number} on {order.site.domain}\n"
        f"Customer: {order.name or '—'} <{order.email or 'no email'}>\n"
        f"Total: ${order.total}  (COGS ${order.cost_total}, profit ${order.profit})\n{lines}\n\n"
        f"{_portal('/portal/orders/')}"
    )
    _send("order", f"[New order] {order.number} — ${order.total}", _alerts_to(), staff,
          site=order.site)


def payment_confirmed(order):
    """Sent when a human confirms the payment landed. Every method we accept is
    manual, so this is the customer's signal that their money actually arrived."""
    if not order.email:
        return
    text = (
        f"Hi {order.name or 'there'},\n\n"
        f"We've confirmed payment for order {order.number}. It's now being placed "
        f"with our manufacturing partner, who ships directly to you.\n\n"
        f"Allow {order.promised_window} from today for delivery. We'll send a "
        f"tracking number the moment it dispatches.\n\n"
        f"Track your order: {_order_url(order)}\n\n"
        "For research use only. Not for human or veterinary use.\n\n"
        "— SmashFat BioLabs"
    )
    _send("order", f"Payment confirmed — order {order.number}", order.email, text,
          site=order.site)


def order_shipped(order):
    """Sent when the supplier's tracking number lands on the order."""
    if not order.email:
        return
    tracking = order.tracking_number or "—"
    carrier = f"{order.tracking_carrier} " if order.tracking_carrier else ""
    text = (
        f"Hi {order.name or 'there'},\n\n"
        f"Order {order.number} has shipped.\n\n"
        f"{carrier}Tracking: {tracking}\n"
        + (f"{order.tracking_url}\n" if order.tracking_url else "")
        + f"\nShipments may be subject to customs clearance, which can affect "
        f"delivery time.\n\n"
        f"Track your order: {_order_url(order)}\n\n"
        "For research use only. Not for human or veterinary use.\n\n"
        "— SmashFat BioLabs"
    )
    _send("order", f"Order {order.number} has shipped", order.email, text,
          site=order.site)


# ---- Staff alerts --------------------------------------------------------

def lead_alert(lead):
    text = (
        f"New {lead.get_kind_display().lower()} on {lead.site.domain}\n"
        f"From: {lead.name or '—'} <{lead.email or 'no email'}>\n"
        f"Rating: {lead.rating or '—'}\n\nMessage:\n{lead.message or '(none)'}\n\n"
        f"{_portal('/portal/leads/')}"
    )
    return _send("lead", f"[Lead] {lead.email or lead.name or 'new contact'} — {lead.site.domain}",
                 _alerts_to(), text, site=lead.site)


def voicemail_alert(vm):
    tag = f"{vm.urgency.upper()}" if vm.urgency in ("high", "urgent") else vm.urgency
    text = (
        f"New voicemail from {vm.from_number}\n"
        f"Site: {getattr(vm.site, 'domain', '—')}  Duration: {vm.duration_sec}s\n"
        f"AI triage: {vm.tier or '—'} · urgency {vm.urgency}"
        f"{' · ' + vm.tier_rationale if vm.tier_rationale else ''}\n\n"
        f"Transcript:\n{vm.transcript or '(not transcribed)'}\n\n"
        f"Listen: {_portal('/portal/calls/')}"
    )
    subject = f"[Voicemail · {tag}] {vm.from_number}"
    return _send("voicemail", subject, _alerts_to(), text, site=vm.site)


def sms_alert(message):
    text = (
        f"New text from {message.from_number} to {message.to_number}\n"
        f"Site: {getattr(message.site, 'domain', '—')}\n\n"
        f"{message.body}\n\nReply: {_portal('/portal/messages/')}"
    )
    return _send("sms", f"[SMS] {message.from_number}", _alerts_to(), text, site=message.site)


# ---- Customer follow-up (from the portal) --------------------------------

def customer_message(to_email, subject, body, site=None, reply_to=None):
    return _send("customer", subject, to_email, body, site=site, reply_to=reply_to)


# ---- Staff invite / password link ----------------------------------------

def send_invite(user, url, invited_by=""):
    text = (
        f"Hi {user.get_username()},\n\n"
        "You've been given access to the SmashFat BioLabs staff portal.\n"
        f"Set your password to get started:\n\n{url}\n\n"
        "This link is single-use and expires. After setting a password, sign in at\n"
        f"{_portal('/portal/')}\n\n— SmashFat BioLabs"
        + (f"\n(invited by {invited_by})" if invited_by else "")
    )
    return _send("invite", "Set up your SmashFat BioLabs staff account", user.email, text)


def health_alert(subject, report):
    """Operational alert to the addresses in MAIL_ALERTS_TO.

    Plain text on purpose. This is the message that arrives when something is
    already wrong, quite possibly at 07:10 on a phone, and the fastest thing to
    read is the thing that was going to be read anyway — the command's own
    output, unstyled and unwrapped.
    """
    return _send("health_alert", subject, _alerts_to(), report)
