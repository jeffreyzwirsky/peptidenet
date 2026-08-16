"""Report what a caller will ACTUALLY hear — the layer a code diff cannot show.

The spoken greeting exists in three places at once, and they can disagree:

  * the hardcoded AI-intake greeting in ``apps/comms/voice.py``  (code)
  * ``PhoneNumber.greeting``                                     (a database row)
  * ``PhoneNumber.greeting_audio``                          (a rendered mp3 file)

Precedence runs backwards from that list: when ``greeting_audio`` is set it is
played with ``<Play>`` and BOTH the database text and the code are irrelevant.
So "I fixed the pronunciation in voice.py" can be entirely true and change
nothing a caller hears.

    python manage.py voice_check
    python manage.py voice_check --number +13252465227

Exit status is 1 when something a caller hears is wrong, so update.sh can gate.

**Why this no longer flags every mp3.** The first version did, on the grounds
that code cannot hear an audio file. True, and useless: it meant the check could
never pass while a greeting mp3 existed, so it printed FAILED on every deploy. A
check that always fails is a check nobody reads — which is exactly how this
codebase has lost audit trails before.

Instead it verifies the mp3 is CURRENT. generate_greeting_audio stamps the URL
with a fingerprint of the text it rendered plus the bytes it produced; this
recomputes that fingerprint from today's greeting and today's file. A match means
the audio really is a render of the text now in the database. A mismatch means it
is stale, and says so with the command that fixes it.

**The pronunciation rule is per-ENGINE, which is why a raw "325" matters on only
one path.** Polly reads "325" as "three hundred twenty five", so text bound for
``<Say>`` goes through ``voice.spoken_text()``. ElevenLabs says "325 BioLabs"
correctly and is made worse by the pre-split form — established by rendering
candidates and comparing by ear, 2026-08-16.
"""
import hashlib
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.comms import voice
from apps.comms.models import PhoneNumber


def audio_token(text, audio_bytes):
    """Fingerprint tying a rendered mp3 to the text it was rendered from.

    Covers BOTH inputs so either kind of drift is caught: the greeting text
    edited without re-rendering, and the audio re-rendered from unchanged text
    (which leaves the URL identical, so a CDN holding it under an immutable
    cache header keeps serving the old file — that happened on 2026-08-16 and
    callers heard the superseded greeting for it).
    """
    h = hashlib.md5()
    h.update((text or "").encode("utf-8"))
    h.update(audio_bytes or b"")
    return h.hexdigest()[:10]


def local_path(url):
    """STATIC_ROOT path for a /static/... URL, or None."""
    rel = (url or "").split("?", 1)[0]
    prefix = settings.STATIC_URL or "/static/"
    if not rel.startswith(prefix):
        return None
    root = getattr(settings, "STATIC_ROOT", None)
    return Path(root) / rel[len(prefix):] if root else None


class Command(BaseCommand):
    help = "Show what callers actually hear, and verify any greeting mp3 is current."

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
            raw = n.greeting or ""
            problems += (self._check_audio(n, raw) if n.greeting_audio
                         else self._check_say(raw))

        self.stdout.write("")
        if problems:
            self.stdout.write(self.style.ERROR(
                f"voice_check: {problems} issue(s) — callers do not hear the fix yet."))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS(
            f"voice_check: {len(numbers)} number(s) OK."))

    # -- the two paths a caller can be on --------------------------------

    def _check_audio(self, n, raw):
        """<Play> of a pre-rendered mp3. The DB text and the code are bypassed."""
        url = n.greeting_audio
        self.stdout.write(f"  PLAYS: pre-generated audio  {url}")
        path = local_path(url)
        if path is None or not path.exists():
            self.stdout.write(self.style.ERROR(
                f"  MISSING on disk: {path or url} — callers hear nothing. Fix: "
                f"manage.py generate_greeting_audio --number {n.e164}"))
            return 1

        stamped = url.split("?v=", 1)[1] if "?v=" in url else ""
        actual = audio_token(raw, path.read_bytes())
        if not stamped:
            self.stdout.write(self.style.ERROR(
                "  UNVERIFIABLE: the URL carries no fingerprint, so nothing can "
                "tell whether this mp3 matches the current greeting. Re-render "
                f"to stamp it: manage.py generate_greeting_audio --number {n.e164}"))
            return 1
        if stamped != actual:
            self.stdout.write(self.style.ERROR(
                f"  STALE: this mp3 is not a render of the current greeting text "
                f"(stamped {stamped}, now {actual}). Callers are hearing a "
                f"superseded recording. Fix: manage.py generate_greeting_audio "
                f"--number {n.e164}"))
            return 1

        self.stdout.write(self.style.SUCCESS(
            f"  current: mp3 matches the greeting text  ({actual}, "
            f"{path.stat().st_size:,} bytes)"))
        # Deliberately no "325" check on this path: ElevenLabs renders it
        # correctly, and the fingerprint above already proves this audio is a
        # render of exactly this text.
        self.stdout.write(f"  rendered from: {raw[:110]}")
        return 0

    def _check_say(self, raw):
        """No mp3, so Twilio <Say> speaks the DB text through Polly."""
        said = voice.spoken_text(raw)
        self.stdout.write("  PLAYS: Twilio <Say> (Polly) — normalisation applies")
        self.stdout.write(f"  DB greeting ({len(raw)} chars): {raw[:110]}")
        if said != raw:
            self.stdout.write(self.style.SUCCESS(f"  normalised to:  {said[:110]}"))
        if "325" in said:
            self.stdout.write(self.style.ERROR(
                '  STILL SAYS 325 after normalisation — Polly will read this as '
                '"three hundred twenty five".'))
            return 1
        return 0
