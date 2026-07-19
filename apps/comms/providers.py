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


def validate_twilio_signature(request):
    """Verify X-Twilio-Signature. Skipped when no auth token (dev)."""
    token = settings.TWILIO_AUTH_TOKEN
    if not token:
        return True
    try:  # pragma: no cover
        from twilio.request_validator import RequestValidator
        validator = RequestValidator(token)
        sig = request.META.get("HTTP_X_TWILIO_SIGNATURE", "")
        url = request.build_absolute_uri()
        return validator.validate(url, request.POST.dict(), sig)
    except Exception:  # pragma: no cover
        log.exception("signature validation error")
        return False


def transcribe(audio_url):
    """OpenAI Whisper. Returns (text, source). Stub when no key."""
    if not (settings.COMMS_LIVE and settings.OPENAI_API_KEY):
        return ("", "")
    try:  # pragma: no cover
        import requests
        from openai import OpenAI
        audio = requests.get(audio_url, timeout=30).content
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        r = client.audio.transcriptions.create(
            model="whisper-1", file=("vm.mp3", audio),
        )
        return (r.text, "whisper")
    except Exception:  # pragma: no cover
        log.exception("whisper transcription failed")
        return ("", "")


def tts_greeting_audio(text):
    """ElevenLabs TTS for a nicer voice greeting. Returns a URL or None
    (None → the voice webhook falls back to Twilio <Say>)."""
    if not (settings.COMMS_LIVE and settings.ELEVENLABS_API_KEY):
        return None
    # Real impl would synthesize + host the mp3 (e.g. DO Spaces) and return its URL.
    return None  # pragma: no cover


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
