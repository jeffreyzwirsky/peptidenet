"""Create ONE clearly-labelled TEST voicemail so the portal voicemail inbox,
AI triage, and alert path can be verified end-to-end WITHOUT placing a real
Twilio call. Also ensures the network PhoneNumber row exists (the inbound-voice
webhook <Reject/>s calls to unknown numbers).

Safe + idempotent: re-running updates the same single test row (sentinel caller
number) instead of piling up. Remove it later with --remove.

    python manage.py create_test_voicemail
    python manage.py create_test_voicemail --number +13252465227 --site smashfatbiolabs.ca --alert
    python manage.py create_test_voicemail --remove
"""
from django.core.management.base import BaseCommand

from apps.comms import sms
from apps.comms.models import PhoneNumber, Voicemail
from apps.stores.models import Site

SENTINEL_FROM = "+15550100001"  # obvious test caller (555-01xx = fictional)
TEST_TRANSCRIPT = (
    "Hi, this is a TEST voicemail. I'm calling about my order SFB-10042 — it "
    "hasn't shipped yet and I need it this week. Can someone call me back? Thanks."
)


class Command(BaseCommand):
    help = "Create/refresh a single TEST voicemail to verify the portal inbox + triage."

    def add_arguments(self, parser):
        parser.add_argument("--number", default="+13252465227",
                            help="E.164 of the network line to attach the voicemail to.")
        parser.add_argument("--site", default="smashfatbiolabs.ca",
                            help="Site domain the voicemail belongs to.")
        parser.add_argument("--alert", action="store_true",
                            help="Also fire the (stubbed until MAIL_LIVE) email alert.")
        parser.add_argument("--remove", action="store_true",
                            help="Delete the test voicemail instead of creating it.")

    def handle(self, *args, **opts):
        site = Site.objects.filter(domain=opts["site"]).first()

        if opts["remove"]:
            n, _ = Voicemail.objects.filter(from_number=SENTINEL_FROM).delete()
            self.stdout.write(self.style.SUCCESS(f"Removed {n} test voicemail row(s)."))
            return

        # Ensure the real network line exists so live inbound calls aren't rejected.
        number, created = PhoneNumber.objects.get_or_create(
            e164=opts["number"],
            defaults={"label": "SmashFat network line (1-325-BIOLABS)",
                      "site": site, "region": "AB", "voice_enabled": True},
        )
        if created:
            self.stdout.write(f"Created PhoneNumber {number.e164} ({number.label}).")

        contact = sms.resolve_contact(SENTINEL_FROM, site=site)
        contact.name = "TEST — Voicemail Check"
        contact.save()

        vm, _ = Voicemail.objects.update_or_create(
            from_number=SENTINEL_FROM,
            defaults={
                "site": site, "contact": contact, "category": "support",
                "duration_sec": 22, "listened": False,
                "transcript": TEST_TRANSCRIPT,
                "transcript_source": "test",
                "recording_url": "https://example.com/test-voicemail.mp3",
            },
        )

        # Run AI triage (falls back to the keyword heuristic when AI is offline).
        try:
            from apps.comms import triage
            triage.classify_voicemail(vm)
        except Exception as e:  # pragma: no cover
            self.stderr.write(f"triage skipped: {e}")

        if opts["alert"]:
            try:
                from apps.mailer import mailer
                mailer.voicemail_alert(vm)
                self.stdout.write("Fired voicemail_alert (EmailLog written; stub until MAIL_LIVE=1).")
            except Exception as e:  # pragma: no cover
                self.stderr.write(f"alert skipped: {e}")

        vm.refresh_from_db()
        self.stdout.write(self.style.SUCCESS(
            "TEST voicemail ready -> open the portal 'Calls & Voicemail' page:\n"
            "  /portal/calls/  or  /manage/calls/\n"
            f"  tier={vm.tier!r} urgency={vm.urgency!r} confidence={vm.tier_confidence} "
            f"source={vm.transcript_source!r}\n"
            "Remove it later with:  python manage.py create_test_voicemail --remove"
        ))
