"""The single SMS send + inbound path — opt-out guard mirrors SMASH's send_sms."""
from . import phone, providers
from .models import Contact, Message, OptOut, PhoneNumber

STOP_WORDS = {"STOP", "STOPALL", "UNSUBSCRIBE", "CANCEL", "END", "QUIT"}
START_WORDS = {"START", "YES", "UNSTOP", "SUBSCRIBE"}
HELP_WORDS = {"HELP", "INFO"}


def is_opted_out(e164):
    e164 = phone.normalize(e164)
    last = OptOut.objects.filter(e164=e164, action__in=["opt_out", "opt_in"]).first()
    return bool(last and last.action == "opt_out")


def resolve_contact(e164, site=None, name="", email=""):
    e164 = phone.normalize(e164)
    contact, created = Contact.objects.get_or_create(
        e164=e164, defaults={"site": site, "name": name, "email": email}
    )
    return contact


def pick_from_number(to_e164, site=None):
    """Region-aware send number (like SMASH MB→431 / SK→639 / AB→825)."""
    region = phone.region_of(to_e164)
    qs = PhoneNumber.objects.filter(is_active=True, sms_enabled=True)
    if site:
        site_qs = qs.filter(site=site)
        if region:
            m = site_qs.filter(region=region).first()
            if m:
                return m
        if site_qs.exists():
            return site_qs.first()
    if region:
        m = qs.filter(region=region).first()
        if m:
            return m
    return qs.first()


def send_sms(to_number, body, category="transactional", site=None, from_number=None,
             ai_generated=False):
    """Guarded send: marketing to opted-out numbers is blocked; transactional flows."""
    to_e164 = phone.normalize(to_number)
    contact = resolve_contact(to_e164, site=site)
    if category == "marketing" and (is_opted_out(to_e164) or contact.marketing_opted_out):
        return Message.objects.create(
            direction="out", status="blocked", category=category, contact=contact,
            site=site, from_number=from_number or "", to_number=to_e164, body=body,
            ai_generated=ai_generated, error="recipient opted out of marketing",
        )
    if not from_number:
        num = pick_from_number(to_e164, site)
        from_number = num.e164 if num else ""
    sid, err = providers.send_sms(from_number, to_e164, body)
    return Message.objects.create(
        direction="out", status="failed" if err else "sent", category=category,
        contact=contact, site=site, from_number=from_number, to_number=to_e164,
        body=body, twilio_sid=sid, error=err, ai_generated=ai_generated,
    )


def handle_inbound(from_number, to_number, body, site=None):
    """Log inbound SMS, resolve contact, handle STOP/HELP/START keywords.
    Returns (message, auto_reply_text|None)."""
    from_e164 = phone.normalize(from_number)
    contact = resolve_contact(from_e164, site=site)
    msg = Message.objects.create(
        direction="in", status="received", contact=contact, site=site,
        from_number=from_e164, to_number=phone.normalize(to_number), body=body,
    )
    word = (body or "").strip().upper().split()[0] if body.strip() else ""
    reply = None
    if word in STOP_WORDS:
        OptOut.objects.create(e164=from_e164, action="opt_out", keyword=word, site=site)
        Contact.objects.filter(pk=contact.pk).update(marketing_opted_out=True)
        reply = "You've been unsubscribed and won't receive further messages. Reply START to opt back in."
    elif word in START_WORDS:
        OptOut.objects.create(e164=from_e164, action="opt_in", keyword=word, site=site)
        Contact.objects.filter(pk=contact.pk).update(marketing_opted_out=False)
        reply = "You're re-subscribed. Reply STOP to opt out at any time."
    elif word in HELP_WORDS:
        OptOut.objects.create(e164=from_e164, action="help", keyword=word, site=site)
        reply = "Research-use-only supplies support. Msg&data rates may apply. Reply STOP to opt out."
    return msg, reply
