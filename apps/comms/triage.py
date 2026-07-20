"""AI voicemail triage — classify intent tier + urgency from the transcript.
Mirrors AR-Sales Voicemail triage. Uses apps.ai.llm (grounded, ledgered);
falls back to a keyword heuristic when the AI isn't live."""
import json

from apps.ai import llm

SYSTEM = (
    "You triage voicemails for a Canadian RESEARCH-COMPOUND (peptide) store. "
    "Classify the caller's intent and urgency. NEVER give medical or dosing advice. "
    "Return ONLY compact JSON: "
    '{"tier": "<order|quote|order-status|coa-request|support|complaint|spam|other>", '
    '"urgency": "<low|normal|high|urgent>", '
    '"confidence": <0-1 float>, "rationale": "<one short sentence>"}.'
)
_URGENT = ("urgent", "asap", "immediately", "right away", "emergency", "wrong order", "not received")
_HIGH = ("order", "buy", "purchase", "where is", "refund", "complaint", "problem", "issue")


def _heuristic(text):
    t = (text or "").lower()
    if not t.strip():
        return {"tier": "other", "urgency": "normal", "confidence": 0.2,
                "rationale": "No transcript available."}
    urgency = "urgent" if any(w in t for w in _URGENT) else (
        "high" if any(w in t for w in _HIGH) else "normal")
    tier = ("complaint" if ("complaint" in t or "refund" in t) else
            "order-status" if ("where is" in t or "status" in t) else
            "order" if ("order" in t or "buy" in t or "purchase" in t) else
            "coa-request" if ("coa" in t or "certificate" in t) else
            "support" if ("help" in t or "question" in t) else "other")
    return {"tier": tier, "urgency": urgency, "confidence": 0.4,
            "rationale": "Keyword-based classification (AI offline)."}


def classify_voicemail(vm):
    text = (vm.transcript or "").strip()
    stub = _heuristic(text)
    raw = llm.complete(
        system=SYSTEM,
        user=f"Voicemail transcript:\n{text or '(empty)'}",
        purpose="voicemail_triage", site=vm.site, stub=json.dumps(stub),
    )
    data = stub
    try:
        data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
    except Exception:
        data = stub
    vm.tier = str(data.get("tier", ""))[:40]
    urgency = data.get("urgency", "normal")
    vm.urgency = urgency if urgency in dict(vm.URGENCY) else "normal"
    vm.tier_rationale = str(data.get("rationale", ""))[:300]
    try:
        vm.tier_confidence = float(data.get("confidence"))
    except (TypeError, ValueError):
        vm.tier_confidence = None
    vm.save(update_fields=["tier", "urgency", "tier_rationale", "tier_confidence"])
    return vm
