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
              "and makes no therapeutic, diagnostic, or health claims. Research summaries "
              "report published findings as-is: always do your own research and consult "
              "the primary literature.")

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

    # Analytical claims. We hold no certificate of analysis, no purity result and
    # no identity confirmation for anything in the catalogue. Every one of these
    # phrases was live across all eight storefronts until it turned out none of
    # it could be evidenced. Competition Act s.74.01(1)(b) requires adequate and
    # proper testing BEFORE a performance claim is made, and the burden sits with
    # the advertiser — so the scanner treats any of them as hard failures.
    #
    # Explaining what a COA or an HPLC test IS remains fine: the negation and
    # quoted-example escapes in scan() cover genuine buyer education.
    "unsupported testing claim": r"\b((third[- ]party|independent(ly)?|lab)\s+"
                                r"(tested|verified|analy[sz]ed|screened)|"
                                r"hplc[- /]?(ms|verified|tested)?|mass[- ]spec(trometry)?|"
                                r"chromatograph(y|ic)|batch[- ]tested|lot[- ]tested|"
                                r"purity[- ](tested|verified|threshold)|release purity)\b",
    "unsupported COA claim": r"\b(coa[s]?\b|certificate[s]? of analysis|"
                             r"batch[- ](specific|matched) certificate|lot file)\b",
    "unsupported purity figure": r"(≥\s*9[0-9](\.[0-9])?\s*%|"
                                 r"\b9[0-9](\.[0-9])?\s*%\s*(pure|purity)|"
                                 r"\b(high|reference|analytical)[- ]?(purity|grade)\b)",

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


# Negation cues that turn a prohibited phrase into the disclaimer we require.
#
# Without this, the scanner flagged its own compliance language: the mandated
# "not approved for human consumption" and "not intended to diagnose, treat,
# cure, or prevent any disease" tripped the human-use and medical-claim rules
# on every single post. Eight of eight flagged is the same as none flagged —
# a reviewer facing an all-red queue stops reading it, and that is exactly how
# a real violation gets waved through.
_NEGATION = re.compile(
    r"\b(not|never|no|cannot|can't|nor|without|neither|"
    r"prohibited|forbidden|unlawful|illegal|"
    # Advisory cues. The buyer-education sites exist to tell a reader what to
    # steer clear of — "avoid suppliers who promise next-day delivery" is the
    # warning, not the promise.
    r"avoid|beware|steer clear of|walk away from|unsubstantiated)\b", re.I,
)

# Quoted spans. A claim inside quotation marks is being *reported*, not made.
#
# The vetting guides quote the exact red flags they teach readers to spot —
# "cheapest research peptides", "clinically proven", "pharmaceutical grade".
# Scanning those as if the site were asserting them turns the most valuable
# editorial content on the network into the most heavily flagged.
_QUOTED = re.compile(r"\"[^\"\n]{0,300}\"|“[^”\n]{0,300}”")


def _in_quotes(text, start, end):
    """True when the match sits wholly inside a quoted span on its own line."""
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    line_end = len(text) if line_end == -1 else line_end
    line = text[line_start:line_end]
    a, b = start - line_start, end - line_start
    return any(m.start() <= a and b <= m.end() for m in _QUOTED.finditer(line))
# How far back to look for the negation. Long enough to span "They are not
# intended for human consumption, veterinary use, medical diagnosis, treatment
# …" where the cue sits well ahead of the match, short enough not to reach
# into a previous sentence.
_LOOKBACK = 140


def _is_negated(text, start):
    """True when the match at `start` sits inside a negated clause.

    Sentence boundaries end the scope: a full stop between the cue and the
    match means the negation belonged to a different sentence and the match
    stands on its own.
    """
    window = text[max(0, start - _LOOKBACK):start]
    cue = None
    for m in _NEGATION.finditer(window):
        cue = m.end()
    if cue is None:
        return False
    return not re.search(r"[.!?]\s", window[cue:])


# Research-news attribution. A finding that is *reported* — pinned to a study,
# a trial, an animal model, the literature — is science journalism, not a claim
# by this business. "A 2023 rodent study reported accelerated tendon repair"
# must be writable; "BPC-157 heals tendons" must not. Only the labels below get
# this escape: dosing/human-use, regulatory, origin, certification, testing/COA,
# superlative and delivery claims stay hard no matter how they are attributed,
# because attribution does not make them lawful for the advertiser.
_ATTRIBUTION = re.compile(
    r"\b(stud(?:y|ies)|trials?|researchers?|scientists?|investigators?|"
    r"paper|publication|preprint|meta[- ]analys[ie]s|systematic review|"
    r"literature|according to|reported(?:ly)?|was (?:reported|observed|shown)|"
    r"findings?|in (?:mice|rats|rodents|cell(?:s| lines?)?|vitro|vivo)|"
    r"animal (?:model|study|studies)|rodent|preclinical|clinical trial)\b", re.I)

REPORTABLE = {"medical/therapeutic claim", "weight-loss / body promise"}


def _is_attributed(text, start, end):
    """True when the match's own sentence carries a research-attribution cue."""
    s = max(text.rfind(".", 0, start), text.rfind("!", 0, start),
            text.rfind("?", 0, start), text.rfind("\n", 0, start)) + 1
    e_candidates = [i for i in (text.find(".", end), text.find("!", end),
                                text.find("?", end), text.find("\n", end)) if i != -1]
    e = min(e_candidates) if e_candidates else len(text)
    return bool(_ATTRIBUTION.search(text[s:e]))


def scan(text):
    """Return (hard_issues, soft_issues) — lists of (label, matched_snippet)."""
    hard, soft = [], []
    for label, pat in HARD_PATTERNS.items():
        for m in re.finditer(pat, text, re.I):
            # Origin claims are checked WITHOUT the negation escape. "We don't
            # ship from China" still puts a country on the page next to this
            # business, and the standing rule is silence on origin, not denial.
            if label == "shipping origin claim":
                # No escapes for origin. Denying an origin, or quoting someone
                # else's, still puts a country on the page beside this business.
                hard.append((label, m.group(0)))
                continue
            if _is_negated(text, m.start()):
                continue
            if _in_quotes(text, m.start(), m.end()):
                # Surfaced, not blocking — the reviewer still sees it, but the
                # post is not painted red for teaching a reader what to avoid.
                soft.append((f"quoted example — {label}", m.group(0)))
                continue
            if label in REPORTABLE and _is_attributed(text, m.start(), m.end()):
                # Reported research finding — surfaced for the reviewer, not
                # blocking. The disclaimer's do-your-own-research note is the
                # standing companion to every such summary.
                soft.append((f"reported research finding — {label}", m.group(0)))
                continue
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
