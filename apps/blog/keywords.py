"""
Per-domain SEO keyword sets.

Two rules run this file:

1. **Market split.** `.ca` domains target the Canadian research market; `.com`
   domains target the United States. Before this split every domain — including
   the .coms — chased "…Canada" terms, which meant the US storefronts were
   optimised for a country they don't serve.

2. **No two sites share an angle.** All eight domains serve one catalogue, so
   the blogs are the main thing keeping them from reading as duplicates. Each
   site gets its own lane: purity/testing, metabolic, handling, library,
   regional, buyer education, verification.

The daily generator rotates through a site's list.
"""

# Fallbacks by market, used for any domain not listed below.
DEFAULT_CA = [
    "research peptides Canada",
    "buy research peptides Canada",
    "Canadian peptide supplier",
    "peptide research news Canada",
    "peptide research studies",
    "research compounds Canada",
]

DEFAULT_US = [
    "research peptides USA",
    "buy research peptides online USA",
    "US research peptide supplier",
    "peptide research news",
    "new peptide research findings",
    "research compounds for laboratory use",
]

DEFAULT = DEFAULT_CA  # back-compat for callers that predate the split

BY_DOMAIN = {
    # ---------------- Canada (.ca) ----------------
    "smashfatbiolabs.ca": [
        "peptide research news", "BPC-157 research studies",
        "TB-500 preclinical research", "GLP-1 peptide research findings",
        "new peptide research 2026", "peptide science news Canada",
        "peptide research review Canada",
    ],
    "smashfat.ca": [
        "metabolic research peptides Canada", "GLP-1 research compounds Canada",
        "retatrutide research Canada", "tesamorelin research Canada",
        "MOTS-C research Canada", "GIP GLP-1 glucagon research compound",
    ],
    "smash-fat.ca": [
        "compounding grade research peptides", "lyophilized research peptides Canada",
        "reconstitution research peptides", "research peptide storage Canada",
        "bacteriostatic water Canada research",
    ],
    "peptidesalberta.ca": [
        "peptides Alberta", "research peptides Calgary", "research peptides Edmonton",
        "buy research peptides Alberta", "Alberta peptide supplier",
        "research peptides Red Deer", "research peptides Lethbridge",
    ],
    "where-do-i-get-peptides.ca": [
        "where to buy research peptides Canada", "how to choose a peptide supplier",
        "research peptide buying guide Canada", "research peptide red flags",
        "questions to ask a peptide supplier",
    ],

    # ---------------- United States (.com) ----------------
    "smashfatbiolabs.com": [
        "peptide research news USA", "peptide clinical trial results",
        "BPC-157 animal study findings", "retatrutide trial research news",
        "peptide research breakthroughs", "new peptide studies 2026",
    ],
    "smash-fat.com": [
        "research peptide library", "documented research peptides",
        "batch tested research compounds", "research peptide reference data",
        "peptide molecular weight reference",
    ],
    "where-do-i-get-peptides.com": [
        "where to buy research peptides", "trusted research peptide source",
        "research peptide supplier checklist", "research peptide scam warning signs",
        "how to vet a peptide vendor", "research peptide supplier comparison",
    ],
}

# Which market each domain serves. Used by the generator to pick a fallback and
# to keep US posts from picking up Canadian framing.
MARKET_BY_DOMAIN = {
    "smashfatbiolabs.ca": "CA",
    "smashfat.ca": "CA",
    "smash-fat.ca": "CA",
    "peptidesalberta.ca": "CA",
    "where-do-i-get-peptides.ca": "CA",
    "smashfatbiolabs.com": "US",
    "smash-fat.com": "US",
    "where-do-i-get-peptides.com": "US",
}


# One editorial lane per domain.
#
# The keyword lists above already stop the eight sites from bidding on the same
# terms, but keywords alone don't stop the prose converging: given the same
# catalogue and the same compliance rules, a model writes eight near-identical
# posts. These angles are what actually differentiate the bodies — they change
# what a post is *about*, not just which phrase it repeats. Duplicate-content
# filtering across a network of related domains is the risk being managed here,
# and it is the whole reason the network runs eight sites instead of one.
ANGLE_BY_DOMAIN = {
    "smashfatbiolabs.ca":
        "Research news desk. Report what published, peer-reviewed studies of a "
        "compound actually found — model, methods, result — with every finding "
        "attributed and hedged, and a standing not-medical-advice / do-your-own-"
        "research note. Science journalism register, never promotion.",
    "smashfat.ca":
        "Metabolic research context. Explain what class of compound is being studied "
        "and why, at the level of mechanism and research literature. Never touch "
        "outcomes in people.",
    "smash-fat.ca":
        "Laboratory handling. Lyophilised material, reconstitution practice, storage "
        "and cold chain, stability, labelling and chain of custody. Practical bench "
        "procedure, not product promotion.",
    "peptidesalberta.ca":
        "Regional and practical, written for Alberta institutions — university and "
        "private labs, procurement processes, documentation a purchasing office asks "
        "for. Plain, local, unhurried.",
    "where-do-i-get-peptides.ca":
        "Buyer education. How a non-specialist evaluates a supplier: what documentation "
        "to demand, which claims are meaningless, what a certificate of analysis proves "
        "and what it does not. Guide voice, genuinely useful even to someone who buys "
        "elsewhere.",
    "smashfatbiolabs.com":
        "US research news desk. Summarize new preclinical and clinical literature on "
        "research compounds — what was studied, in what model, what was reported — "
        "attributed, hedged, with a not-medical-advice / do-your-own-research note. "
        "Reads like a lab newsletter, not a store.",
    "smash-fat.com":
        "Reference library. Structural and physicochemical data — sequence, molecular "
        "weight, formula, solubility — presented as a factual entry a researcher cites. "
        "Encyclopaedic, near-neutral in tone.",
    "where-do-i-get-peptides.com":
        "Verification and vetting for the US market. How to check a supplier's claims "
        "independently, comparison frameworks, red flags. Investigative, sceptical, "
        "willing to say when a common industry claim is unverifiable.",
}


def angle_for(site):
    """The editorial lane for a domain, or '' when it has none."""
    return ANGLE_BY_DOMAIN.get(getattr(site, "domain", ""), "")


def market_for(site):
    """'CA' or 'US'. Prefers the Site row, falls back to the TLD."""
    country = getattr(site, "country", "") or ""
    if country in ("CA", "US"):
        return country
    domain = getattr(site, "domain", "") or ""
    if domain in MARKET_BY_DOMAIN:
        return MARKET_BY_DOMAIN[domain]
    return "US" if domain.endswith(".com") else "CA"


def for_site(site):
    domain = getattr(site, "domain", "")
    if domain in BY_DOMAIN:
        return BY_DOMAIN[domain]
    return DEFAULT_US if market_for(site) == "US" else DEFAULT_CA
