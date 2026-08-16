"""
Provider adapters — mirror the SMASH stack (Twilio SMS/voice, OpenAI Whisper
transcription, ElevenLabs TTS, Anthropic Claude AI drafts).

Every adapter degrades GRACEFULLY with no credentials: it logs what it *would*
do and returns a stub, so the whole system runs and is testable locally without
sending anything or spending money. Nothing goes live until the relevant env
keys are set AND settings.COMMS_LIVE is true.
"""
import logging

from django.conf import settings

log = logging.getLogger("comms")


def sms_live():
    return bool(settings.COMMS_LIVE and settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN)


def send_sms(from_number, to_number, body):
    """Return (twilio_sid, error). In stub mode returns a fake sid, no send."""
    if not sms_live():
        log.info("[stub] SMS %s -> %s: %s", from_number, to_number, body[:60])
        return ("STUB-SMS", "")
    try:  # pragma: no cover - only runs with real creds
        from twilio.rest import Client
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        msg = client.messages.create(to=to_number, from_=from_number, body=body)
        return (msg.sid, "")
    except Exception as e:  # pragma: no cover
        log.exception("twilio send failed")
        return ("", str(e)[:200])


def place_call(to_number, from_number, twiml):
    """Originate a call that plays `twiml` when answered. Returns (sid, error).

    Used for click-to-call: we ring the OPERATOR first, and the TwiML then dials
    the customer — so the operator is already on the line when the customer's
    phone rings, and the customer sees the business number.
    """
    if not sms_live():
        log.info("[stub] CALL %s -> %s", from_number, to_number)
        return ("STUB-CALL", "")
    try:  # pragma: no cover - only runs with real creds
        from twilio.rest import Client
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        call = client.calls.create(to=to_number, from_=from_number, twiml=twiml)
        return (call.sid, "")
    except Exception as e:  # pragma: no cover
        log.exception("twilio call failed")
        return ("", str(e)[:200])


def validate_twilio_signature(request):
    """Verify X-Twilio-Signature.

    FAILS CLOSED. This used to `return True` whenever TWILIO_AUTH_TOKEN was
    empty — and `scripts/deploy.sh` never wrote a TWILIO_* line into the
    production `.env`, so a droplet rebuilt from the documented path came up
    with every `/webhooks/twilio/*` route publicly writable: anyone could POST
    a forged STOP to suppress a real customer's messaging and plant rows in the
    deliberately-immutable SmsConsent trail that the compliance export presents
    as a legal record.

    A missing credential now means "reject", never "allow". The dev bypass is a
    separate, explicit opt-in that is impossible to reach with DEBUG off.
    """
    token = settings.TWILIO_AUTH_TOKEN
    if not token:
        if settings.DEBUG and getattr(settings, "COMMS_WEBHOOK_INSECURE", False):
            log.warning("twilio webhook signature check bypassed (DEBUG dev flag)")
            return True
        log.error("twilio webhook rejected: TWILIO_AUTH_TOKEN is not configured")
        return False
    try:  # pragma: no cover
        from twilio.request_validator import RequestValidator
        validator = RequestValidator(token)
        sig = request.META.get("HTTP_X_TWILIO_SIGNATURE", "")
        url = request.build_absolute_uri()
        return validator.validate(url, request.POST.dict(), sig)
    except Exception:  # pragma: no cover
        log.exception("signature validation error")
        return False


# Recording media lives on this host and nowhere else. Used to validate a stored
# URL before the console proxy fetches it: a proxy that fetches whatever host it
# is handed is an SSRF hole, and `recording_url` is written from a webhook body.
RECORDING_HOST = "api.twilio.com"


def recording_url_ok(url):
    """True only for an https URL on Twilio's recording host.

    Deliberately a SECOND check, not a replacement for the write-time one in
    webhooks.recording(): that one only enforces `https://`, so any https host
    passes it. Re-validating at fetch time means a forged webhook that planted a
    URL cannot turn the console into a request proxy for an arbitrary host.
    """
    from urllib.parse import urlparse
    try:
        p = urlparse((url or "").strip())
    except ValueError:
        return False
    return p.scheme == "https" and p.hostname == RECORDING_HOST


