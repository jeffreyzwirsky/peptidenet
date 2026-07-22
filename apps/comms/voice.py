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


def voicemail_twiml(number, request, category="general"):
    """Greeting, then record a voicemail and post to the recording webhook."""
    q = urlencode({"number": number.e164, "category": category})
    action = request.build_absolute_uri(reverse("comms:recording") + "?" + q)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<Response>'
        f"{_greeting(number, request)}"
        f'<Record maxLength="120" playBeep="true" transcribe="false" '
        f'recordingStatusCallback="{escape(action)}" '
        f'recordingStatusCallbackEvent="completed"/>'
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
