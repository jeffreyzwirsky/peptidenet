"""TwiML builders for inbound calls — greeting → voicemail, or a simple IVR.
Mirrors SMASH's straight-to-voicemail default with an optional phone tree."""
from urllib.parse import urlencode
from xml.sax.saxutils import escape

from django.conf import settings
from django.urls import reverse


def _say(text):
    # Amazon Polly Neural voice via Twilio <Say> — natural-sounding, configurable
    # through PEPTIDENET_TTS_VOICE (settings.COMMS_TTS_VOICE).
    voice = getattr(settings, "COMMS_TTS_VOICE", "Polly.Ruth-Neural")
    return f"<Say voice=\"{voice}\">{escape(text)}</Say>"


def _greeting(number, request):
    """Play the pre-generated ElevenLabs greeting mp3 if one exists, else fall
    back to Twilio <Say> with the Polly Neural voice."""
    audio = getattr(number, "greeting_audio", "")
    if audio:
        return f"<Play>{escape(request.build_absolute_uri(audio))}</Play>"
    return _say(number.greeting)


def _record_fragment(number, request, category="general", subject=""):
    """A <Record> that posts to the recording webhook, carrying an optional
    AI-intake subject line through to the created Voicemail."""
    q = {"number": number.e164, "category": category}
    if subject:
        q["subject"] = subject[:180]
    action = request.build_absolute_uri(reverse("comms:recording") + "?" + urlencode(q))
    return (
        f'<Record maxLength="120" playBeep="true" transcribe="false" '
        f'recordingStatusCallback="{escape(action)}" '
        f'recordingStatusCallbackEvent="completed"/>'
    )


def voicemail_twiml(number, request, category="general"):
    """Greeting, then record a voicemail and post to the recording webhook."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<Response>'
        f"{_greeting(number, request)}"
        f"{_record_fragment(number, request, category)}"
        f"{_say('We did not receive a recording. Goodbye.')}"
        "<Hangup/></Response>"
    )


def intake_twiml(number, request):
    """AI intake: greet + research-use-only disclaimer, then gather the caller's
    question by speech. No speech -> fall through to a normal voicemail."""
    gather_url = request.build_absolute_uri(
        reverse("comms:gather") + "?" + urlencode({"number": number.e164}))
    greet = ("Thanks for calling 325 BioLabs. This is the AI assistant. All of our "
             "products are for laboratory research use only, and not for human or "
             "veterinary consumption. How can I help you today? "
             "Or press zero at any time to leave a message for the team.")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<Response>'
        f'<Gather input="speech dtmf" numDigits="1" speechTimeout="auto" '
        f'speechModel="phone_call" action="{escape(gather_url)}" method="POST">'
        f"{_say(greet)}</Gather>"
        f"{_say('I did not catch that — let me take a message.')}"
        f"{_greeting(number, request)}"
        f"{_record_fragment(number, request)}"
        f"{_say('We did not receive a recording. Goodbye.')}"
        "<Hangup/></Response>"
    )


def agent_reply_twiml(number, request, reply, subject=""):
    """Speak the guarded AI reply, then record the full voicemail (with the
    AI-built subject line attached)."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<Response>'
        f"{_say(reply)}"
        f"{_say('Please leave your name, number, and any other details after the tone, and the team will follow up.')}"
        f"{_record_fragment(number, request, subject=subject)}"
        f"{_say('We did not receive a recording. Goodbye.')}"
        "<Hangup/></Response>"
    )


def ivr_twiml(number, request):
    """Simple phone tree: prompt for a digit → gather posts back to the voice
    webhook with ?digit=. Falls back to voicemail on timeout."""
    action = request.build_absolute_uri(
        reverse("comms:voice") + "?" + urlencode({"number": number.e164})
    )
    opts = list(number.ivr_options.all())
    menu = number.greeting + " " + " ".join(
        f"Press {o.digit} for {o.label}." for o in opts
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<Response>'
        f'<Gather numDigits="1" timeout="5" action="{escape(action)}" method="POST">'
        f"{_say(menu)}</Gather>"
        f"{_say('Sorry, I did not get that.')}"
        f'<Redirect method="POST">{escape(action)}</Redirect>'
        "</Response>"
    )