def fetch_recording(audio_url, timeout=30):
    """GET a Twilio recording WITH credentials. Returns (response, reason).

    Success is `(response, "")`; every failure is `(None, reason)` and never a
    silent empty success — that shape is exactly what hid the empty-transcript
    bug for a month.

    **Twilio recording media requires HTTP Basic auth (AccountSid/AuthToken).**
    Unauthenticated, api.twilio.com answers 401 with a ~232-byte XML body;
    verified live 2026-08-16. That single fact has now produced two separate
    defects — transcription fed the XML to Whisper as if it were audio, and the
    console's Play button pointed a browser straight at the URL, where it 401s
    because a browser cannot send those credentials. Both consumers now come
    through here, so the next thing that needs a recording inherits the auth
    instead of rediscovering the 401.
    """
    if not recording_url_ok(audio_url):
        log.error("recording fetch refused, not an https %s URL: %r",
                  RECORDING_HOST, (audio_url or "")[:120])
        return (None, "bad_url")
    if not (settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN):
        log.error("recording fetch refused: TWILIO credentials not configured")
        return (None, "no_credentials")
    try:
        import requests
        resp = requests.get(
            audio_url, timeout=timeout,
            auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN))
    except Exception as e:  # pragma: no cover - network
        log.exception("recording fetch errored for %s", audio_url[:120])
        return (None, f"error:{type(e).__name__}")
    ctype = (resp.headers.get("content-type") or "").lower()
    # A 200 carrying XML or JSON is still a failure. Passing it downstream is
    # what hid the transcription bug; handing it to an <audio> tag would render
    # a player that silently never plays.
    if resp.status_code != 200 or not ctype.startswith("audio"):
        log.error("recording fetch refused: status=%s ctype=%r bytes=%s url=%s",
                  resp.status_code, ctype, len(resp.content or b""),
                  audio_url[:120])
        return (None, "fetch_failed")
    return (resp, "")


def transcribe(audio_url):
    """OpenAI Whisper. Returns (text, source). Stub when no key."""
    if not (settings.COMMS_LIVE and settings.OPENAI_API_KEY):
        return ("", "")
    try:  # pragma: no cover
        from openai import OpenAI
        resp, reason = fetch_recording(audio_url)
        if resp is None:
            return ("", reason or "fetch_failed")
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        r = client.audio.transcriptions.create(
            model="whisper-1", file=("vm.mp3", resp.content),
        )
        return (r.text, "whisper")
    except Exception:  # pragma: no cover
        log.exception("whisper transcription failed for %s", audio_url[:120])
        return ("", "error")


def tts_greeting_audio(text):
    """ElevenLabs TTS -> mp3 bytes for a natural greeting. Returns raw mp3 bytes,
    or None (caller falls back to Twilio <Say> with the Polly Neural voice).
    Generation is a one-time admin step (generate_greeting_audio), not per call."""
    if not (settings.ELEVENLABS_API_KEY and (text or "").strip()):
        return None
    try:  # pragma: no cover - needs a real ElevenLabs key
        import requests
        voice_id = getattr(settings, "ELEVENLABS_VOICE_ID", "") or "21m00Tcm4TlvDq8ikWAM"
        model = getattr(settings, "ELEVENLABS_MODEL", "") or "eleven_turbo_v2_5"
        r = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={"xi-api-key": settings.ELEVENLABS_API_KEY,
                     "accept": "audio/mpeg", "content-type": "application/json"},
            json={"text": text, "model_id": model,
                  "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}},
            timeout=30,
        )
        if r.status_code == 200 and r.content:
            return r.content
        log.warning("elevenlabs tts %s: %s", r.status_code, r.text[:200])
    except Exception:
        log.exception("elevenlabs tts error")
    return None


def draft_reply(thread_messages, contact_name=""):
    """AI-drafted SMS reply (Anthropic Claude Haiku, like SMASH). Returns "" if
    no key so the compose box stays usable."""
    if not (settings.COMMS_LIVE and settings.ANTHROPIC_API_KEY):
        # Offline-friendly heuristic draft so the button still does something useful.
        last = thread_messages[-1].body if thread_messages else ""
        name = f" {contact_name}" if contact_name else ""
        return (f"Hi{name}, thanks for reaching out — happy to help with that. "
                "Could you share your order number or the product you're asking about?")
    try:  # pragma: no cover
        import anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        convo = "\n".join(f"{m.direction}: {m.body}" for m in thread_messages[-8:])
        msg = client.messages.create(
            model="claude-haiku-4-5", max_tokens=160,
            messages=[{"role": "user", "content":
                       f"Draft a short, friendly SMS reply for a research-peptide "
                       f"store support line. Conversation so far:\n{convo}\nReply:"}],
        )
        return msg.content[0].text.strip()
    except Exception:  # pragma: no cover
        log.exception("ai draft failed")
        return ""
