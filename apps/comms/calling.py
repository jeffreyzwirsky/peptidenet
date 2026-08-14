"""Click-to-call: ring the operator, then bridge them to the customer.

Why this shape rather than dialling the customer directly: a call originated
straight to the customer rings them while nobody is on our end, so they answer
to silence. Ringing the operator first means a human is already holding the
line, and the customer's phone shows the business number rather than anyone's
personal mobile.
"""
from django.conf import settings
from django.core.cache import cache

from . import phone, providers, voice
from .models import Call, ComplianceConfig, PhoneNumber
from .sms import resolve_contact

# Outbound calling is the one feature here that turns a login into money.
# International premium-rate ranges are where revenue-share fraud lives, so the
# default is North America only, with a hard hourly ceiling. Both are settings
# rather than constants so a real need can widen them deliberately.
_CAP_KEY = "comms:outbound-calls:hour"


# Both limits are read at CALL time, not import time. Read at import they bake
# into the module and an operator raising the cap in .env would see no change
# until the process restarted — the kind of "I changed it and nothing happened"
# that ends with someone disabling the brake entirely.
def _allowed_prefixes():
    return tuple(getattr(settings, "COMMS_CALL_ALLOWED_PREFIXES", None) or ("+1",))


def _max_calls_per_hour():
    return int(getattr(settings, "COMMS_MAX_CALLS_PER_HOUR", 20) or 20)


def _check_destination(e164):
    """Refuse anything outside the allowed dialling prefixes."""
    allowed = _allowed_prefixes()
    if not any(e164.startswith(p) for p in allowed):
        raise ValueError(
            f"Refused: {e164} is outside the allowed dialling range "
            f"({', '.join(allowed)}). Widen "
            "COMMS_CALL_ALLOWED_PREFIXES if this is deliberate.")


def _check_cap():
    """Hard ceiling on outbound calls per hour, across all operators."""
    cap = _max_calls_per_hour()
    used = cache.get(_CAP_KEY, 0)
    if used >= cap:
        raise ValueError(
            f"Refused: outbound call cap reached ({cap}/hour). "
            "This is the toll-fraud brake — wait, or raise COMMS_MAX_CALLS_PER_HOUR.")
    cache.set(_CAP_KEY, used + 1, timeout=3600)


def operator_number():
    """The mobile that click-to-call rings first. Blank = feature unavailable."""
    return ComplianceConfig.get_solo().operator_callback_e164


def place_bridge_call(customer_number, site=None, from_number=None, operator=None,
                      placed_by=""):
    """Ring the operator, bridge to `customer_number`. Returns the Call row.

    A failed origination is still recorded — a silent failure in a sales tool is
    worse than a logged one — and `placed_by` is stamped on the row so an
    unexpected call bill can be traced to a person rather than to "the system".
    """
    customer = phone.normalize(customer_number)
    operator = phone.normalize(operator or operator_number())
    if not customer:
        raise ValueError("No customer number to call.")
    _check_destination(customer)
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

    _check_cap()
    twiml = voice.bridge_twiml(customer, from_number)
    sid, err = providers.place_call(operator, from_number, twiml)
    who = f" by {placed_by}" if placed_by else ""
    return Call.objects.create(
        direction="out", status="failed" if err else "initiated",
        site=site, contact=resolve_contact(customer, site=site),
        from_number=from_number, to_number=customer, twilio_sid=sid,
        transcript=(f"click-to-call via {operator}{who}"
                    + (f" — ERROR: {err}" if err else "")),
    )
