from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.blog import guardrails
from apps.stores.models import Site

from . import phone, sms
from .models import Call, Contact, Message, OptOut, PhoneNumber, Voicemail


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


@override_settings(TWILIO_AUTH_TOKEN="", DEBUG=True, COMMS_WEBHOOK_INSECURE=True)
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


@override_settings(TWILIO_AUTH_TOKEN="", DEBUG=True, COMMS_WEBHOOK_INSECURE=True)
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


@override_settings(TWILIO_AUTH_TOKEN="", DEBUG=True, COMMS_WEBHOOK_INSECURE=True)
class VoiceAgentTests(TestCase):
    """Guarded AI phone intake: deflects dosing/medical + company/address/staff,
    answers catalogue questions with the research-use-only disclaimer, and builds
    a voicemail subject line. The webhook always ends by recording the message."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog")
        call_command("seed_sites")

    def test_deflects_dosing_and_medical(self):
        from apps.comms import agent
        self.assertEqual(agent.answer("how much should I inject", None), agent.MEDICAL_DEFLECT)
        self.assertEqual(agent.answer("what is the dosage", None), agent.MEDICAL_DEFLECT)
        self.assertEqual(agent.answer("does this treat inflammation", None), agent.MEDICAL_DEFLECT)

    def test_deflects_company_info(self):
        from apps.comms import agent
        self.assertEqual(agent.answer("what is your address", None), agent.INFO_DEFLECT)
        self.assertEqual(agent.answer("who is the owner", None), agent.INFO_DEFLECT)
        self.assertEqual(agent.answer("can I speak to a real person", None), agent.INFO_DEFLECT)

    def test_price_question_is_not_medical(self):
        from apps.comms import agent
        self.assertNotEqual(agent.classify("how much is bpc-157"), "medical")

    def test_answers_product_with_research_disclaimer(self):
        from apps.comms import agent
        site = Site.objects.get(domain="smashfatbiolabs.ca")
        with self.settings(AI_LIVE=False):
            r = agent.answer("is BPC-157 in stock", site)
        self.assertIn("research", r.lower())

    def test_subject_line_short(self):
        from apps.comms import agent
        with self.settings(AI_LIVE=False):
            s = agent.subject_line("I want to ask about bulk pricing on retatrutide", None)
        self.assertTrue(0 < len(s) <= 80)

    def test_voice_webhook_starts_ai_intake(self):
        from apps.comms.models import PhoneNumber
        PhoneNumber.objects.create(e164="+13252465227", ai_intake=True,
                                   site=Site.objects.get(domain="smashfatbiolabs.ca"))
        r = self.client.post("/webhooks/twilio/voice/",
                             {"To": "+13252465227", "From": "+15875551212", "CallSid": "CA1"},
                             HTTP_HOST="smashfatbiolabs.ca")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'input="speech dtmf"', r.content)   # gather intake (speech + press-0)

    def test_gather_webhook_answers_then_records(self):
        from apps.comms.models import PhoneNumber
        PhoneNumber.objects.create(e164="+13252465227", ai_intake=True,
                                   site=Site.objects.get(domain="smashfatbiolabs.ca"))
        with self.settings(AI_LIVE=False):
            r = self.client.post("/webhooks/twilio/gather/?number=%2B13252465227",
                                 {"SpeechResult": "do you have BPC-157 in stock",
                                  "From": "+15875551212"},
                                 HTTP_HOST="smashfatbiolabs.ca")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"<Record", r.content)          # always records the message

    def test_press_zero_skips_agent(self):
        from apps.comms.models import PhoneNumber
        PhoneNumber.objects.create(e164="+13252465227", ai_intake=True,
                                   site=Site.objects.get(domain="smashfatbiolabs.ca"))
        r = self.client.post("/webhooks/twilio/gather/?number=%2B13252465227",
                             {"Digits": "0", "From": "+15875551212"},
                             HTTP_HOST="smashfatbiolabs.ca")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"<Record", r.content)                       # straight to voicemail
        self.assertNotIn(b"qualified professional", r.content)     # agent was skipped


@override_settings(TWILIO_AUTH_TOKEN="", DEBUG=True, COMMS_WEBHOOK_INSECURE=True)
class VoicemailCaptureTests(TestCase):
    """The recording callback must survive Twilio's actual payload, which
    carries Recording* + CallSid and NOT From/To."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog"); call_command("seed_sites")
        from apps.stores.models import Site
        cls.num = PhoneNumber.objects.create(
            e164="+13252465227", label="test", site=Site.objects.first(),
            voice_enabled=True, sms_enabled=True, ai_intake=True,
            greeting="Leave a message.")

    def test_record_tag_pins_caller_and_sets_action(self):
        from apps.comms import voice as voicelib
        rf = self.client.post("/webhooks/twilio/voice/", {
            "To": self.num.e164, "From": "+12045551234", "CallSid": "CA1",
            "CallStatus": "ringing"})
        xml = rf.content.decode()
        self.assertIn("<Gather", xml)               # AI intake answers
        # ...and the fallback Record carries the caller + an action to hang up on
        self.assertIn("from=%2B12045551234", xml)
        self.assertIn("recording-done", xml)

    def test_recording_callback_without_From_still_captures_caller(self):
        """The exact bug: all 5 production voicemails had a blank caller."""
        Call.objects.create(direction="in", twilio_sid="CA9",
                            from_number="+12045559999", to_number=self.num.e164)
        r = self.client.post(
            f"/webhooks/twilio/recording/?number={self.num.e164}&from=%2B12045559999&call_sid=CA9",
            {"RecordingUrl": "https://api.twilio.com/rec1", "RecordingDuration": "12",
             "CallSid": "CA9"})
        self.assertEqual(r.status_code, 200)
        vm = Voicemail.objects.latest("pk")
        self.assertEqual(vm.from_number, "+12045559999")
        self.assertIsNotNone(vm.contact)

    def test_recording_callback_falls_back_to_the_call_row(self):
        Call.objects.create(direction="in", twilio_sid="CA7",
                            from_number="+12045558888", to_number=self.num.e164)
        self.client.post(
            f"/webhooks/twilio/recording/?number={self.num.e164}&call_sid=CA7",
            {"RecordingUrl": "https://api.twilio.com/rec2", "RecordingDuration": "5",
             "CallSid": "CA7"})
        self.assertEqual(Voicemail.objects.latest("pk").from_number, "+12045558888")

    def test_recording_done_hangs_up_instead_of_looping(self):
        r = self.client.post(f"/webhooks/twilio/recording-done/?number={self.num.e164}", {})
        xml = r.content.decode()
        self.assertIn("<Hangup/>", xml)
        self.assertNotIn("<Gather", xml)


class OutboundCallingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog"); call_command("seed_sites")
        from apps.stores.models import Site
        cls.num = PhoneNumber.objects.create(
            e164="+13252465227", label="biz", site=Site.objects.first(),
            voice_enabled=True, sms_enabled=True)

    def test_bridge_requires_an_operator_number(self):
        from apps.comms import calling
        with self.assertRaises(ValueError):
            calling.place_bridge_call("+12045551234")

    def test_bridge_logs_an_outbound_call(self):
        from apps.comms import calling
        from apps.comms.models import ComplianceConfig
        cfg = ComplianceConfig.get_solo()
        cfg.operator_callback_e164 = "+12045550000"; cfg.save()
        call = calling.place_bridge_call("204-555-1234")
        self.assertEqual(call.direction, "out")
        self.assertEqual(call.to_number, "+12045551234")
        self.assertEqual(call.from_number, self.num.e164)
        self.assertNotEqual(call.status, "failed")

    def test_bridge_twiml_dials_customer_with_business_caller_id(self):
        from apps.comms import voice as voicelib
        xml = voicelib.bridge_twiml("+12045551234", "+13252465227")
        self.assertIn('callerId="+13252465227"', xml)
        self.assertIn("<Dial", xml)
        self.assertIn("+12045551234", xml)


