"""
Compliance guardrails for research-compound content.

Goal: never accidentally publish a false or non-compliant claim. Research
peptides are research-use-only; marketing them with medical/therapeutic/dosing
or "guaranteed results" language is false-advertising and health-claim risk.

This scanner runs on every AI-generated (or edited) post. It:
  * blocks hard-prohibited claims (medical/efficacy/dosing/human-use/regulatory),
  * warns on softer risky phrasing,
  * ensures the research-use-only disclaimer is present (appends if missing).

Policy: a post is NEVER auto-published. Clean posts become `needs_review`
(compliance = pass); flagged posts become `needs_review` (compliance = flagged)
with the issues listed for a human to fix. Only a human approve → published.
"""
import re

DISCLAIMER = ("For research use only. Not for human or veterinary use. This content is "
              "informational and describes laboratory research — it is not medical advice, "
              "and makes no therapeutic, diagnostic, or health claims.")

# Hard-prohibited: presence flags the post for mandatory human fix. Word-boundary,
# case-insensitive. Kept conservative and research-context aware.
HARD_PATTERNS = {
    # "treated" is excluded deliberately: "cells treated with the compound" is
    # ordinary in-vitro description, and flagging it fired on essentially every
    # legitimate post — a scanner that flags everything is one a reviewer stops
    # reading. "treats", "treatment for" and the rest still trip.
    "medical/therapeutic claim": r"\b(cure[sd]?|treats\b|treatment for|heal(s|ed|ing)?|"
                                 r"prevent(s|ed|ion)?|diagnos(e|es|is|ing)|remed(y|ies)|"
                                 r"therapy for|reverses?)\b",
    "efficacy / guarantee": r"\b(clinically proven|proven to|guarantee[ds]?|guaranteed results|"
                            r"miracle|100% effective|risk[- ]free|no side effects)\b",
    "human use / dosing": r"\b(for human use|human consumption|safe for humans|take (this|it|daily)|"
                          r"dosage|recommended dose|how (much|to) (take|use|inject|dose)|"
                          r"\d+\s?mg (per|a) (day|week)|twice daily|once daily)\b",
    "weight-loss / body promise": r"\b(lose \d+|lose weight|melt(s|ed)? (fat|away)|burn(s|ed)? fat|"
                                  r"shed pounds|drop pounds|get ripped|guaranteed weight loss)\b",
    "regulatory claim": r"\b(fda[- ]approved|health canada[- ]approved|approved for (use|treatment)|"
                        r"gras|prescription)\b",
    "personal testimonial of outcome": r"\b(i lost|my results|changed my life|worked for me|cured my)\b",

    # --- claims about the business itself, not the compound ------------------
    # These are the ones a compliant-sounding model produces most readily,
    # because they read like helpful reassurance rather than like a claim.
    #
    # Origin: the network makes no representation about where goods ship from,
    # in either direction. A model told the audience is Canadian will reach for
    # "ships from Canada" unprompted — that is a false origin representation
    # under the Competition Act (and the FTC Act on the .com side), and naming
    # any other country is equally off the table. Silence is the position.
    "shipping origin claim": r"\b(ship(s|ped|ping)?|dispatch(ed|es)?|sent|stock(ed)?|warehouse[sd]?|"
                             r"made|manufactur(ed|ing)|produc(ed|tion)|sourced|based)\s+"
                             r"(directly\s+)?(from|in|out of)\s+(the\s+)?"
                             r"(canada|canadian|alberta|calgary|edmonton|ontario|toronto|vancouver|bc|"
                             r"china|chinese|usa|u\.s\.|united states|america[n]?|europe|india)\b",
    "domestic-stock claim": r"\b(domestic(ally)?\s+(stock|ship|warehous|source)|"
                            r"canadian[- ]made|made in canada|local(ly)? stocked|in[- ]country stock)\b",

    # Superlatives and price claims are unverifiable comparative advertising.
    "unverifiable superlative": r"\b(cheapest|lowest price[sd]?|best price[sd]?|highest quality|"
                                r"purest|the best|number one|#1|market leader|industry leading|"
                                r"fastest shipping|unbeatable)\b",

    # Credentials the business does not hold. Inventing an accreditation is the
    # most damaging thing a generated post can do, and the easiest to miss on
    # a skim because it reads like boilerplate.
    "unheld certification": r"\b(gmp[- ]certified|iso[- ]?\d{4,5}[- ]?(certified|accredited)|"
                            r"usp[- ]grade|pharmaceutical[- ]grade|cgmp|fda[- ]registered|"
                            r"health canada licen[cs]ed|licen[cs]ed facility)\b",

    # The delivery promise is 10–15 days everywhere. Any other window in a post
    # is a promise the fulfilment chain has not agreed to.
    "off-policy delivery promise": r"\b((?!10\s*[-–]\s*15)\d{1,2}\s*[-–]\s*\d{1,2}\s*(business\s+)?days?\s+"
                                   r"(delivery|shipping|to arrive)|"
                                   r"(next|same)[- ]day (delivery|shipping)|overnight (delivery|shipping)|"
                                   r"free (express|expedited) shipping)\b",
}

# Soft-risky: allowed but surfaced so the reviewer double-checks framing.
SOFT_PATTERNS = {
    "benefit framing": r"\b(benefit[s]?|improve[sd]?|boost[s]?|enhance[sd]?|optimi[sz]e[sd]?)\b",
    "outcome words": r"\b(results?|effective|powerful|potent)\b",
    "audience-directed 'you'": r"\byou(r)?\b",
}


def scan(text):
    """Return (hard_issues, soft_issues) — lists of (label, matched_snippet)."""
    hard, soft = [], []
    for label, pat in HARD_PATTERNS.items():
        for m in re.finditer(pat, text, re.I):
            hard.append((label, m.group(0)))
    for label, pat in SOFT_PATTERNS.items():
        hits = len(re.findall(pat, text, re.I))
        if hits:
            soft.append((label, f"{hits}×"))
    return hard, soft


def ensure_disclaimer(text):
    """Guarantee the research-use-only disclaimer is present."""
    key = "research use only"
    if key not in text.lower():
        return text.rstrip() + "\n\n---\n\n_" + DISCLAIMER + "_\n"
    return text


def review(text):
    """Full compliance pass. Returns a dict the caller stores on the post."""
    text = ensure_disclaimer(text)
    hard, soft = scan(text)
    status = "flagged" if hard else "pass"
    notes = []
    for label, snip in hard:
        notes.append(f"❌ {label}: “{snip}”")
    for label, snip in soft:
        notes.append(f"⚠️ {label} ({snip}) — check framing")
    return {
        "text": text,
        "status": status,               # pass | flagged
        "notes": "\n".join(notes),
        "hard_count": len(hard),
        "soft_count": len(soft),
    }
