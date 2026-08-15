"""Hand-written editorial copy for each research category.

Every `/category/<slug>/` URL on the network used to render the site's own
homepage with a JavaScript filter chip preselected: identical `<title>`,
identical meta description, identical `<h1>`, identical body. Seven categories
across eight domains is fifty-six URLs, each one a duplicate of the homepage it
was supposed to support, all competing with it and with each other.

The fix is not a template trick. A category page earns its URL by saying
something the homepage does not, so the copy below is written per category:
what the class of compound is, what the research literature actually covers,
and what a lab should think about before ordering. It is deliberately in the
same register as `stores/regions.py` — specific, unhurried, and honest about
what this business does and does not hold.

Compliance: this copy is scanned by `apps.blog.guardrails` in the test suite.
No therapeutic claim, no purity figure, no testing or COA claim, no origin.
"""

CATEGORIES = {
    "metabolic": {
        "lede": "Compounds studied for their effects on energy balance, appetite "
                "signalling and lipid handling — the most active area of peptide "
                "research literature at the moment, and the one where the gap "
                "between a published finding and a marketing claim is widest.",
        "body": [
            "The incretin family sits at the centre of this category. GLP-1, GIP "
            "and glucagon receptor agonists are studied as single-, dual- and "
            "triple-receptor molecules, and the published work on each is at a "
            "different stage — some in large human trials, some still in rodent "
            "models, some barely characterised outside a handful of papers. A "
            "researcher choosing between them is usually choosing between "
            "literatures, not between products.",

            "Alongside those sit the mitochondrial and lipolytic compounds that "
            "get grouped here by convention rather than mechanism. They are "
            "studied for quite different reasons and it is worth reading what a "
            "given compound is actually being investigated for before assuming a "
            "shared pathway.",

            "We hold no analytical documentation for anything in this category. "
            "There is no certificate, no purity result and no identity "
            "confirmation, and the material should be treated as uncharacterised "
            "until your own analysis says otherwise. That matters more here than "
            "in most categories, because the compounds in it are the ones most "
            "often misrepresented elsewhere.",
        ],
        "considerations": [
            "Several compounds in this class are the subject of active patents and "
            "regulatory attention. Confirm the position that applies to your "
            "institution before ordering.",
            "Lyophilised material in this category is typically supplied in small "
            "masses where a weighing error is proportionally large — plan the "
            "reconstitution volume before the vial arrives.",
        ],
    },
    "mitochondrial": {
        "lede": "Peptides encoded in or acting on mitochondrial pathways — a small, "
                "young literature where most of what is published is still in cells "
                "and animal models.",
        "body": [
            "Mitochondrial-derived peptides were only described relatively "
            "recently, which shapes what is available to read about them: a "
            "modest number of papers, many from the same small group of labs, and "
            "very little replication. That is not a criticism of the field. It is "
            "the ordinary shape of an early literature, and it is the reason "
            "claims about this class should be read with the model and the sample "
            "size attached.",

            "Research in the category tends to concentrate on cellular energy "
            "metabolism and stress response signalling. Where a finding is "
            "reported, it is almost always in vitro or in a rodent model, and "
            "human relevance is generally unknown rather than established.",

            "As everywhere else in this catalogue, no analysis accompanies the "
            "material and none is claimed.",
        ],
        "considerations": [
            "Reported stability varies considerably across this class — check the "
            "handling notes in the literature for the specific compound rather "
            "than applying a general rule.",
            "Small published sample sizes make effect sizes in this field "
            "unusually unreliable; design around that.",
        ],
    },
    "repair-recovery": {
        "lede": "Compounds studied in tissue-repair, connective-tissue and "
                "gastrointestinal models — the category most heavily marketed on "
                "claims the published work does not support.",
        "body": [
            "This is where careful reading matters most. Several compounds here "
            "have a genuinely interesting preclinical literature — rodent tendon, "
            "ligament and gut models, mostly — and an online reputation that has "
            "run a very long way ahead of it. A study reporting accelerated repair "
            "in a rat model is a real result and is not a statement about people.",

            "Where those studies exist, they are worth reading directly rather "
            "than through a summary. Methods and models vary enough that two "
            "papers on the same compound can support quite different conclusions, "
            "and the differences usually live in the method section.",

            "We publish no purity figure and hold no certificate of analysis for "
            "any of it. If your work depends on confirmed identity, budget for "
            "your own characterisation.",
        ],
        "considerations": [
            "Compounds in this category are among the most frequently "
            "counterfeited in the wider market — a supplier's confidence is not "
            "evidence, including ours.",
            "Reconstituted material in this class is generally reported as less "
            "stable at room temperature than the lyophilised form.",
        ],
    },
    "growth-factors": {
        "lede": "Secretagogues, releasing peptides and growth-factor analogues "
                "studied for their signalling behaviour in endocrine research.",
        "body": [
            "The compounds grouped here act at different points of the same broad "
            "axis, which is why they are so often confused with one another. A "
            "releasing hormone analogue, a ghrelin-receptor secretagogue and a "
            "growth-factor analogue are three different things with three "
            "different literatures, and the shorthand names used to sell them "
            "tend to flatten that distinction.",

            "Published research in this area is comparatively mature — some of it "
            "dates back decades — which means it is possible to read the primary "
            "sources rather than relying on summaries. It also means the "
            "regulatory position on several of them is well established and worth "
            "checking against your own institution's rules.",

            "Nothing in this category is supplied with analytical documentation, "
            "and no purity is stated.",
        ],
        "considerations": [
            "Several compounds here are structurally similar enough that identity "
            "confirmation is genuinely worth doing before use.",
            "Reported solubility differs sharply across the group; do not carry a "
            "reconstitution protocol from one compound to another.",
        ],
    },
    "neuropeptides": {
        "lede": "Peptides studied for activity in neural and cognitive research "
                "models, including the short bioregulator peptides.",
        "body": [
            "This category spans two quite separate traditions. One is the "
            "Western literature on neuroactive peptides and their signalling; the "
            "other is the body of work on short bioregulator peptides published "
            "largely in Russian journals from the 1980s onward, much of which has "
            "never been replicated outside its original group and a good deal of "
            "which is difficult to obtain in translation.",

            "Both are legitimate things to research. They are not "
            "interchangeable, and a reader who does not know which tradition a "
            "given claim comes from will struggle to judge it. Where a compound "
            "here has a reputation, it is usually worth asking which literature "
            "the reputation came from.",

            "No certificate of analysis exists for this material and none is "
            "claimed.",
        ],
        "considerations": [
            "Translation quality is a real constraint on the bioregulator "
            "literature — secondary summaries in English are frequently "
            "unreliable.",
            "Peptides in this class are often supplied at very small masses where "
            "handling losses are proportionally significant.",
        ],
    },
    "melanocortin": {
        "lede": "Melanocortin-receptor peptides, a small and unusually "
                "well-characterised family with a correspondingly specific "
                "research literature.",
        "body": [
            "The melanocortin receptors are a defined set, and the peptides "
            "studied against them are usually described in the literature by "
            "which receptor subtypes they engage. That makes this one of the "
            "easier categories to read carefully: the papers tend to state the "
            "receptor selectivity plainly, and selectivity is what most of the "
            "differences between these compounds come down to.",

            "The regulatory history of this family is also unusually well "
            "documented, and worth reading before ordering — it is a category "
            "where the position varies meaningfully between jurisdictions.",

            "We hold no analysis for any of it and state no purity figure.",
        ],
        "considerations": [
            "Receptor selectivity, not potency, is usually the variable that "
            "matters when choosing between compounds in this family.",
            "Reported photosensitivity of some members of this class affects "
            "storage as well as handling.",
        ],
    },
    "supplies": {
        "lede": "The consumables a peptide bench actually runs on — diluents, "
                "vials and the small equipment that turns lyophilised powder into "
                "something a protocol can use.",
        "body": [
            "Nothing in this category is a research compound. It is the "
            "supporting material: bacteriostatic and sterile diluents, empty "
            "vials, and the handling consumables that a peptide protocol assumes "
            "you already have and that are irritating to source separately.",

            "Diluent choice is the decision worth thinking about here. "
            "Bacteriostatic and non-bacteriostatic water behave differently once "
            "a vial has been entered more than once, and the difference shows up "
            "in how long a reconstituted preparation stays usable rather than in "
            "anything you can see.",

            "These items are supplied as laboratory consumables. As with "
            "everything else here, no analytical documentation accompanies them.",
        ],
        "considerations": [
            "Match the diluent to how many times the vial will be entered, not to "
            "the compound.",
            "Order consumables with the compound rather than after it — the "
            "delivery window applies to both.",
        ],
    },
}

