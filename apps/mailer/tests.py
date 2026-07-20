from django.test import TestCase, override_settings

from apps.mailer import mailer
from apps.mailer.models import EmailLog

# Django's test runner swaps EMAIL_BACKEND for locmem; force ours so the
# stub-logging path (and EmailLog writes) actually runs.
REAL_BACKEND = "apps.mailer.backend.MailgunAPIBackend"


@override_settings(EMAIL_BACKEND=REAL_BACKEND, MAIL_LIVE=False)
class MailerStubTests(TestCase):
    def test_stub_send_is_logged_and_sends_nothing(self):
        ok = mailer.customer_message("cust@example.com", "Hello", "Body text")
        self.assertTrue(ok)  # handled (stubbed), not an error
        e = EmailLog.objects.latest("id")
        self.assertEqual(e.status, "stub")
        self.assertEqual(e.kind, "customer")
        self.assertEqual(e.to_email, "cust@example.com")

    def test_alert_helpers_are_safe(self):
        # No recipients configured edge-case + a normal alert both return cleanly.
        self.assertTrue(mailer._send("other", "Subj", ["ops@example.com"], "body"))
        self.assertFalse(mailer._send("other", "Subj", [], "body"))


class PasswordResetPageTests(TestCase):
    def test_reset_request_page_loads(self):
        r = self.client.get("/account/password/reset/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Reset your password")
