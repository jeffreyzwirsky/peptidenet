import logging

from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from xml.sax.saxutils import escape as _xml_escape

from . import phone, providers, sms
from . import voice as voicelib
from .models import Call, PhoneNumber, Voicemail

XML = "application/xml"

log = logging.getLogger("comms")


def log_security(request, kind, detail):
    try:
        from apps.security.utils import log_event
        log_event(request, kind, detail=detail)
    except Exception:
        pass


def _lookup_number(request):
    # Twilio POSTs the called number as To/Called; ?number= is our own fallback.
    # normalize() also repairs the "+"→space decoding that can hit query strings.
    cand = (request.POST.get("To") or request.POST.get("Called")
            or request.GET.get("number") or "")
    e164 = phone.normalize(cand)
    return PhoneNumber.objects.filter(e164=e164, is_active=True).first()


def _call_of(request):
    """The Call row this callback belongs to, or None.

    CallSid is in the POST body on Twilio's own callbacks and in the query
    string on the ones whose URL we built ourselves (?call_sid=), because
    recordingStatusCallback does not carry it in the body.
    """
    sid = request.POST.get("CallSid") or request.GET.get("call_sid") or ""
    return Call.objects.filter(twilio_sid=sid).first() if sid else None


def _guard(request):
    """Twilio signature check (skipped in dev when no auth token).

    A failure is recorded, not just refused. A forged webhook is somebody
    actively trying to inject fake calls, texts or voicemails into the system —
    that belongs in the Security audit trail, and the ``bad_signature`` event
    kind existed for it but nothing ever wrote one.
    """
    ok = providers.validate_twilio_signature(request)
    if not ok:
        try:
            from apps.security.utils import log_event
            log_event(request, "bad_signature",
                      detail=f"unverified Twilio webhook to {request.path}")
        except Exception:
            pass
    return ok


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
        # The STOP/HELP/START replies are staff-editable in the compliance page;
        # an unescaped "&" or "<" there produced malformed TwiML (silently no
        # reply to a legally-required STOP confirmation), and a crafted value
        # could inject sibling verbs.
        twiml += f"<Message>{_xml_escape(reply)}</Message>"
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


def _turn_of(request):
    """Which turn of the conversation this callback belongs to (1-based).

    Carried in the <Gather> action URL because Twilio holds no session state.
    Clamped rather than trusted: the query string is caller-influencable in
    principle, and an absurd value here would otherwise decide how many LLM
    round-trips a single call can buy.
    """
    try:
        return max(1, min(int(request.GET.get("turn") or 1), 20))
    except (TypeError, ValueError):
        return 1


def _log_turn(call, speech, reply):
    """Append one exchange to the Call's transcript, as it happens.

    This is worth a write per turn for two reasons.

    1. Memory. The next turn is grounded in what was already said, so "how much
       is that one?" resolves instead of being answered blind.
    2. Corpus. Phase 2 learns from transcripts — and until now the only
       transcript a call could produce was of the voicemail left AFTER the agent
       stopped talking. The conversation itself, which is the thing worth
       learning from, was never written down anywhere.

    Best-effort by design: a database problem must never break a live call.
    """
    if not call:
        return
    try:
        prior = call.transcript or ""
        merged = prior + f"Caller: {speech}\nAgent: {reply}\n"
        if len(merged) > 8000:                    # keep whole lines only
            merged = merged[-8000:].split("\n", 1)[-1]
        call.transcript = merged
        fields = ["transcript"]
        if not call.transcript_source:
            call.transcript_source = "conversation"
            fields.append("transcript_source")
        call.save(update_fields=fields)
    except Exception:
        log.exception("comms: could not log conversation turn for call %s",
                      getattr(call, "pk", "?"))


@csrf_exempt
@require_POST
def gather(request):
    """AI intake speech callback: answer the caller's question (guarded), then
    hand back a TwiML document that asks for the NEXT question. A keypress or
    silence -> record the message.

    Before 2026-08-16 this always ended the conversation: one answer, then the
    beep — "it only lets you ask one question", as Jeff put it after the first
    working call. The loop itself lives in voice.agent_reply_twiml(); what
    changes here is that the turn counter and the subject line travel with it,
    and each exchange is written to the Call row as it happens.
    """
    if not _guard(request):
        return HttpResponseForbidden("bad signature")
    number = _lookup_number(request)
    if number is None:
        return HttpResponse(
            '<?xml version="1.0" encoding="UTF-8"?><Response><Reject/></Response>',
            content_type=XML)
    turn = _turn_of(request)
    carried_subject = (request.GET.get("subject") or "")[:180]
    speech = (request.POST.get("SpeechResult") or "").strip()
    # Caller pressed a key (0 = "just let me leave a message"), or said nothing.
    # Mid-conversation that must NOT replay the greeting, hence handoff_twiml.
    if request.POST.get("Digits") or not speech:
        if turn > 1:
            return HttpResponse(
                voicelib.handoff_twiml(number, request, subject=carried_subject),
                content_type=XML)
        return HttpResponse(voicelib.voicemail_twiml(number, request), content_type=XML)
    call = _call_of(request)
    from . import agent
    try:
        reply = agent.answer(speech, number.site,
                             history=(call.transcript if call else ""))
        # The subject line is the caller's REASON for calling, which is their
        # first question — computed once and carried forward, not recomputed
        # every turn. That also keeps a second LLM round-trip out of the middle
        # of a live call, where latency is a caller listening to silence.
        subject = carried_subject or agent.subject_line(speech, number.site)
    except Exception:  # never let the agent break the call
        reply = agent.SAFE_FALLBACK
        subject = carried_subject or " ".join(speech.split()[:8])[:80]
    _log_turn(call, speech, reply)
    return HttpResponse(
        voicelib.agent_reply_twiml(number, request, reply, subject, turn=turn),
        content_type=XML)


