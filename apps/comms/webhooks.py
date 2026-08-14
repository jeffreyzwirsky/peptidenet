from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import phone, providers, sms
from . import voice as voicelib
from .models import Call, PhoneNumber, Voicemail

XML = "application/xml"


def _lookup_number(request):
    # Twilio POSTs the called number as To/Called; ?number= is our own fallback.
    # normalize() also repairs the "+"→space decoding that can hit query strings.
    cand = (request.POST.get("To") or request.POST.get("Called")
            or request.GET.get("number") or "")
    e164 = phone.normalize(cand)
    return PhoneNumber.objects.filter(e164=e164, is_active=True).first()


def _guard(request):
    """Twilio signature check (skipped in dev when no auth token)."""
    return providers.validate_twilio_signature(request)


@csrf_exempt
@require_POST
def inbound_sms(request):
    """Twilio inbound-SMS webhook: log, keyword-handle, optional auto-reply (TwiML)."""
    if not _guard(request):
        return HttpResponseForbidden("bad signature")
    number = _lookup_number(request)
    site = number.site if number else None
    body = request.POST.get("Body", "")
    frm = request.POST.get("From", "")
    to = request.POST.get("To", "")
    _msg, reply = sms.handle_inbound(frm, to, body, site=site)
    twiml = '<?xml version="1.0" encoding="UTF-8"?><Response>'
    if reply:
        twiml += f"<Message>{reply}</Message>"
    twiml += "</Response>"
    return HttpResponse(twiml, content_type=XML)


@csrf_exempt
@require_POST
def sms_status(request):
    """Delivery-status callback: update the matching outbound message."""
    if not _guard(request):
        return HttpResponseForbidden("bad signature")
    from .models import Message
    sid = request.POST.get("MessageSid", "")
    status = request.POST.get("MessageStatus", "")
    if sid and status:
        Message.objects.filter(twilio_sid=sid).update(status=status)
    return HttpResponse("", content_type=XML)


@csrf_exempt
@require_POST
def voice(request):
    """Inbound call: IVR (if enabled + digit) else straight to voicemail."""
    if not _guard(request):
        return HttpResponseForbidden("bad signature")
    number = _lookup_number(request)
    if number is None or not number.voice_enabled:
        return HttpResponse(
            '<?xml version="1.0" encoding="UTF-8"?><Response><Reject/></Response>',
            content_type=XML,
        )
    # Log the inbound call once (best-effort).
    Call.objects.get_or_create(
        twilio_sid=request.POST.get("CallSid", ""),
        defaults={"direction": "in", "site": number.site,
                  "from_number": request.POST.get("From", ""),
                  "to_number": number.e164,
                  "status": request.POST.get("CallStatus", "in-progress")},
    )
    digit = request.POST.get("Digits") or request.GET.get("digit")
    if getattr(number, "ai_intake", False) and not digit:
        # Turn-based AI intake: greet + disclaimer, then gather the question.
        return HttpResponse(voicelib.intake_twiml(number, request), content_type=XML)
    if number.ivr_enabled and not digit:
        return HttpResponse(voicelib.ivr_twiml(number, request), content_type=XML)
    category = "general"
    if digit:
        opt = number.ivr_options.filter(digit=digit).first()
        if opt:
            category = opt.voicemail_category
    return HttpResponse(voicelib.voicemail_twiml(number, request, category), content_type=XML)


@csrf_exempt
@require_POST
def gather(request):
    """AI intake speech callback: answer the caller's question (guarded), build a
    subject line, then record the full voicemail. Empty speech -> voicemail."""
    if not _guard(request):
        return HttpResponseForbidden("bad signature")
    number = _lookup_number(request)
    if number is None:
        return HttpResponse(
            '<?xml version="1.0" encoding="UTF-8"?><Response><Reject/></Response>',
            content_type=XML)
    # Caller pressed a key (0 = "just let me leave a message") -> skip the agent.
    if request.POST.get("Digits"):
        return HttpResponse(voicelib.voicemail_twiml(number, request), content_type=XML)
    speech = (request.POST.get("SpeechResult") or "").strip()
    if not speech:
        return HttpResponse(voicelib.voicemail_twiml(number, request), content_type=XML)
    from . import agent
    try:
        reply = agent.answer(speech, number.site)
        subject = agent.subject_line(speech, number.site)
    except Exception:  # never let the agent break the call
        reply, subject = agent.SAFE_FALLBACK, " ".join(speech.split()[:8])[:80]
    return HttpResponse(
        voicelib.agent_reply_twiml(number, request, reply, subject), content_type=XML)


@csrf_exempt
@require_POST
def recording_done(request):
    """``action`` target of <Record>. Thanks the caller and hangs up.

    Without this Twilio re-requests the current document when the recording
    ends, which put the caller back at the top of the AI greeting instead of
    ending the call."""
    if not _guard(request):
        return HttpResponseForbidden("bad signature")
    return HttpResponse(voicelib.recording_done_twiml(), content_type=XML)


@csrf_exempt
@require_POST
def recording(request):
    """Recording-complete callback: create the Voicemail + transcribe (Whisper)."""
    if not _guard(request):
        return HttpResponseForbidden("bad signature")
    number = _lookup_number(request)
    site = number.site if number else None
    rec_url = request.POST.get("RecordingUrl", "")
    # Twilio's recordingStatusCallback does NOT send From/To — only Recording*
    # and CallSid. Reading POST["From"] here is what left every stored voicemail
    # with a blank caller (and therefore no callback number). Prefer the number
    # we pinned into the callback URL when building the TwiML; fall back to the
    # Call row we logged when the call came in.
    frm = (request.GET.get("from") or request.POST.get("From") or "").strip()
    call_sid = request.GET.get("call_sid") or request.POST.get("CallSid", "")
    call = Call.objects.filter(twilio_sid=call_sid).first() if call_sid else None
    if not frm and call:
        frm = call.from_number
    duration = int(request.POST.get("RecordingDuration", 0) or 0)
    contact = sms.resolve_contact(frm, site=site) if frm else None
    text, source = providers.transcribe(rec_url) if rec_url else ("", "")
    vm = Voicemail.objects.create(
        site=site, contact=contact, from_number=frm,
        category=request.GET.get("category", "general"),
        subject=request.GET.get("subject", "")[:200],
        recording_url=rec_url, duration_sec=duration, transcript=text,
        transcript_source=source,
    )
    if call and rec_url and not call.recording_url:
        call.recording_url = rec_url
        call.duration_sec = call.duration_sec or duration
        if text and not call.transcript:
            call.transcript, call.transcript_source = text, source
        call.contact = call.contact or contact
        call.save(update_fields=["recording_url", "duration_sec", "transcript",
                                 "transcript_source", "contact"])

    try:  # AI triage: intent tier + urgency (heuristic when AI offline)
        from . import triage
        triage.classify_voicemail(vm)
    except Exception:
        pass
    try:
        from apps.mailer import mailer
        mailer.voicemail_alert(vm)
    except Exception:
        pass
    return HttpResponse("", content_type=XML)