@override_settings(TWILIO_AUTH_TOKEN="", DEBUG=True, COMMS_WEBHOOK_INSECURE=True)
class MultiTurnConversationTests(TestCase):
    """The call is a conversation, not one question and a beep.

    Jeff, after the first working acceptance call (2026-08-16): "it only lets
    you ask one question and then goes and explains it and then goes straight to
    voicemail." These tests pin the loop, its ceiling, its escapes, and the
    guardrail scan that has to run on every turn of it — the last being the one
    that matters, because a multi-turn agent validated only on turn 1 is the
    blog's stale-verdict bug wearing a different hat.
    """

    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog"); call_command("seed_sites")
        cls.site = Site.objects.get(domain="smashfatbiolabs.ca")
        cls.num = PhoneNumber.objects.create(
            e164="+13252465227", label="test", site=cls.site,
            voice_enabled=True, ai_intake=True, greeting="Leave a message.")

    def _ask(self, text, turn=None, sid="CA-MT", **extra):
        url = "/webhooks/twilio/gather/?number=%2B13252465227"
        if turn is not None:
            url += f"&turn={turn}"
        data = {"From": "+15875551212", "CallSid": sid}
        if text is not None:
            data["SpeechResult"] = text
        data.update(extra)
        with self.settings(AI_LIVE=False):
            return self.client.post(url, data, HTTP_HOST="smashfatbiolabs.ca")

    def test_answer_is_followed_by_another_gather(self):
        """The whole point: after answering, ask for the next question."""
        xml = self._ask("do you have BPC-157 in stock").content.decode()
        self.assertIn("<Gather", xml)
        self.assertIn("turn=2", xml)
        self.assertIn("<Record", xml)   # still falls through if they go quiet

    def test_follow_up_gather_keeps_the_recogniser_settings(self):
        """A later turn that quietly reverted to Twilio's defaults would bring
        back 'the AI isn't hearing me' from turn 2 on, with turn 1 still fine
        and hiding it."""
        xml = self._ask("what about retatrutide", turn=2).content.decode()
        gathers = [g for g in xml.split("<Gather")[1:]]
        self.assertTrue(gathers)
        for g in gathers:
            self.assertIn('speechTimeout="3"', g)
            self.assertNotIn('speechTimeout="auto"', g)
            self.assertIn('speechModel="googlev2_telephony"', g)
            self.assertIn('numDigits="1"', g)   # the press-zero escape survives

    def test_turn_ceiling_stops_the_loop(self):
        xml = self._ask("and how about shipping", turn=99).content.decode()
        self.assertNotIn("<Gather", xml)
        self.assertIn("<Record", xml)
        self.assertIn("<Hangup", xml)

    def test_press_zero_mid_conversation_does_not_replay_the_greeting(self):
        """Assert against the DATABASE greeting, which is what voicemail_twiml
        would replay — an earlier version of this test looked for the hardcoded
        code greeting instead and a mutation that reintroduced the replay walked
        straight past it."""
        xml = self._ask(None, turn=3, Digits="0").content.decode()
        self.assertIn("<Record", xml)
        self.assertNotIn(self.num.greeting, xml)
        self.assertNotIn("<Gather", xml)

    def test_silence_mid_conversation_does_not_replay_the_greeting_either(self):
        xml = self._ask(None, turn=2).content.decode()
        self.assertIn("<Record", xml)
        self.assertNotIn(self.num.greeting, xml)

    def test_silence_on_turn_one_still_takes_a_message(self):
        xml = self._ask(None, turn=1).content.decode()
        self.assertIn("<Record", xml)

    def test_every_turn_is_scanned_before_it_is_spoken(self):
        """Not 'the answer was scanned when generated' — scanned at speak time,
        which is the only moment that is true for text of any age."""
        from apps.comms import voice as voicelib

        class _Req:
            META = {"HTTP_HOST": "smashfatbiolabs.ca"}
            POST = {}
            def build_absolute_uri(self, loc):
                return "https://smashfatbiolabs.ca" + loc

        banned = "Every vial is 99% purity with a Certificate of Analysis."
        self.assertTrue(guardrails.scan(banned)[0], "test premise: this must trip")
        xml = voicelib.agent_reply_twiml(self.num, _Req(), banned, turn=1)
        self.assertNotIn("Certificate of Analysis", xml)
        self.assertIn("qualified professional", xml)   # the safe fallback

    def test_fixed_phrases_are_speakable(self):
        """speakable() returns SAFE_FALLBACK for anything that trips the scan.
        If the fixed strings tripped it, the agent would answer every question
        with the fallback — and if SAFE_FALLBACK itself tripped, there would be
        nothing clean left to say."""
        from apps.comms import agent
        from apps.comms import voice as voicelib
        for text in (agent.SAFE_FALLBACK, agent.MEDICAL_DEFLECT,
                     agent.INFO_DEFLECT, agent.DISCLAIMER,
                     voicelib.INTAKE_GREETING):
            self.assertEqual(guardrails.scan(text)[0], [], f"trips the scan: {text[:60]}")
            self.assertEqual(agent.speakable(text), " ".join(text.split()))

    def test_conversation_is_written_to_the_call(self):
        """The corpus Phase 2 is supposed to learn from. Before this, the only
        transcript a call could produce was of the voicemail left after the
        agent stopped talking."""
        call = Call.objects.create(direction="in", twilio_sid="CA-LOG",
                                   from_number="+15875551212", to_number=self.num.e164)
        self._ask("do you have BPC-157", sid="CA-LOG")
        self._ask("and what does it cost", sid="CA-LOG", turn=2)
        call.refresh_from_db()
        self.assertIn("Caller: do you have BPC-157", call.transcript)
        self.assertIn("Caller: and what does it cost", call.transcript)
        self.assertEqual(call.transcript.count("Agent: "), 2)

    def test_later_turns_see_the_earlier_ones(self):
        from apps.comms import agent
        seen = {}
        real = agent.llm.complete

        def spy(system, user, **kw):
            seen["user"] = user
            return real(system, user, **kw)

        agent.llm.complete = spy
        try:
            with self.settings(AI_LIVE=False):
                agent.answer("how much is that one", self.site,
                             history="Caller: do you have BPC-157\nAgent: Yes, $64 a vial.\n")
        finally:
            agent.llm.complete = real
        self.assertIn("BPC-157", seen["user"])
        self.assertIn("how much is that one", seen["user"])

    def test_the_webhook_actually_hands_the_history_to_the_agent(self):
        """Separate from the test above on purpose. That one proves answer()
        USES history; this one proves gather() PASSES it. A mutation that
        replaced the argument with "" survived the first test — memory would
        have been silently dead on every real call while the suite stayed green.
        """
        from apps.comms import agent
        call = Call.objects.create(direction="in", twilio_sid="CA-HIST",
                                   from_number="+15875551212", to_number=self.num.e164,
                                   transcript="Caller: do you have BPC-157\n"
                                              "Agent: Yes, $64 a vial.\n")
        seen = {}
        real = agent.answer

        def spy(speech, site, history=""):
            seen["history"] = history
            return real(speech, site, history=history)

        agent.answer = spy
        try:
            self._ask("how much is that one", sid="CA-HIST", turn=2)
        finally:
            agent.answer = real
        self.assertIn("BPC-157", seen.get("history", ""))

    def test_the_subject_line_is_computed_once_and_carried(self):
        """Recomputing it every turn would put a second LLM round-trip in the
        middle of a live call for no gain."""
        xml = self._ask("do you have BPC-157", turn=1).content.decode()
        self.assertIn("subject=", xml)
        from apps.comms import agent
        real = agent.subject_line
        agent.subject_line = _boom            # blows up if called again
        try:
            r = self.client.post(
                "/webhooks/twilio/gather/?number=%2B13252465227&turn=2&subject=Pricing+question",
                {"SpeechResult": "what about shipping", "From": "+15875551212"},
                HTTP_HOST="smashfatbiolabs.ca")
        finally:
            agent.subject_line = real
        self.assertEqual(r.status_code, 200)
        self.assertIn("Pricing+question", r.content.decode())


