"""A Django email backend that sends through the Mailgun HTTP API and logs every
message to EmailLog. One credential (MAILGUN_API_KEY) powers ALL platform email —
transactional sends AND Django's built-in password-reset emails.

Inert until PEPTIDENET_MAIL_LIVE=1 AND a Mailgun key + domain are set: it logs a
'stub' EmailLog row and sends nothing, so the whole system runs without spending.
"""
import logging

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

log = logging.getLogger("mailer")


def mail_live():
    return bool(settings.MAIL_LIVE and settings.MAILGUN_API_KEY and settings.MAILGUN_DOMAIN)


class MailgunAPIBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        sent = 0
        for message in email_messages:
            if self._send_one(message):
                sent += 1
        return sent

    def _send_one(self, message):
        from .models import EmailLog

        headers = getattr(message, "extra_headers", {}) or {}
        kind = headers.get("X-Mail-Kind", "other")
        site = getattr(message, "site", None)
        to_list = list(message.to or [])
        to_str = ", ".join(to_list)[:254]
        from_email = message.from_email or settings.DEFAULT_FROM_EMAIL

        def _log(status, provider_id="", error=""):
            try:
                EmailLog.objects.create(
                    kind=kind if kind in dict(EmailLog.KIND) else "other",
                    status=status, to_email=to_str, from_email=from_email[:254],
                    subject=(message.subject or "")[:255], site=site,
                    provider_id=provider_id[:140], error=error[:255],
                )
            except Exception:  # never let logging break a send
                log.exception("EmailLog write failed")

        if not to_list:
            return False
        if not mail_live():
            log.info("[stub] email to %s: %s", to_str, message.subject)
            _log("stub")
            return True  # treat as handled so callers don't error

        try:  # pragma: no cover - only runs with real creds
            import requests

            data = {
                "from": from_email,
                "to": to_list,
                "subject": message.subject or "",
                "text": message.body or "",
                "o:tag": kind,
            }
            if message.cc:
                data["cc"] = list(message.cc)
            if message.bcc:
                data["bcc"] = list(message.bcc)
            if message.reply_to:
                data["h:Reply-To"] = ", ".join(message.reply_to)
            for content, mimetype in getattr(message, "alternatives", []) or []:
                if mimetype == "text/html":
                    data["html"] = content
            resp = requests.post(
                f"{settings.MAILGUN_BASE_URL}/{settings.MAILGUN_DOMAIN}/messages",
                auth=("api", settings.MAILGUN_API_KEY), data=data, timeout=20,
            )
            if resp.status_code // 100 == 2:
                _log("sent", provider_id=resp.json().get("id", ""))
                return True
            _log("failed", error=f"{resp.status_code}: {resp.text}")
            log.error("mailgun send failed %s: %s", resp.status_code, resp.text[:200])
            return False
        except Exception as e:  # pragma: no cover
            _log("failed", error=str(e))
            log.exception("mailgun send error")
            if not self.fail_silently:
                return False
            return False