# Fallback for a category added later without copy. Deliberately short and
# obviously generic, so an uncopied category is visible rather than silently
# shipping filler that reads like the real thing.
FALLBACK = {
    "lede": "Research compounds in this category, supplied as laboratory "
            "reference materials.",
    "body": [
        "No analytical documentation accompanies this material and no purity "
        "figure is stated. Treat it as uncharacterised until your own analysis "
        "says otherwise.",
    ],
    "considerations": [],
}


def for_category(category):
    """Editorial copy for a Category, or the fallback."""
    return CATEGORIES.get(getattr(category, "slug", ""), FALLBACK)


def has_copy(category):
    return getattr(category, "slug", "") in CATEGORIES


# ---------------------------------------------------------------------------
# Per-site framing
# ---------------------------------------------------------------------------
#
# Seven categories of copy across eight domains still leaves fifty-six pages
# where the substance is identical and only the logo changes. That is the same
# duplicate-network problem the category split was meant to solve, moved one
# level out.
#
# These paragraphs are the answer: each domain reads its catalogue through the
# lane it already occupies editorially — the research-news desk frames a
# category by its literature, the handling site by the bench, the buyer-guide
# site by what a purchaser should ask. Same catalogue, genuinely different page,
# which is the honest version of what eight domains are supposed to be.
SITE_FRAMING = {
    "smashfatbiolabs.ca":
        "We track this category the way a news desk would: what was published, "
        "in what model, and what the authors themselves said the result does "
        "and does not show. Where a compound below has an interesting recent "
        "paper, it is written up in the research notes rather than compressed "
        "into a product bullet.",
    "smashfatbiolabs.com":
        "Our coverage of this category follows the primary literature — "
        "preclinical and clinical, attributed and hedged, with the model stated "
        "every time. If a finding here is exciting, the write-up will say "
        "plainly whether human relevance has been established.",
    "smashfat.ca":
        "This category is where our own reading concentrates. We are interested "
        "in mechanism and in what the research literature actually supports, "
        "which mostly means being careful about the distance between a receptor "
        "study and anything a person would experience.",
    "smash-fat.ca":
        "We look at this category from the bench outward: how the material "
        "arrives, what reconstitution it wants, how it should be stored and "
        "labelled, and what a lab notebook needs to record. The chemistry is "
        "interesting; the handling is what determines whether your result means "
        "anything.",
    "smash-fat.com":
        "This category is presented as reference data first — sequence, "
        "molecular weight, formula and solubility where they are established — "
        "on the assumption that a researcher arriving here already knows what "
        "they are looking for and wants the numbers without the sales copy.",
    "peptidesalberta.ca":
        "We serve Alberta labs, and this category tends to raise the same "
        "procurement questions each time: what documentation a purchasing "
        "office will ask for, what we can and cannot supply with it, and how "
        "the delivery window lands against a research schedule. Short answer on "
        "documentation — we hold none, and we say so before you order.",
    "where-do-i-get-peptides.ca":
        "If you are new to buying research compounds, this category is a good "
        "place to practise reading a supplier critically. Notice what is "
        "claimed and what is evidenced, here and everywhere else. We publish no "
        "purity figure and hold no certificate, and any supplier who publishes "
        "one should be able to show you the underlying analysis.",
    "where-do-i-get-peptides.com":
        "This category is a useful test case for vetting a vendor. The claims "
        "made about these compounds vary enormously between suppliers while the "
        "underlying material often does not, which tells you the claims are "
        "marketing rather than measurement. Ask for the analysis; note who can "
        "produce it.",
}

DEFAULT_FRAMING = (
    "Everything in this category is supplied as a laboratory reference "
    "material. No analytical documentation accompanies it and none is claimed."
)


def framing_for(site):
    """The per-domain paragraph that keeps eight category pages from being one."""
    return SITE_FRAMING.get(getattr(site, "domain", ""), DEFAULT_FRAMING)
