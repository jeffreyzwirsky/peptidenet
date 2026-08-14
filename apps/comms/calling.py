"""Click-to-call: ring the operator, then bridge them to the customer.

Why this shape rather than dialling the customer directly: a call originated
straight to the customer rings them while nobody is on our end, so they answer
to silence. Ringing the operator first means a human is already holding the
line, and the customer's phone shows the business number rather than anyone's
personal mobile.
"""
from . import phone, providers, voice
from .models import Call, ComplianceConfig, PhoneNumber
from .sms import resolve_contact


def operator_number():
    """The mobile that click-to-call rings first. Blank = feature unavailable."""
    return ComplianceConfig.get_solo().operator_callback_e164


def place_bridge_call(customer_number, site=None, from_number=None, operator=None):
    """Ring the operator, bridge to `customer_number`. Returns the Call row.

    A failed origination is still recorded — a silent failure in a sales tool is
    worse than a logged one.
    """
    customer = phone.normalize(customer_number)
    operator = phone.normalize(operator or operator_number())
    if not customer:
        raise ValueError("No customer number to call.")
    if not operator:
        raise ValueError(
            "No operator callback number set — add your mobile under Phone Numbers "
            "before using click-to-call.")

    if not from_number:
        qs = PhoneNumber.objects.filter(is_active=True, voice_enabled=True)
        if site:
            from_number = getattr(qs.filter(site=site).first(), "e164", "")
        from_number = from_number or getattr(qs.first(), "e164", "")
    if not from_number:
        raise ValueError("No voice-enabled business number is configured.")

    twiml = voice.bridge_twiml(customer, from_number)
    sid, err = providers.place_call(operator, from_number, twiml)
    return Call.objects.create(
        direction="out", status="failed" if err else "initiated",
        site=site, contact=resolve_contact(customer, site=site),
        from_number=from_number, to_number=customer, twilio_sid=sid,
        transcript=(f"click-to-call via {operator}" + (f" — ERROR: {err}" if err else "")),
    )
