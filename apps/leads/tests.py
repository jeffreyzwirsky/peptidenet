"""Lead review queue — the /manage/leads/ workflow.

Same fixtures pattern as apps/manage/tests.py: seed the catalogue + sites,
sign in a superuser, then drive the queue the way an operator would.
"""
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.leads.models import Lead
from apps.mailer.models import EmailLog
from apps.orders.models import Order
from apps.stores.models import Site


class LeadReviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog")
        call_command("seed_sites")
        cls.site = Site.objects.first()
        cls.boss = get_user_model().objects.create_user(
            "boss", password="x", is_staff=True, is_superuser=True
        )

    def setUp(self):
        self.client.force_login(self.boss)

    def _lead(self, **kw):
        defaults = dict(site=self.site, name="Pat", email="pat@example.com",
                        message="Do you ship to Manitoba?")
        defaults.update(kw)
        return Lead.objects.create(**defaults)

    # --- the queue ---

    def test_default_queue_shows_open_hides_closed_and_spam(self):
        open_lead = self._lead(message="open one")
        self._lead(message="closed one", status="closed")
        self._lead(message="spam one", status="spam")
        r = self.client.get("/manage/leads/")
        self.assertContains(r, "open one")
        self.assertNotContains(r, "closed one")
        self.assertNotContains(r, "spam one")
        self.assertEqual(r.context["counts"]["open"], 1)
        # new lead default status
        self.assertEqual(open_lead.status, "new")

    def test_all_filter_still_excludes_spam(self):
        self._lead(message="closed one", status="closed")
        self._lead(message="spam one", status="spam")
        r = self.client.get("/manage/leads/?status=all")
        self.assertContains(r, "closed one")
        self.assertNotContains(r, "spam one")

    def test_search_matches_message_and_phone(self):
        self._lead(message="wholesale pricing please", phone="+12045551234")
        self._lead(message="unrelated")
        r = self.client.get("/manage/leads/?status=all&q=wholesale")
        self.assertEqual(len(r.context["leads"]), 1)
        r = self.client.get("/manage/leads/?status=all&q=2045551234")
        self.assertEqual(len(r.context["leads"]), 1)

    def test_existing_customer_is_flagged(self):
        self._lead(email="buyer@example.com")
        Order.objects.create(site=self.site, email="buyer@example.com",
                             name="Buyer", total=100)
        r = self.client.get("/manage/leads/")
        lead = r.context["leads"][0]
        self.assertIsNotNone(lead.customer)
        self.assertEqual(lead.customer["n"], 1)

    # --- actions ---

    def test_set_status_stamps_reviewer(self):
        lead = self._lead()
        self.client.post("/manage/leads/", {
            "lead_id": lead.pk, "action": "set_status", "status": "reviewed"})
        lead.refresh_from_db()
        self.assertEqual(lead.status, "reviewed")
        self.assertEqual(lead.reviewed_by, "boss")
        self.assertIsNotNone(lead.reviewed_at)

    def test_bogus_status_is_rejected(self):
        lead = self._lead()
        self.client.post("/manage/leads/", {
            "lead_id": lead.pk, "action": "set_status", "status": "exploded"})
        lead.refresh_from_db()
        self.assertEqual(lead.status, "new")

    def test_save_note(self):
        lead = self._lead()
        self.client.post("/manage/leads/", {
            "lead_id": lead.pk, "action": "save_note", "notes": "call back Tuesday"})
        lead.refresh_from_db()
        self.assertEqual(lead.notes, "call back Tuesday")

    @override_settings(EMAIL_BACKEND="apps.mailer.backend.MailgunAPIBackend",
                       MAIL_LIVE=False)
    def test_reply_sends_email_and_marks_replied(self):
        lead = self._lead()
        n_before = EmailLog.objects.count()
        self.client.post("/manage/leads/", {
            "lead_id": lead.pk, "action": "reply",
            "subject": "Re: shipping", "body": "Yes — 10-15 days to Manitoba."})
        lead.refresh_from_db()
        self.assertEqual(lead.status, "replied")
        self.assertEqual(EmailLog.objects.count(), n_before + 1)
        log = EmailLog.objects.latest("pk")
        self.assertEqual(log.to_email, "pat@example.com")

    def test_reply_without_email_errors_cleanly(self):
        lead = self._lead(email="")
        n_before = EmailLog.objects.count()
        r = self.client.post("/manage/leads/", {
            "lead_id": lead.pk, "action": "reply", "body": "hi"}, follow=True)
        lead.refresh_from_db()
        self.assertEqual(lead.status, "new")
        self.assertEqual(EmailLog.objects.count(), n_before)
        self.assertContains(r, "no email")

    # --- capture ---

    def test_contact_form_stores_phone_on_lead(self):
        r = self.client.post(
            "/contact/",
            data={"name": "Sam", "email": "sam@example.com",
                  "message": "hi", "phone": "204-555-9999"},
            content_type="application/json", HTTP_HOST="smashfat.ca",
        )
        self.assertEqual(r.status_code, 200)
        lead = Lead.objects.latest("pk")
        self.assertEqual(lead.phone, "204-555-9999")
        self.assertEqual(lead.status, "new")
