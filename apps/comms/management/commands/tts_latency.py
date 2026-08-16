"""Measure what ElevenLabs synthesis would cost a LIVE CALL, in seconds of dead air.

The open question from 2026-08-16 is whether the agent's replies should stop
going through Twilio <Say> (Polly.Ruth-Neural, which Jeff described as "a little
bit too robotic") and be synthesised per reply by ElevenLabs instead. The greeting
already uses ElevenLabs, but that is a one-time admin render — a reply is
synthesised while the caller is on the line, listening to nothing.

So the decision needs a number, not a preference. A slow natural voice is worse
on a phone call than a fast synthetic one, and neither of us can hear the
difference from a diff. This command produces the number, on the box where the
key actually lives:

    python manage.py tts_latency
    python manage.py tts_latency --runs 5

It measures the ROUND TRIP for reply-length text — request out to mp3 bytes in
hand — because that is the whole of the gap the caller experiences. Twilio's
<Play> fetch and the caller's own network add to it; this is a floor, not a
total, and the output says so.

Reference points for reading the result:
  under 400ms   comparable to <Say>; the swap is invisible
  400ms-1s      a noticeable beat before every answer
  over 1s       worse than the robotic voice, on every turn of every call
"""
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.comms import providers

# Three real reply shapes, at the length cap the agent now speaks to.
SAMPLES = [
    ("short", "BPC-157 is $64 a vial."),
    ("typical", "BPC-157 is $64 a vial and it's in stock in 5 and 10 milligram "
                "sizes. All products are for laboratory research use only."),
    ("at the cap", "Retatrutide is $189 a vial in 10 and 20 milligram sizes and "
                   "ships from our manufacturing partner within 7 to 14 days. All "
                   "products are for laboratory research use only, and not for "
                   "human or veterinary consumption."),
]


class Command(BaseCommand):
    help = "Measure ElevenLabs per-reply synthesis latency before wiring it into live calls."

    def add_arguments(self, parser):
        parser.add_argument("--runs", type=int, default=3,
                            help="Measurements per sample (default 3).")

    def handle(self, *args, **opts):
        if not settings.ELEVENLABS_API_KEY:
            # Not a result. Say so rather than printing zeros.
            self.stdout.write(self.style.ERROR(
                "ELEVENLABS_API_KEY is not set in this environment — NOTHING WAS "
                "MEASURED. Run this on the production box, where the key lives. "
                "A missing key is not a fast result."))
            raise SystemExit(1)

        self.stdout.write(
            f"model={settings.ELEVENLABS_MODEL}  "
            f"voice={settings.ELEVENLABS_VOICE_ID or '(default Rachel)'}  "
            f"runs={opts['runs']}\n")

        worst = 0.0
        failures = 0
        for label, text in SAMPLES:
            times = []
            for _ in range(opts["runs"]):
                t0 = time.monotonic()
                audio = providers.tts_greeting_audio(text)
                dt = time.monotonic() - t0
                if not audio:
                    failures += 1
                    self.stdout.write(self.style.ERROR(
                        f"  {label}: request returned no audio after {dt:.2f}s "
                        "— see the log line from providers.tts_greeting_audio."))
                    continue
                times.append(dt)
            if not times:
                continue
            best, med = min(times), sorted(times)[len(times) // 2]
            worst = max(worst, med)
            self.stdout.write(
                f"  {label:11} {len(text):3} chars   "
                f"best {best:.2f}s   median {med:.2f}s   n={len(times)}")

        self.stdout.write("")
        if failures:
            self.stdout.write(self.style.ERROR(
                f"{failures} request(s) returned nothing — the numbers above are "
                "from the successful ones only and are not the whole picture."))
        if not worst:
            self.stdout.write(self.style.ERROR("No successful measurement. No verdict."))
            raise SystemExit(1)

        self.stdout.write("This is the SYNTHESIS floor only. Twilio then has to fetch "
                          "the mp3, which adds to it.")
        if worst < 0.4:
            self.stdout.write(self.style.SUCCESS(
                f"median {worst:.2f}s — comparable to <Say>. Worth trying on a real call."))
        elif worst < 1.0:
            self.stdout.write(self.style.WARNING(
                f"median {worst:.2f}s — a noticeable beat before every answer, on "
                "every turn. Judge it on a real call before committing."))
        else:
            self.stdout.write(self.style.ERROR(
                f"median {worst:.2f}s — this is worse than the robotic voice. Try "
                "other Polly Neural voices first (PEPTIDENET_TTS_VOICE)."))