def _boom(*a, **kw):
    raise AssertionError("subject_line must not be recomputed on a later turn")


@override_settings(TWILIO_AUTH_TOKEN="", DEBUG=True, COMMS_WEBHOOK_INSECURE=True)
class SpokenTextTests(TestCase):
    """Polly reads '325 BioLabs' as 'three hundred twenty five BioLabs'."""

    def test_brand_digits_are_spelled_out(self):
        from apps.comms import voice as voicelib
        self.assertEqual(voicelib.spoken_text("Thanks for calling 325 BioLabs."),
                         "Thanks for calling three two five BioLabs.")
        self.assertEqual(voicelib.spoken_text("325 Biolabs"), "three two five Biolabs")
        self.assertEqual(voicelib.spoken_text("325-BioLabs"), "three two five-BioLabs")

    def test_other_numbers_are_left_alone(self):
        from apps.comms import voice as voicelib
        self.assertEqual(voicelib.spoken_text("That is $325 for 325 vials."),
                         "That is $325 for 325 vials.")

    def test_normalisation_reaches_the_database_greeting(self):
        """A code fix is not a data fix. The greeting that actually plays comes
        from a DB row, so the fix has to sit where BOTH paths pass through."""
        from apps.comms import voice as voicelib
        num = PhoneNumber.objects.create(
            e164="+13252465227", greeting="You have reached 325 BioLabs.",
            voice_enabled=True)

        class _Req:
            POST = {}
            def build_absolute_uri(self, loc):
                return "https://smashfatbiolabs.ca" + loc

        xml = voicelib.voicemail_twiml(num, _Req())
        self.assertIn("three two five BioLabs", xml)
        self.assertNotIn("325 BioLabs", xml)

    def test_pregenerated_audio_is_the_one_path_code_cannot_fix(self):
        """Documents the trap rather than pretending it is closed: when an mp3
        exists it is played and every text fix above is bypassed."""
        from apps.comms import voice as voicelib
        num = PhoneNumber.objects.create(
            e164="+13252465228", greeting="You have reached 325 BioLabs.",
            greeting_audio="/static/comms/greeting-1.mp3", voice_enabled=True)

        class _Req:
            POST = {}
            def build_absolute_uri(self, loc):
                return "https://smashfatbiolabs.ca" + loc

        xml = voicelib.voicemail_twiml(num, _Req())
        self.assertIn("<Play>", xml)
        self.assertNotIn("three two five", xml)   # the mp3 says whatever it says


