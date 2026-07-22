from django.core.management import call_command
from django.test import TestCase

from apps.stores.models import Site

from . import phone, sms
from .models import Contact, Message, OptOut, PhoneNumber, Voicemail


class PhoneNormalizeTests(TestCase):
    def test_normalize(self):
        self.assertEqual(phone.normalize("(587) 555-1234"), "+15875551234")
        self.assertEqual(phone.normalize("5875551234"), "+15875551234")
        self.assertEqual(phone.normalize("+1 587 555 1234"), "+15875551234")
        self.assertEqual(phone.normalize(""), "")

    def test_region(self):
        self.assertEqual(phone.region_of("+15875551234"), "AB")
        self.assertEqual(phone.region_of("+16395551234"), "SK")

    def test_display(self):
        self.assertEqual(phone.display("+15875551234"), "(587) 555-1234")


class SmsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_sites")
        cls.site = Site.objects.get(domain="smashfat.ca")
        cls.number = PhoneNumber.objects.create(
            e164="+15875550000", label="SmashFat line", site=cls.site
        )

    def test_send_transactional_stub(self):
        m = sms.send_sms("587-555-1111", "Your order shipped.", site=self.site)
        self.assertEqual(m.status, "sent")          # stub send succeeds
        self.assertEqual(m.twilio_sid, "STUB-SMS")
        self.assertEqual(m.to_number, "+15875551111")

    def test_marketing_blocked_after_stop(self):
        num = "+15875552222"
        # inbound STOP opts out
        _msg, reply = sms.handle_inbound(num, self.number.e164, "STOP", site=self.site)
        self.assertIn("unsubscribed", reply.lower())
        self.assertTrue(sms.is_opted_out(num))
        # marketing is blocked...
        mk = sms.send_sms(num, "10% off peptides!", category="marketing", site=self.site)
        self.assertEqual(mk.status, "blocked")
        # ...but transactional still flows
        tx = sms.send_sms(num, "Your COA is ready.", category="transactional", site=self.site)
        self.assertEqual(tx.status, "sent")

    def test_start_reopts_in(self):
        num = "+15875553333"
        sms.handle_inbound(num, self.number.e164, "STOP", site=self.site)
        sms.handle_inbound(num, self.number.e164, "START", site=self.site)
        self.assertFalse(sms.is_opted_out(num))

    def test_inbound_logs_and_links_contact(self):
        sms.handle_inbound("587-555-4444", self.number.e164, "hi do you ship to AB?", site=self.site)
        self.assertTrue(Message.objects.filter(direction="in").exists())
        self.assertTrue(Contact.objects.filter(e164="+15875554444").exists())

    def test_region_aware_from_number(self):
        PhoneNumber.objects.create(e164="+16395550000", label="SK", region="SK", site=self.site)
        chosen = sms.pick_from_number("+16395559999", self.site)
        self.assertEqual(chosen.region, "SK")


class WebhookTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_sites")
        cls.site = Site.objects.get(domain="smashfat.ca")
        cls.number = PhoneNumber.objects.create(
            e164="+15875550000", label="line", site=cls.site, ivr_enabled=False
        )

    def test_inbound_sms_webhook(self):
        r = self.client.post("/webhooks/twilio/sms/", {
            "From": "+15875551234", "To": "+15875550000", "Body": "hello",
        })
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Response", r.content)
        self.assertTrue(Message.objects.filter(from_number="+15875551234").exists())

    def test_voice_webhook_returns_voicemail_twiml(self):
        r = self.client.post("/webhooks/twilio/voice/?number=+15875550000", {
            "From": "+15875551234", "To": "+15875550000", "CallSid": "CA1",
        })
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"<Record", r.content)

    def test_recording_creates_voicemail(self):
        self.client.post("/webhooks/twilio/recording/?number=+15875550000&category=sales", {
            "From": "+15875551234", "RecordingUrl": "https://x/r.mp3", "RecordingDuration": "12",
        })
        vm = Voicemail.objects.first()
        self.assertIsNotNone(vm)
        self.assertEqual(vm.category, "sales")

    def test_unknown_number_rejects_call(self):
        r = self.client.post("/webhooks/twilio/voice/?number=+19999999999", {"From": "+1587", "CallSid": "CA2"})
        self.assertIn(b"<Reject", r.content)


class ComplianceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_sites")
        cls.site = Site.objects.get(domain="smashfat.ca")
        cls.number = PhoneNumber.objects.create(e164="+15875550000", label="line", site=cls.site)

    def test_stop_logs_consent_and_keyword(self):
        from .models import ComplianceConfig, SmsConsent, SmsKeywordEvent
        _m, reply = sms.handle_inbound("+15875557777", self.number.e164, "STOP", site=self.site)
        self.assertEqual(reply, ComplianceConfig.get_solo().stop_reply)
        self.assertTrue(SmsConsent.objects.filter(e164="+15875557777", event_type="opt_out").exists())
        self.assertTrue(SmsKeywordEvent.objects.filter(e164="+15875557777", keyword="STOP").exists())

    def test_start_logs_resubscribe(self):
        from .models import SmsConsent
        sms.handle_inbound("+15875558888", self.number.e164, "STOP", site=self.site)
        sms.handle_inbound("+15875558888", self.number.e164, "START", site=self.site)
        self.assertTrue(SmsConsent.objects.filter(e164="+15875558888", event_type="resubscribe").exists())

    def test_consent_is_immutable(self):
        from .models import SmsConsent
        c = SmsConsent.objects.create(e164="+15875559999", event_type="opt_in")
        c.note = "changed"
        with self.assertRaises(ValueError):
            c.save()

    def test_voicemail_triage_runs_via_webhook(self):
        self.client.post("/webhooks/twilio/recording/?number=+15875550000&category=sales", {
            "From": "+15875551234", "RecordingUrl": "https://x/r.mp3", "RecordingDuration": "9",
        })
        vm = Voicemail.objects.first()
        self.assertIn(vm.urgency, ["low", "normal", "high", "urgent"])

    def test_triage_heuristic_flags_urgent(self):
        from . import triage
        vm = Voicemail.objects.create(
            from_number="+15875550001", site=self.site,
            transcript="This is urgent, my order never arrived and I need it ASAP",
        )
        triage.classify_voicemail(vm)
        self.assertEqual(vm.urgency, "urgent")

    def test_contact_form_logs_sms_consent(self):
        from .models import SmsConsent
        self.client.post("/contact/", {
            "name": "L", "email": "l@x.ca", "message": "hi",
            "phone": "587-555-6543", "sms_optin_marketing": "1",
        }, content_type="application/json", HTTP_HOST="smashfat.ca")
        self.assertTrue(SmsConsent.objects.filter(
            e164="+15875556543", event_type="opt_in", category="marketing",
            source="contact_form").exists())


class VoiceGreetingTests(TestCase):
    """Greeting uses the natural Polly Neural voice by default, and plays a
    pre-generated ElevenLabs mp3 via <Play> when greeting_audio is set."""

    def _req(self):
        from django.test import RequestFactory
        return RequestFactory().post("/webhooks/twilio/voice/",
                                     HTTP_HOST="smashfatbiolabs.ca")

    def test_default_greeting_uses_neural_say(self):
        from apps.comms import voice
        from apps.comms.models import PhoneNumber
        n = PhoneNumber.objects.create(e164="+13252465227", greeting="Hello there.")
        xml = voice.voicemail_twiml(n, self._req())
        self.assertIn("Polly.Ruth-Neural", xml)   # natural neural voice
        self.assertIn("<Record", xml)

    def test_elevenlabs_audio_played_when_set(self):
        from apps.comms import voice
        from apps.comms.models import PhoneNumber
        n = PhoneNumber.objects.create(
            e164="+13252465999", greeting="Hi",
            greeting_audio="/static/comms/greeting-9.mp3")
        xml = voice.voicemail_twiml(n, self._req())
        self.assertIn("<Play>", xml)
        self.assertIn("greeting-9.mp3", xml)
