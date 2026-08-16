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
            # spoken_text(), NOT the raw DB string. This path never passes
            # through voice._say(), so it never picked up the pronunciation
            # normalisation. Regenerating the mp3 to "fix" the 3-2-5 greeting
            # would have rendered "three hundred twenty five" all over again —
            # and looked fixed, because the file changed and voice_check stopped
            # complaining. Third layer of one trap: the code string, the DB row,
            # and now the renderer that reads the DB row.
            audio = providers.tts_greeting_audio(voice.spoken_text(n.greeting))
            if audio:
                url = _save_static(audio, f"comms/greeting-{n.pk}.mp3")
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
