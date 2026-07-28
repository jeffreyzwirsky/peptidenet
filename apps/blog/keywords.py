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
    "third-party tested peptides Canada",
    "peptide COA Canada",
    "research compounds Canada",
]

DEFAULT_US = [
    "research peptides USA",
    "buy research peptides online USA",
    "US research peptide supplier",
    "third-party tested research peptides",
    "peptide certificate of analysis",
    "research compounds for laboratory use",
]

DEFAULT = DEFAULT_CA  # back-compat for callers that predate the split

BY_DOMAIN = {
    # ---------------- Canada (.ca) ----------------
    "smashfatbiolabs.ca": [
        "research peptides Canada", "high purity peptides Canada",
        "HPLC tested peptides Canada", "buy BPC-157 Canada research",
        "TB-500 research Canada", "peptide COA Canada",
        "lab verified peptides Canada",
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
        "how to read a peptide COA", "research peptide buying guide Canada",
        "what is a certificate of analysis peptide",
    ],

    # ---------------- United States (.com) ----------------
    "smashfatbiolabs.com": [
        "reference grade research peptides", "certified research peptides USA",
        "research peptide supplier United States", "mass-spec verified peptides",
        "HPLC purity testing peptides", "research peptides shipped to USA",
    ],
    "smash-fat.com": [
        "research peptide library", "documented research peptides",
        "batch tested research compounds", "research peptide reference data",
        "peptide molecular weight reference",
    ],
    "where-do-i-get-peptides.com": [
        "where to buy research peptides", "trusted research peptide source",
        "research peptide supplier checklist", "how to verify peptide purity",
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
        "Analytical rigour. Lead with methodology — how HPLC and mass spectrometry "
        "establish identity and purity, what a release threshold means, how to read "
        "a chromatogram. Technical register, for a reader with bench experience.",
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
        "Reference-grade documentation for US laboratories. Specification, traceability, "
        "batch records, what 'reference grade' means and what it doesn't.",
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
