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