@override_settings(TWILIO_AUTH_TOKEN="", DEBUG=True, COMMS_WEBHOOK_INSECURE=True)
class SpeechBrevityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog"); call_command("seed_sites")

    def test_reply_is_capped_at_two_sentences(self):
        from apps.comms import agent
        long = ("One. Two. Three. Four. Five.")
        self.assertEqual(agent.shorten_for_speech(long), "One. Two.")

    def test_a_single_runaway_sentence_is_cut_on_a_word_boundary(self):
        from apps.comms import agent
        out = agent.shorten_for_speech("word " * 200)
        self.assertLessEqual(len(out), agent.SPEECH_HARD_CEILING + 1)
        self.assertTrue(out.endswith("."))
        self.assertNotIn("  ", out)

    def test_short_answers_are_untouched(self):
        from apps.comms import agent
        s = "BPC-157 is $64 a vial. For research use only."
        self.assertEqual(agent.shorten_for_speech(s), s)

    def test_a_real_answer_stays_short_and_keeps_the_disclaimer(self):
        from apps.comms import agent
        site = Site.objects.get(domain="smashfatbiolabs.ca")
        with self.settings(AI_LIVE=False):
            r = agent.answer("how much is BPC-157", site)
        self.assertIn("research", r.lower())
        self.assertLessEqual(len(r), agent.SPEECH_HARD_CEILING + len(agent.DISCLAIMER) + 4)
        self.assertEqual(guardrails.scan(r)[0], [])


class GreetingAudioNormalisationTests(TestCase):
    """The renderer that turns the DB greeting into an mp3 must apply the same
    pronunciation normalisation as <Say>.

    It does not go through voice._say(), so it did not. Regenerating the mp3 to
    "fix" the 3-2-5 greeting would have produced a new file that still said
    "three hundred twenty five" — and looked fixed, because voice_check only
    knows whether an mp3 exists, not what is inside it."""

    def test_the_text_sent_to_tts_is_normalised(self):
        from apps.comms.management.commands import generate_greeting_audio as cmd
        from apps.comms import providers
        from apps.stores.models import Site
        call_command("seed_sites")
        PhoneNumber.objects.create(
            e164="+13252465227", voice_enabled=True, is_active=True,
            site=Site.objects.first(),
            greeting="Thanks for calling 325 BioLabs. Leave a message.")
        seen = {}
        real = providers.tts_greeting_audio
        providers.tts_greeting_audio = lambda t: seen.setdefault("text", t) and None
        try:
            call_command("generate_greeting_audio", "--number", "+13252465227",
                         stdout=StringIO())
        finally:
            providers.tts_greeting_audio = real
        self.assertIn("three two five BioLabs", seen.get("text", ""))
        self.assertNotIn("325 BioLabs", seen.get("text", ""))
