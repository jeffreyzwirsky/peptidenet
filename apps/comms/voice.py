"""TwiML builders for inbound calls — greeting → voicemail, or a simple IVR.
Mirrors SMASH's straight-to-voicemail default with an optional phone tree."""
import re
from urllib.parse import urlencode
from xml.sax.saxutils import escape

from django.conf import settings
from django.urls import reverse

# How many questions the AI agent will take before it stops and records a
# message. Before 2026-08-16 this was effectively 1: agent_reply_twiml() spoke
# one answer and went straight to <Record>, which is what Jeff heard on the
# acceptance call — "it only lets you ask one question and then goes straight
# to voicemail". A ceiling still exists because an unbounded loop is an
# unbounded spend and an unbounded time on hold.
DEFAULT_MAX_TURNS = 4


def max_turns():
    return max(1, int(getattr(settings, "COMMS_MAX_AI_TURNS", DEFAULT_MAX_TURNS) or 1))


# Polly reads "325 BioLabs" as "three hundred twenty five BioLabs". Jeff asked
# for it spoken as 3-2-5.
#
# This is applied inside _say(), not at the call sites, deliberately: the brand
# string arrives from four different places and fixing only the one in this file
# is the "a code fix is not a data fix" trap.
#   1. the hardcoded greeting in intake_twiml() below                (code)
#   2. PhoneNumber.greeting — a 247-char DB row, spoken by _greeting() (DB)
#   3. Site.brand_name / ComplianceConfig.business_name, which reach the LLM
#      system prompt and can come back inside a generated reply       (DB → LLM)
#   4. a pre-generated greeting_audio mp3                       (rendered audio)
# Routing every <Say> through here covers 1-3. Nothing in code can cover 4 —
# that is already-rendered audio and must be regenerated. `manage.py voice_check`
# reports whether one is set.
#
# Spelled as words rather than "3-2-5": a hyphenated form is read as a range or
# a subtraction by some voices. SSML would be the "proper" fix and is not
# available here — _say() XML-escapes its input, so a <say-as> tag would be
# spoken as literal angle brackets.
_BRAND_DIGITS = re.compile(r"\b325(?=[\s-]*bio\s?labs\b)", re.I)


def spoken_text(text):
    """Normalise text for a TTS engine's ear. Applied to every <Say>."""
    return _BRAND_DIGITS.sub("three two five", text or "")


def _say(text):
    # Amazon Polly Neural voice via Twilio <Say> — natural-sounding, configurable
    # through PEPTIDENET_TTS_VOICE (settings.COMMS_TTS_VOICE).
    voice = getattr(settings, "COMMS_TTS_VOICE", "Polly.Ruth-Neural")
    return f"<Say voice=\"{voice}\">{escape(spoken_text(text))}</Say>"


def _greeting(number, request):
    """Play the pre-generated ElevenLabs greeting mp3 if one exists, else fall
    back to Twilio <Say> with the Polly Neural voice."""
    audio = getattr(number, "greeting_audio", "")
    if audio:
        return f"<Play>{escape(request.build_absolute_uri(audio))}</Play>"
    return _say(number.greeting)


def _record_fragment(number, request, category="general", subject=""):
    """A <Record> that posts to the recording webhook, carrying an optional
    AI-intake subject line through to the created Voicemail.

    Two things here are load-bearing and were both wrong before:

    1. **The caller's number travels in the query string.** Twilio's
       ``recordingStatusCallback`` POST carries RecordingUrl/RecordingSid/CallSid
       and *not* From/To — so reading ``request.POST['From']`` in the callback
       produced a blank caller on every single voicemail (all 5 stored ones are
       blank). We know who is calling at the moment we build this TwiML, so the
       number is pinned into the callback URL where it cannot be lost.

    2. **``action`` is set.** ``<Record>`` without an ``action`` makes Twilio
       re-request the *current document* when recording ends — which dropped the
       caller back into the AI greeting and looped them instead of hanging up.
    """
    caller = (request.POST.get("From") or "")[:20]
    q = {"number": number.e164, "category": category}
    if caller:
        q["from"] = caller
    if request.POST.get("CallSid"):
        q["call_sid"] = request.POST["CallSid"][:64]
    if subject:
        q["subject"] = subject[:180]
    status_cb = request.build_absolute_uri(reverse("comms:recording") + "?" + urlencode(q))
    done = request.build_absolute_uri(
        reverse("comms:recording_done") + "?" + urlencode({"number": number.e164}))
    return (
        f'<Record maxLength="120" playBeep="true" transcribe="false" '
        f'timeout="4" finishOnKey="#" '
        f'action="{escape(done)}" method="POST" '
        f'recordingStatusCallback="{escape(status_cb)}" '
        f'recordingStatusCallbackEvent="completed"/>'
    )


