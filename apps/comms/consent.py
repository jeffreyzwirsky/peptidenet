"""SMS consent + keyword logging — the TCPA/CASL evidence layer.

`OptOut` stays the active send-blocker (see sms.py). These helpers write the
immutable `SmsConsent` audit and the `SmsKeywordEvent` trail, capturing the
spoof-resistant client IP when the consent came from a web form.
"""
from apps.security.utils import client_ip

from .models import SmsConsent, SmsKeywordEvent


def log_consent(e164, event_type, category="marketing", source="keyword",
                request=None, site=None, note="", message_sid=""):
    ip = None
    ua = ""
    if request is not None:
        try:
            ip = client_ip(request)
        except Exception:
            ip = None
        ua = request.META.get("HTTP_USER_AGENT", "")[:300]
    return SmsConsent.objects.create(
        e164=e164, event_type=event_type, category=category, source=source,
        ip_address=ip, user_agent=ua, note=note[:300], message_sid=message_sid, site=site,
    )


def log_keyword_event(e164, keyword, raw_body="", receiving_number="",
                      message_sid="", reply_text="", site=None):
    return SmsKeywordEvent.objects.create(
        e164=e164, keyword=keyword, raw_body=(raw_body or "")[:300],
        receiving_number=receiving_number, message_sid=message_sid,
        reply_sent=bool(reply_text), reply_text=(reply_text or "")[:300], site=site,
    )
