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
