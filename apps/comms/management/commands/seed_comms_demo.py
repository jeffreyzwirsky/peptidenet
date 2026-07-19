"""Demo comms data (numbers, threads, a voicemail) so the panel has content.
Dev only. `python manage.py seed_comms_demo`"""
from django.core.management.base import BaseCommand

from apps.comms import sms
from apps.comms.models import Call, IvrOption, PhoneNumber, Voicemail
from apps.stores.models import Site

NUMBERS = [
    ("+15873060001", "SmashFat BioLabs — AB line", "smashfatbiolabs.ca", "AB"),
    ("+16396380002", "Peptides Alberta — SK line", "peptidesalberta.ca", "SK"),
    ("+14313060003", "Network support — MB", None, "MB"),
]
THREADS = [
    ("+15875551212", "Dr. Priya Sandhu", "smashfat.ca", [
        ("in", "Hi, do you ship BPC-157 to Alberta?"),
        ("out", "We do — free express on orders over $200, usually 1–2 days to AB."),
        ("in", "Great, is there a COA for the current batch?"),
    ]),
    ("+16045553434", "Ty Nguyen", "smashfatbiolabs.ca", [
        ("in", "Order SFB-44967 — when does it ship?"),
        ("out", "It shipped this morning, tracking is on its way to your email."),
    ]),
    ("+14035559090", "STOP tester", "peptidesalberta.ca", [
        ("in", "STOP"),
    ]),
]


class Command(BaseCommand):
    help = "Seed demo phone numbers, SMS threads, a call and a voicemail."

    def handle(self, *args, **opts):
        for e164, label, dom, region in NUMBERS:
            site = Site.objects.filter(domain=dom).first() if dom else None
            n, _ = PhoneNumber.objects.get_or_create(
                e164=e164, defaults={"label": label, "site": site, "region": region}
            )
        # a simple IVR on the support line
        support = PhoneNumber.objects.filter(region="MB").first()
        if support:
            support.ivr_enabled = True
            support.greeting = "Thanks for calling. For orders press 1, for research support press 2."
            support.save()
            IvrOption.objects.get_or_create(number=support, digit="1",
                                            defaults={"label": "orders", "voicemail_category": "sales"})
            IvrOption.objects.get_or_create(number=support, digit="2",
                                            defaults={"label": "support", "voicemail_category": "support"})

        for frm, name, dom, msgs in THREADS:
            site = Site.objects.filter(domain=dom).first()
            for direction, body in msgs:
                if direction == "in":
                    sms.handle_inbound(frm, NUMBERS[0][0], body, site=site)
                else:
                    sms.send_sms(frm, body, site=site)
            c = sms.resolve_contact(frm, site=site)
            c.name = name
            c.save()

        # a call + voicemail
        site = Site.objects.filter(domain="smashfatbiolabs.ca").first()
        contact = sms.resolve_contact("+15875557777", site=site)
        contact.name = "Sandy Beaumont"; contact.save()
        call = Call.objects.create(direction="in", site=site, contact=contact,
                                   from_number="+15875557777", to_number=NUMBERS[0][0],
                                   duration_sec=18, status="completed")
        Voicemail.objects.get_or_create(
            call=call, site=site, contact=contact, from_number="+15875557777",
            category="sales", duration_sec=18, listened=False,
            transcript="Hi, this is Sandy — I wanted to ask about bulk pricing on "
                       "Retatrutide for a research group. Please call me back. Thanks.",
            recording_url="https://example.com/demo-recording.mp3",
        )
        self.stdout.write(self.style.SUCCESS(
            f"Comms demo: {PhoneNumber.objects.count()} numbers, threads + 1 voicemail seeded."
        ))
