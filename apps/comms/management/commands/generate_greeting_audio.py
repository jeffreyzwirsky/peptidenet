"""Generate a natural ElevenLabs greeting mp3 for each phone number and wire it
into the voicemail TwiML (<Play> instead of the Polly <Say>). Requires
ELEVENLABS_API_KEY (+ the `requests` package) on the box; no-ops gracefully and
tells you why when offline. Files write to the source static dir + STATIC_ROOT,
so they serve immediately (no collectstatic needed).

  python manage.py generate_greeting_audio
  python manage.py generate_greeting_audio --number +13252465227
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.comms import providers
from apps.comms import voice
from apps.comms.management.commands.voice_check import audio_token
from apps.comms.models import PhoneNumber


def _save_static(data: bytes, rel: str) -> str:
    targets = []
    dirs = list(getattr(settings, "STATICFILES_DIRS", []) or [])
    if dirs:
        targets.append(Path(dirs[0]) / rel)
    if getattr(settings, "STATIC_ROOT", None):
        targets.append(Path(settings.STATIC_ROOT) / rel)
    for p in targets:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return f"{settings.STATIC_URL.rstrip('/')}/{rel}"


class Command(BaseCommand):
    help = "Generate ElevenLabs greeting audio for phone numbers (falls back to Polly when offline)."

    def add_arguments(self, parser):
        parser.add_argument("--number", default="", help="Limit to one E.164 number.")

    def handle(self, *args, **opts):
        qs = PhoneNumber.objects.filter(is_active=True, voice_enabled=True)
        if opts["number"]:
            qs = qs.filter(e164=opts["number"])
        done = offline = 0
        for n in qs:
            # RAW DB text, deliberately NOT voice.spoken_text().
            #
            # spoken_text() exists for Amazon Polly, which reads "325" as "three
            # hundred twenty five". ElevenLabs does not have that problem — it
            # says "325 BioLabs" correctly on its own. Feeding it the
            # pre-split "three two five" makes it worse, not better: it staggers
            # the digits unnaturally and inserts an audible artifact before them.
            #
            # Measured, not assumed. Three clips of the same sentence were
            # rendered through ElevenLabs on prod 2026-08-16 and compared by ear
            # — "3-2-5", raw "325", and "three two five". Jeff picked raw "325".
            # An earlier version of this line applied spoken_text() here and
            # shipped exactly the staggered "M-325" delivery he then reported.
            #
            # So the rule is per-engine, and the seam is the engine, not the
            # text: normalise for <Say> (voice._say), send raw to ElevenLabs.
            audio = providers.tts_greeting_audio(n.greeting)
            if audio:
                url = _save_static(audio, f"comms/greeting-{n.pk}.mp3")
                # Stamp the URL with a fingerprint of (text + rendered bytes).
                # Two jobs, both learned the hard way on 2026-08-16:
                #  1. voice_check recomputes it to prove the mp3 is a render of
                #     the greeting text that is in the database TODAY. Without
                #     it the audio layer is unverifiable, and the check had to
                #     fail on every deploy to stay honest.
                #  2. It is the CDN cache key. Re-rendering from unchanged text
                #     leaves the filename identical, and these are served
                #     immutable — Cloudflare kept handing Twilio the superseded
                #     greeting until the URL changed. Callers heard the old one.
                url = f"{url}?v={audio_token(n.greeting, audio)}"
                n.greeting_audio = url
                n.save(update_fields=["greeting_audio"])
                done += 1
                self.stdout.write(f"  {n.e164}: {len(audio)} bytes -> {url}")
            else:
                offline += 1
        if offline and not done:
            self.stdout.write(self.style.WARNING(
                "No audio generated - ElevenLabs offline. Set ELEVENLABS_API_KEY "
                "(and pip install requests) on the server, then re-run."))
        self.stdout.write(self.style.SUCCESS(
            f"Greeting audio: {done} generated, {offline} skipped (offline)."))
