"""Turn-based AI phone intake — a SHORT, guarded conversation that answers basic
catalogue questions (the same brain as the website chat) and builds a voicemail
subject line, then records the message. Compliance is enforced in layers:

  1. Pre-filter on the CALLER's words: anything about use/dosing/health, or about
     the company/address/staff/internal info, gets a fixed safe deflection and
     NEVER reaches the LLM.
  2. The LLM answer is grounded ONLY in the product catalogue (reuses the site
     chat assistant); every product answer keeps a research-use-only framing.
  3. A guardrail scan runs on the generated answer; if it trips a prohibited
     pattern it is replaced with a safe fallback instead of being spoken. Since
     2026-08-16 the call is a CONVERSATION rather than a single question, so
     this runs per turn — and `speakable()` re-runs it at the moment of
     speaking, so text that was cleared earlier (or drafted by some future
     nightly job) is still checked against today's rules before anyone hears it.
  4. The full call is recorded, and transcribed when the media fetch and
     Whisper both succeed. This said "always ... transcribed" until
     2026-08-16, when it turned out the media fetch had never been
     authenticated and every transcript silently came back empty. Treat a
     missing transcript as a fault to investigate, not as normal.

All of this is easy to loosen later (edit the deflect lists / system prompt).
"""
import logging
import re

from apps.ai import assistant, llm
from apps.blog import guardrails

log = logging.getLogger("comms")

# Spoken answers are capped. Two sentences read aloud is about eleven seconds;
# the same answer as written prose runs past thirty and the caller has forgotten
# the start of it. The cap is on the SUBSTANTIVE answer — the research-use-only
# note is appended afterwards and is never trimmed away to save time.
SPEECH_MAX_SENTENCES = 2
SPEECH_MAX_CHARS = 240
# Only reachable when the model returns one enormous unpunctuated sentence.
SPEECH_HARD_CEILING = 400
# How much of the conversation so far is fed back in on a later turn.
HISTORY_MAX_CHARS = 900

DISCLAIMER = ("All products are for laboratory research use only, and not for "
              "human or veterinary consumption.")

# These three are what a caller hears when the agent will not answer — and until
# 2026-08-16 all three offered "purity" and "certificates of analysis" as things
# the agent could help with. The company holds NEITHER for any compound: that is
# the standing position in assistant.system_prompt ("We hold NO certificate of
# analysis, NO purity result and NO identity confirmation... Never claim testing,
# purity or a COA"), and guardrails.scan() flags the phrase as a hard
# "unsupported COA claim" — the same rule that blocks a blog post.
#
# They survived because they were the strings that BYPASSED the scan: answer()
# returns them instead of scanning, so the one check that would have caught it
# never ran on them. Found by speakable() re-scanning at speak time, on the first
# run of the test suite in this codebase's recent history.
#
# Offering a COA is a claim that one exists. If a caller asks, the answer is that
# we hold none — which the negation escape in guardrails lets through, so it can
# be said plainly. What cannot be done is advertising it.
MEDICAL_DEFLECT = (
    "I'm sorry, I can't advise on use, dosing, or anything medical — please "
    "consult a qualified professional. I can help with what's in the catalogue, "
    "pricing, availability, shipping, and placing an order.")

INFO_DEFLECT = (
    "I'm not able to share company details right now. I can help with what's in "
    "the catalogue, pricing, availability, shipping, and placing an order.")

SAFE_FALLBACK = (
    "I can help with what's in the catalogue, pricing, availability, shipping, "
    "and orders. For anything about use or dosing, please consult a qualified "
    "professional. " + DISCLAIMER)

# Caller asks about use / dosing / health -> deflect (never hits the LLM).
_MEDICAL = re.compile(
    r"\b(dosage|dosing|\bdose\b|how (do|to|much|many) (i |you )?(take|use|inject|administer|dose|run|cycle|stack)|"
    r"inject|injection|administer|milligram|mg (per|a) (day|week)|per day|reconstitut|"
    r"side ?effect|safe for (human|people|me|use)|for (weight|fat) loss|lose weight|"
    r"build muscle|treat|cure|heal|therap|prescri)", re.I)

# Caller asks about the company / address / staff / internal info -> deflect.
_INFO = re.compile(
    r"\b(address|where are you|where('?s| is) (your|the|you)|located|location|warehouse|"
    r"who owns|owner|who runs|manager|your staff|employee|who works|your (real )?name|"
    r"speak to (a|someone|the)|real (human|person)|your hours|are you open|based in|"
    r"headquarter|your office|registered|licen[sc]e|company (info|details)|your email|your number)",
    re.I)


def classify(speech):
    """Return 'medical' | 'info' | 'ok' for the caller's utterance."""
    t = speech or ""
    if _MEDICAL.search(t):
        return "medical"
    if _INFO.search(t):
        return "info"
    return "ok"


