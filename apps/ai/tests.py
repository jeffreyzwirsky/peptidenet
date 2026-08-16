import json

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase

from apps.stores.models import Site

from .models import AgentRun, AiConversation


class AiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog")
        call_command("seed_sites")

    def setUp(self):
        # The /ai/ask/ rate limiter is CACHE-backed, and the cache is not part
        # of the per-test transaction that gets rolled back — so state leaks
        # forwards between tests. apps.security's
        # test_rate_limit_returns_429_and_logs deliberately fires 20 requests at
        # this exact endpoint to exhaust the bucket, and leaves it exhausted.
        # Every test in this class then gets 429 instead of an answer.
        #
        # It never showed because Django runs apps alphabetically and "ai" sorts
        # before "security". `manage.py test --shuffle` fails 5 tests here at
        # 24cde4f, before any of tonight's changes. A suite that only passes in
        # one order is not measuring what it appears to be measuring.
        cache.clear()

    def test_ask_returns_grounded_answer_and_ledgers(self):
        r = self.client.post("/ai/ask/", json.dumps({"question": "Do you ship to Alberta?"}),
                             content_type="application/json", HTTP_HOST="smashfat.ca")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["ok"])
        self.assertIn("ship", data["answer"].lower())
        self.assertEqual(AgentRun.objects.count(), 1)          # ledgered
        self.assertEqual(AgentRun.objects.first().provider, "stub")

    def test_ask_knows_products(self):
        r = self.client.post("/ai/ask/", json.dumps({"question": "Tell me about BPC-157"}),
                             content_type="application/json", HTTP_HOST="smashfat.ca")
        self.assertIn("BPC-157", r.json()["answer"])

    def test_ask_logs_conversation(self):
        self.client.post("/ai/ask/", json.dumps({"question": "hi"}),
                         content_type="application/json", HTTP_HOST="smashfat.ca")
        self.assertTrue(AiConversation.objects.exists())

    def test_empty_question_rejected(self):
        r = self.client.post("/ai/ask/", json.dumps({"question": "  "}),
                             content_type="application/json", HTTP_HOST="smashfat.ca")
        self.assertEqual(r.status_code, 400)

    def test_honeypot_short_circuits(self):
        r = self.client.post("/ai/ask/",
                             json.dumps({"question": "buy now", "company_website": "spam.example"}),
                             content_type="application/json", HTTP_HOST="smashfat.ca")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(AgentRun.objects.count(), 0)          # no LLM/stub call for bots