def recording_done_twiml():
    """Spoken after the caller finishes a message. Ends the call cleanly —
    without this the caller was looped back into the greeting."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<Response>'
        f"{_say('Thanks — we have your message and the team will follow up. Goodbye.')}"
        "<Hangup/></Response>"
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


def _gather(number, request, prompt, turn, subject=""):
    """The <Gather> that collects ONE caller turn.

    There is exactly one of these, used by both the opening greeting and every
    follow-up, because the recogniser settings below are the whole reason the
    agent can hear anyone at all — a second copy that drifted back to the
    defaults would reintroduce "the AI isn't hearing me" from turn 2 onward,
    with turn 1 still working and hiding it.

    speechTimeout: NOT "auto". Twilio documents auto as "stops recognizing
    speech at the first pause" — so a caller who breathes mid-sentence gets cut
    off and the agent answers a fragment. 3 seconds lets a sentence finish. The
    acceptance call on 2026-08-16 transcribed 194 chars across pauses with this
    set; "auto" would have truncated at the first breath.

    speechModel: googlev2_telephony is Google STT V2 tuned for phone audio (this
    is what "Chirp" means in Twilio's vocabulary — there is no
    speechModel="chirp"). Was "phone_call", the legacy generic model.
    deepgram_nova-3 is the alternative worth A/B-ing if this is not enough.

    numDigits="1" stays: it is load-bearing for the "press zero at any time"
    escape, making a single keypress submit immediately. Twilio gives precedence
    to whichever input it detects first and ignores finishOnKey when speech
    comes first, so it does not shorten speech.

    `turn` and `subject` ride in the action URL because Twilio holds no session
    state for us. `subject` in particular is computed once, from the caller's
    FIRST question (that is what a voicemail subject line means), and carried
    forward — recomputing it every turn would put a second LLM round-trip in the
    middle of a live call for no gain.
    """
    q = {"number": number.e164, "turn": turn}
    if subject:
        q["subject"] = subject[:180]
    url = request.build_absolute_uri(reverse("comms:gather") + "?" + urlencode(q))
    return (
        f'<Gather input="speech dtmf" numDigits="1" speechTimeout="3" '
        f'speechModel="googlev2_telephony" language="en-CA" '
        f'action="{escape(url)}" method="POST">'
        f"{_say(prompt)}</Gather>"
    )


# Module-level so `manage.py voice_check` reports on the same string that is
# actually spoken, rather than on a copy of it that can drift.
INTAKE_GREETING = (
    "Thanks for calling 325 BioLabs. This is the AI assistant. All of our "
    "products are for laboratory research use only, and not for human or "
    "veterinary consumption. How can I help you today? "
    "Or press zero at any time to leave a message for the team.")


def intake_twiml(number, request):
    """AI intake: greet + research-use-only disclaimer, then gather the caller's
    question by speech. No speech -> fall through to a normal voicemail."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<Response>'
        f"{_gather(number, request, INTAKE_GREETING, turn=1)}"
        f"{_say('I did not catch that — let me take a message.')}"
        f"{_greeting(number, request)}"
        f"{_record_fragment(number, request)}"
        f"{_say('We did not receive a recording. Goodbye.')}"
        "<Hangup/></Response>"
    )


def agent_reply_twiml(number, request, reply, subject="", turn=1):
    """Speak the guarded AI reply, then take another question — or, at the turn
    ceiling, record the message.

    Until 2026-08-16 this spoke one answer and went straight to <Record>. The
    caller got exactly one question per call and then a beep, which is what Jeff
    reported after the acceptance call. The <Gather> below is what makes it a
    conversation; the verbs after it are the no-answer fall-through, which is
    how Twilio ends a <Gather> that nobody replies to.

    The reply is re-scanned HERE, at the last moment before it is spoken, rather
    than trusted from wherever it was generated. See agent.speakable().
    """
    from . import agent  # local: keeps app-loading order out of this module

    parts = ['<?xml version="1.0" encoding="UTF-8"?>\n<Response>',
             _say(agent.speakable(reply))]
    if turn < max_turns():
        parts.append(_gather(
            number, request,
            "Anything else I can help with? Or press zero to leave a message.",
            turn=turn + 1, subject=subject))
        # Reached only when the caller says nothing to the <Gather> above.
        parts.append(_say(
            "Alright — please leave your name, number and any details after the "
            "tone, and the team will follow up."))
    else:
        parts.append(_say(
            "That is all I can take on this call. Please leave your name, number "
            "and any details after the tone, and the team will follow up."))
    parts.append(_record_fragment(number, request, subject=subject))
    parts.append(_say('We did not receive a recording. Goodbye.'))
    parts.append("<Hangup/></Response>")
    return "".join(parts)


def handoff_twiml(number, request, category="general", subject=""):
    """Drop to voicemail from PART-WAY THROUGH a conversation — the caller
    pressed zero, or went quiet on a follow-up turn.

    Deliberately does not replay the greeting. voicemail_twiml() does, which is
    right for a caller who has not heard it yet and wrong for one who is three
    turns in; re-introducing yourself mid-conversation is exactly the robotic
    edge that was reported.
    """
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<Response>'
        f"{_say('Sure — please leave your name, number and any details after the tone, and the team will follow up.')}"
        f"{_record_fragment(number, request, category, subject=subject)}"
        f"{_say('We did not receive a recording. Goodbye.')}"
        "<Hangup/></Response>"
    )


def bridge_twiml(customer_e164, caller_id):
    """Played to the OPERATOR when they pick up a click-to-call. Dials the
    customer and bridges the two legs, showing the business number as caller ID."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<Response>'
        f"{_say('Connecting you now.')}"
        f'<Dial callerId="{escape(caller_id)}" timeout="30">{escape(customer_e164)}</Dial>'
        f"{_say('The call could not be completed. Goodbye.')}"
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