def _voice_system_prompt(site):
    return assistant.system_prompt(site) + (
        "\nYOU ARE ON A PHONE CALL. Answer in AT MOST two short sentences — the "
        "caller is listening, not reading. When the question is about a product, "
        "LEAD with the product name and its price, then stock or shipping if it "
        "was asked. Do not list several products unless asked to. No bullet "
        "points, no headings, no URLs read out character by character. "
        "Only discuss the product catalogue, pricing, shipping timeframes, and "
        "how to order on the website. If the caller asks about a certificate of "
        "analysis, purity or testing, say plainly that we hold none for any "
        "compound and never offer one. NEVER give use, "
        "dosing, medical, or health advice. NEVER share the company address, "
        "location, where it ships from, staff names, ownership, hours, or any "
        "internal or contact info — say you cannot share that. Always keep a "
        "research-use-only framing and end product answers with a brief "
        "research-use-only note.")


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def shorten_for_speech(text):
    """Trim a reply to what is bearable to listen to.

    Cuts on SENTENCE boundaries, not characters, and that is a safety property
    rather than a stylistic one: chopping mid-sentence can drop the word that
    carried a negation, turning "we hold no purity result" into a purity claim.
    The character ceiling below is a last resort for a model that returns one
    enormous unpunctuated sentence, and whatever comes out of here is scanned
    again by the caller before it is spoken.
    """
    t = " ".join((text or "").split())
    if not t:
        return ""
    sentences = [s for s in _SENTENCE_SPLIT.split(t) if s]
    out = sentences[0]
    for s in sentences[1:SPEECH_MAX_SENTENCES]:
        if len(out) + 1 + len(s) > SPEECH_MAX_CHARS:
            break
        out = f"{out} {s}"
    if len(out) > SPEECH_HARD_CEILING:
        out = out[:SPEECH_HARD_CEILING].rsplit(" ", 1)[0].rstrip(" ,;:") + "."
    return out


def speakable(text):
    """Re-scan at SPEAK time, not at generate time. Returns text safe to say.

    Same shape as blog_tick.publishable(), and for the same reason. The blog put
    "≥95% purity" and "Certificate of Analysis" live on 2026-08-15 because it
    trusted a compliance verdict recorded weeks earlier. The voice path now has
    that exposure too: a call has several answers in it rather than one, and
    Phase 2 intends to speak canned text a nightly job drafted days beforehand.
    So whatever is about to reach <Say> is scanned here, at the last possible
    moment, regardless of where it came from or how old it is.

    SAFE_FALLBACK is the floor and is returned even if it somehow failed a scan
    itself — there has to be something to say. `test_fixed_phrases_are_speakable`
    is what keeps that from ever mattering.
    """
    t = " ".join((text or "").split())
    if not t:
        return SAFE_FALLBACK
    if guardrails.scan(t)[0]:
        log.error("voice: refused to speak text that failed the guardrail scan: %r",
                  t[:200])
        return SAFE_FALLBACK
    return t


def _recent(history):
    """The tail of the conversation so far, whole lines only."""
    h = (history or "").strip()
    if len(h) > HISTORY_MAX_CHARS:
        h = h[-HISTORY_MAX_CHARS:]
        h = h.split("\n", 1)[-1]      # drop the half line the cut left behind
    return h.strip()


def answer(speech, site, history=""):
    """Return a fully-guarded spoken reply for the caller's question.

    `history` is the conversation so far on this call. Without it a follow-up
    turn is unanswerable — "how much is that one?" has no referent — and a
    multi-turn agent with no memory is worse than a single-turn one, because it
    invites the caller to rely on something that is not there.

    The medical/company pre-filter runs on the CURRENT utterance, which is the
    correct seam: history is only ever text this same guarded path already
    produced, so it cannot be used to smuggle a deflected question through.
    """
    kind = classify(speech)
    if kind == "medical":
        return MEDICAL_DEFLECT
    if kind == "info":
        return INFO_DEFLECT
    user = (speech or "").strip()[:400] or "How can you help me?"
    prior = _recent(history)
    if prior:
        user = (f"Earlier in this same phone call:\n{prior}\n\n"
                f"The caller now says: {user}")
    reply = llm.complete(
        system=_voice_system_prompt(site), user=user,
        purpose="voice_intake", site=site,
        stub=assistant.stub_answer(speech, site),
    )
    # Shorten BEFORE scanning, never after: the scan has to run on the exact
    # words that will be spoken, or it is verifying a draft nobody hears.
    reply = shorten_for_speech(reply)
    hard, _soft = guardrails.scan(reply)
    if hard or not reply:
        return SAFE_FALLBACK
    if "research" not in reply.lower():   # belt-and-suspenders disclaimer
        reply = reply.rstrip(". ") + ". " + DISCLAIMER
    return reply


def subject_line(speech, site):
    """Short subject line for the voicemail, from the caller's first question."""
    speech = (speech or "").strip()
    if not speech:
        return "Voicemail"
    stub = " ".join(speech.split()[:8])[:80]
    raw = llm.complete(
        system=("Summarize the caller's reason into a 3 to 6 word voicemail "
                "subject line for a research-compound store. No medical or dosing "
                "advice. Return only the subject text."),
        user=speech[:400], purpose="voice_subject", site=site, stub=stub,
    )
    subj = (raw or stub).strip().strip('"').splitlines()[0]
    return subj[:80] or "Voicemail"