def _close_call(request, duration=0):
    """Move a Call off 'ringing'.

    Twilio only POSTs a call-status callback to the URL configured on the phone
    NUMBER in the console — it cannot be set from TwiML for an inbound leg. That
    was never configured, so all 18 Call rows sat at status='ringing' with
    duration_sec=0 forever and the Calls page showed a fiction. Until the console
    field is set (see comms:call_status below), we close the record from the
    callbacks we *do* receive, which carry CallSid and CallStatus.
    """
    sid = request.POST.get("CallSid") or request.GET.get("call_sid") or ""
    if not sid:
        return None
    call = Call.objects.filter(twilio_sid=sid).first()
    if not call:
        return None
    status = request.POST.get("CallStatus") or ""
    fields = []
    if status and status != call.status:
        call.status, _ = status, fields.append("status")
    if duration and not call.duration_sec:
        call.duration_sec, _ = duration, fields.append("duration_sec")
    if fields:
        call.save(update_fields=fields)
    return call


@csrf_exempt
@require_POST
def call_status(request):
    """Twilio call-status callback.

    NOT wired automatically: paste this URL into the Twilio Console under the
    number's Voice configuration -> "Call status changes" ->
    https://smashfatbiolabs.ca/webhooks/twilio/call-status/ (POST). Until then
    _close_call() approximates it from the recording callbacks.
    """
    if not _guard(request):
        return HttpResponseForbidden("bad signature")
    _close_call(request, int(request.POST.get("CallDuration", 0) or 0))
    return HttpResponse("", content_type=XML)


@csrf_exempt
@require_POST
def recording_done(request):
    """``action`` target of <Record>. Thanks the caller and hangs up.

    Without this Twilio re-requests the current document when the recording
    ends, which put the caller back at the top of the AI greeting instead of
    ending the call."""
    if not _guard(request):
        return HttpResponseForbidden("bad signature")
    _close_call(request, int(request.POST.get("RecordingDuration", 0) or 0))
    return HttpResponse(voicelib.recording_done_twiml(), content_type=XML)


@csrf_exempt
@require_POST
def recording(request):
    """Recording-complete callback: create the Voicemail + transcribe (Whisper)."""
    if not _guard(request):
        return HttpResponseForbidden("bad signature")
    number = _lookup_number(request)
    site = number.site if number else None
    rec_url = (request.POST.get("RecordingUrl", "") or "").strip()
    # Rendered as an href in the console. Anything that is not a plain https URL
    # is dropped rather than stored — a `javascript:` value here becomes stored
    # XSS the moment an operator clicks Play.
    if rec_url and not rec_url.lower().startswith("https://"):
        log_security(request, "blocked", f"refused non-https RecordingUrl: {rec_url[:80]}")
        rec_url = ""
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
    # call= is the join a learning loop needs: without it there is no way to get
    # from a stored message back to the conversation that produced it. Every
    # voicemail before 2026-08-16 has call_id NULL for exactly this reason —
    # the Call was resolved here and then not used.
    vm = Voicemail.objects.create(
        site=site, contact=contact, from_number=frm, call=call,
        category=request.GET.get("category", "general"),
        subject=request.GET.get("subject", "")[:200],
        recording_url=rec_url, duration_sec=duration, transcript=text,
        transcript_source=source,
    )
    if call and call.status in ("", "ringing", "in-progress"):
        call.status = "completed"
        call.save(update_fields=["status"])
    if call and rec_url and not call.recording_url:
        call.recording_url = rec_url
        call.duration_sec = call.duration_sec or duration
        if text:
            # APPEND, not "only if empty". From 2026-08-16 the Call row carries
            # the conversation itself (one block per turn), so `not
            # call.transcript` is false on every AI call — the spoken message
            # would have been dropped from the one record that ties it to the
            # conversation that produced it.
            call.transcript = (
                f"{call.transcript}\nVoicemail: {text}" if call.transcript else text)
            call.transcript_source = call.transcript_source or source
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
