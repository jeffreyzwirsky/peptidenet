"""Per-domain SEO keyword sets — Canadian research-peptide market. Each site
targets a different angle so the blogs don't compete/duplicate. The daily
generator rotates through a site's list."""

DEFAULT = [
    "research peptides Canada",
    "buy research peptides Canada",
    "Canadian peptide supplier",
    "third-party tested peptides Canada",
    "peptide COA Canada",
    "research compounds Canada shipping",
]

BY_DOMAIN = {
    "smashfatbiolabs.ca": [
        "research peptides Canada", "high purity peptides Canada",
        "HPLC tested peptides Canada", "buy BPC-157 Canada research",
        "TB-500 research Canada", "peptide COA Canada",
    ],
    "smashfatbiolabs.com": [
        "reference grade research peptides", "certified research peptides",
        "research peptide supplier North America", "mass-spec verified peptides",
    ],
    "smashfat.ca": [
        "metabolic research peptides Canada", "GLP-1 research compounds Canada",
        "retatrutide research Canada", "tesamorelin research Canada",
        "MOTS-C research Canada",
    ],
    "smash-fat.ca": [
        "compounding grade research peptides", "lyophilized research peptides Canada",
        "reconstitution research peptides", "research peptide storage Canada",
    ],
    "smash-fat.com": [
        "research peptide library", "documented research peptides",
        "batch tested research compounds",
    ],
    "peptidesalberta.ca": [
        "peptides Alberta", "research peptides Calgary", "research peptides Edmonton",
        "buy research peptides Alberta", "Alberta peptide supplier",
        "same day peptide shipping Alberta",
    ],
    "where-do-i-get-peptides.ca": [
        "where to buy research peptides Canada", "how to choose a peptide supplier",
        "how to read a peptide COA", "research peptide buying guide Canada",
    ],
    "where-do-i-get-peptides.com": [
        "where to buy research peptides", "trusted research peptide source",
        "research peptide supplier checklist", "how to verify peptide purity",
    ],
}


def for_site(site):
    return BY_DOMAIN.get(getattr(site, "domain", ""), DEFAULT)
