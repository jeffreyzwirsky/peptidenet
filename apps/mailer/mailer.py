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


# ---- Transactional -------------------------------------------------------

def order_confirmation(order):
    """Customer confirmation + a new-order alert to staff."""
    lines = "\n".join(f"  {i.qty}x {i.product_name} — ${i.line_total}" for i in order.items.all())
    if order.email:
        text = (
            f"Hi {order.name or 'there'},\n\n{order.confirmation_message}\n\n"
            f"Order {order.number}\n{lines}\nTotal: ${order.total}\n\n"
            "This is a research-use-only order. We'll follow up with next steps.\n\n"
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
    text = (
        f"New voicemail from {vm.from_number}\n"
        f"Site: {getattr(vm.site, 'domain', '—')}  Duration: {vm.duration_sec}s\n\n"
        f"Transcript:\n{vm.transcript or '(not transcribed)'}\n\n"
        f"Listen: {_portal('/portal/calls/')}"
    )
    return _send("voicemail", f"[Voicemail] {vm.from_number}", _alerts_to(), text, site=vm.site)


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
