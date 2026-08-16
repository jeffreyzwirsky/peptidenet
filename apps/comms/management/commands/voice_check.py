"""Report what a caller will ACTUALLY hear — the layer a code diff cannot show.

The spoken greeting exists in three places at once, and they can disagree:

  * the hardcoded AI-intake greeting in ``apps/comms/voice.py``  (code)
  * ``PhoneNumber.greeting``                                     (a database row)
  * ``PhoneNumber.greeting_audio``                          (a rendered mp3 file)

Precedence runs backwards from that list: when ``greeting_audio`` is set it is
played with ``<Play>`` and BOTH the database text and the code are irrelevant.
So "I fixed the pronunciation in voice.py" can be entirely true and change
nothing a caller hears. This command measures the layer the question is actually
about, and says which one wins.

    python manage.py voice_check
    python manage.py voice_check --number +13252465227

Exit status is 1 if anything would still be mispronounced, so it can be wired
into update.sh's post-deploy verification block.
"""
from django.core.management.base import BaseCommand

from apps.comms import voice
from apps.comms.models import PhoneNumber


class Command(BaseCommand):
    help = "Show what callers actually hear (DB greeting vs pre-generated mp3) and flag mispronunciations."

    def add_arguments(self, parser):
        parser.add_argument("--number", default="", help="Limit to one E.164 number.")

    def handle(self, *args, **opts):
        qs = PhoneNumber.objects.filter(is_active=True, voice_enabled=True)
        if opts["number"]:
            qs = qs.filter(e164=opts["number"])
        numbers = list(qs)
        if not numbers:
            # A zero here is a claim about the query, not about the world, and
            # "I checked nothing" must never read as green in a deploy log.
            self.stdout.write(self.style.ERROR(
                "No active voice-enabled PhoneNumber matched. Nothing was checked "
                "— this is NOT a clean result."))
            raise SystemExit(1)

        problems = 0
        for n in numbers:
            self.stdout.write(f"\n{n.e164}  ({n.label or 'no label'})  "
                              f"ai_intake={n.ai_intake}")

            # --- what actually plays -------------------------------------
            if n.greeting_audio:
                self.stdout.write(self.style.WARNING(
                    f"  PLAYS: pre-generated audio  {n.greeting_audio}"))
                self.stdout.write(
                    "         The DB text and the code greeting are BYPASSED. If this "
                    "mp3 was\n"
                    "         rendered before the pronunciation fix it still says the "
                    "old thing.\n"
                    "         Regenerate:  manage.py generate_greeting_audio --number "
                    f"{n.e164}")
                problems += 1
            else:
                self.stdout.write("  PLAYS: Twilio <Say> (Polly) — normalisation applies")

            # --- the DB text, before and after normalisation --------------
            raw = n.greeting or ""
            said = voice.spoken_text(raw)
            self.stdout.write(f"  DB greeting ({len(raw)} chars): {raw[:160]}")
            if said != raw:
                self.stdout.write(self.style.SUCCESS(
                    f"  normalised to:  {said[:160]}"))

            # --- anything left that a TTS engine will read as a number ----
            for label, text in (("DB greeting", said),
                                ("code intake greeting",
                                 voice.spoken_text(voice.INTAKE_GREETING))):
                if "325" in text:
                    self.stdout.write(self.style.ERROR(
                        f"  STILL SAYS 325 in the {label} — Polly will read this as "
                        '"three hundred twenty five".'))
                    problems += 1

        self.stdout.write("")
        if problems:
            self.stdout.write(self.style.ERROR(
                f"voice_check: {problems} issue(s) — callers do not hear the fix yet."))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS(
            f"voice_check: {len(numbers)} number(s) OK — nothing spoken contains a "
            "raw 325."))
