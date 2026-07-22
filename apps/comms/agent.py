"""Turn-based AI phone intake — a SHORT, guarded conversation that answers basic
catalogue questions (the same brain as the website chat) and builds a voicemail
subject line, then records the message. Compliance is enforced in layers:

  1. Pre-filter on the CALLER's words: anything about use/dosing/health, or about
     the company/address/staff/internal info, gets a fixed safe deflection and
     NEVER reaches the LLM.
  2. The LLM answer is grounded ONLY in the product catalogue (reuses the site
     chat assistant); every product answer keeps a research-use-only framing.
  3. A guardrail scan runs on the generated answer; if it trips a prohibited
     pattern it is replaced with a safe fallback instead of being spoken.
  4. The full call is always recorded + transcribed as an audit-trail fallback.

All of this is easy to loosen later (edit the deflect lists / system prompt).
"""
import re

from apps.ai import assistant, llm
from apps.blog import guardrails

DISCLAIMER = ("All products are for laboratory research use only, and not for "
              "human or veterinary consumption.")

MEDICAL_DEFLECT = (
    "I'm sorry, I can't advise on use, dosing, or anything medical — please "
    "consult a qualified professional. I can help with product availability, "
    "pricing, purity, certificates of analysis, shipping, and placing an order.")

INFO_DEFLECT = (
    "I'm not able to share company details right now. I can help with product "
    "availability, pricing, purity, certificates of analysis, shipping, and "
    "placing an order.")

SAFE_FALLBACK = (
    "I can help with product details, availability, purity, certificates of "
    "analysis, shipping, and orders. For anything about use or dosing, please "
    "consult a qualified professional. " + DISCLAIMER)

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
        "\nYOU ARE ON A PHONE CALL. Keep replies to 1-2 short sentences. "
        "Only discuss the product catalogue, purity, certificates of analysis, "
        "shipping timeframes, and how to order on the website. NEVER give use, "
        "dosing, medical, or health advice. NEVER share the company address, "
        "location, where it ships from, staff names, ownership, hours, or any "
        "internal or contact info — say you cannot share that. Always keep a "
        "research-use-only framing and end product answers with a brief "
        "research-use-only note.")


def answer(speech, site):
    """Return a fully-guarded spoken reply for the caller's question."""
    kind = classify(speech)
    if kind == "medical":
        return MEDICAL_DEFLECT
    if kind == "info":
        return INFO_DEFLECT
    reply = llm.complete(
        system=_voice_system_prompt(site),
        user=(speech or "").strip()[:400] or "How can you help me?",
        purpose="voice_intake", site=site,
        stub=assistant.stub_answer(speech, site),
    )
    reply = (reply or "").strip()
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
