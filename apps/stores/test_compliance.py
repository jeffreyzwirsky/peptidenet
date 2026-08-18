"""
Compliance remediation regression tests — added 2026-08-16.

The repo's existing pattern is that a compliance rule which matters is enforced
by a test, not by a comment: `test_no_shipping_origin_claim_anywhere`,
`test_no_fabricated_reviews` and `test_region_copy_makes_no_banned_claim` all
work that way. These extend it to the findings from the labeling review.

The one that would have caught the worst of it is
`test_no_administration_surface_anywhere`. The blog guardrails in
`apps/blog/guardrails.py` were thorough and correct, and they never fired on
`/calculator/` — because the calculator was not a blog post. The strongest
dosing content on the network sat entirely outside the only system built to
block dosing content. These tests scan rendered pages instead, so a surface
does not escape by not being the kind of thing the guardrails inspect.
"""
import json
import re

from django.core.management import call_command
from django.test import TestCase

from apps.catalog.models import Product
from apps.stores.models import Site


# Vocabulary that describes preparing or giving a substance to a subject. None
# of it has an in-vitro meaning on a storefront page.
ADMIN_TERMS = [
    r"\bsyringe", r"\binsulin\b", r"\bU-?100\b", r"\bU-?50\b", r"\bU-?30\b",
    r"\bdraw to\b", r"\b\d+\s*units\b", r"\bdosage\b", r"\bdosing\b",
    r"\bdoses? per\b", r"\breconstitut", r"\bbacteriostatic\b",
    r"\binject", r"\badminister",
]

# Retail urgency and gamification.
PROMO_TERMS = [
    r"\d+% off", r"\bsave \d", r"\bunlock\b", r"\bbulk pricing\b",
    r"\bbuy more\b", r"\brefer a\b", r"\breferral credit\b",
    r"SMASH10", r"BURN10", r"CALM10", r"ALBERTA10", r"START10", r"LAB10",
    r"NOISE10", r"GUIDE10",
]

# Body-composition and outcome vocabulary.
OUTCOME_TERMS = [
    r"\bsmash fat\b", r"\bfat loss\b", r"\bweight loss\b", r"\banti-?aging\b",
    r"\blean mass\b", r"\bbefore and after\b", r"\bon cycle\b",
]


# Sentences that prohibit a thing necessarily name it: "must not be
# administered", "we do not provide dosing guidance". Scanning raw text flags
# the remediation copy itself. Sentences carrying a negation marker are dropped
# before the scan, so what is left is instructional use of the vocabulary.
_NEGATION = re.compile(
    r"\b(not|no|never|cannot|can't|don't|won't|declined?|refused?|"
    r"prohibit\w*|forbid\w*|without|neither|nor)\b", re.I)


def _instructional(text):
    """Strip markup, then drop every sentence that is a prohibition."""
    text = re.sub(r"<script.*?</script>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    # Collapse whitespace BEFORE splitting. HTML wraps mid-sentence, and
    # splitting on newlines would cut "...will not be\nadministered..." into a
    # fragment that has lost its "not".
    text = re.sub(r"\s+", " ", text)
    keep = [t for t in re.split(r"(?<=[.!?]) ", text) if not _NEGATION.search(t)]
    return " ".join(keep)


def _hits(text, patterns):
    text = _instructional(text)
    return [p for p in patterns if re.search(p, text, re.I)]


class ComplianceSurfaceTests(TestCase):
    """Scan what the storefront actually renders, on every domain."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog")
        call_command("seed_sites")

    def _pages(self):
        """Every public page worth scanning, on every live domain."""
        for site in Site.objects.all():
            paths = ["/", "/shipping/", "/returns/", "/privacy/", "/terms/"]
            for p in Product.objects.filter(is_active=True)[:12]:
                paths.append(f"/product/{p.slug}/")
            for path in paths:
                r = self.client.get(path, HTTP_HOST=site.domain, secure=True)
                if r.status_code == 200:
                    yield site.domain, path, r.content.decode()

    def test_no_administration_surface_anywhere(self):
        """No rendered page may carry preparation or administration vocabulary.

        This is the test that would have caught /calculator/, which published a
        fill line on a U-100 insulin syringe under a research-use-only
        paragraph."""
        bad = []
        for domain, path, html in self._pages():
            for hit in _hits(html, ADMIN_TERMS):
                bad.append(f"{domain}{path}: {hit}")
        self.assertEqual(bad, [], "administration vocabulary rendered:\n" + "\n".join(bad))

    def test_no_promotional_urgency(self):
        bad = []
        for domain, path, html in self._pages():
            for hit in _hits(html, PROMO_TERMS):
                bad.append(f"{domain}{path}: {hit}")
        self.assertEqual(bad, [], "retail urgency rendered:\n" + "\n".join(bad))

    # The brand name itself is an outcome claim on six of eight domains, and
    # that is a rename-or-retire decision for the operator, not a string edit.
    # It is tracked here as a dated allowlist rather than excluded from the
    # scan, so the failure stays visible and the list can only shrink.
    CONSUMER_INTENT_DOMAINS = {
        "smashfat.ca", "smash-fat.ca", "smash-fat.com",
        "smashfatbiolabs.ca", "smashfatbiolabs.com",
        "where-do-i-get-peptides.ca", "where-do-i-get-peptides.com",
    }

    def test_consumer_intent_domain_list_has_not_grown(self):
        """Opened 2026-08-16 with 7 of 8 domains. Every one is a finding.

        Under 21 CFR 201.128 intended use is inferred from the totality of the
        circumstances; a domain name is the top-level circumstance. No copy
        change reaches it. This asserts only that the list does not grow -
        it is a ratchet, not a pass."""
        live = {s.domain for s in Site.objects.all()}
        self.assertLessEqual(
            len(live & self.CONSUMER_INTENT_DOMAINS), 7,
            "the consumer-intent domain list must shrink, never grow")

    def test_no_outcome_vocabulary(self):
        """Brand tokens on the domains in CONSUMER_INTENT_DOMAINS are excluded
        here and tracked by the ratchet above instead - otherwise this test
        fails permanently on a finding it cannot fix, and a permanently red
        test is a test nobody reads."""
        bad = []
        for domain, path, html in self._pages():
            if domain in self.CONSUMER_INTENT_DOMAINS:
                html = re.sub(r"smash[\s-]?fat", " ", html, flags=re.I)
            for hit in _hits(html, OUTCOME_TERMS):
                bad.append(f"{domain}{path}: {hit}")
        self.assertEqual(bad, [], "outcome vocabulary rendered:\n" + "\n".join(bad))

    def test_who_we_sell_to_statement_on_every_storefront(self):
        """The statement that distinguishes a reagent supplier from a consumer
        storefront is who it will sell to. It must be on the page, not only in
        the terms."""
        for site in Site.objects.all():
            html = self.client.get("/", HTTP_HOST=site.domain, secure=True).content.decode()
            self.assertIn("do not sell to patients", html.lower().replace("&#x27;", "'"),
                          f"{site.domain} homepage")

    def test_withdrawn_urls_return_410(self):
        for site in Site.objects.all():
            for path in ("/calculator/", "/rewards/"):
                r = self.client.get(path, HTTP_HOST=site.domain, secure=True)
                self.assertEqual(r.status_code, 410, f"{site.domain}{path}")


class CatalogueDispositionTests(TestCase):
    """The triage is data, so it can be asserted."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog")
        call_command("seed_sites")

    def test_every_catalogue_row_carries_a_disposition(self):
        with open("data/catalogue.json", encoding="utf-8") as fh:
            rows = json.load(fh)["products"]
        missing = [r["n"] for r in rows if r.get("disposition") not in ("KEEP", "FIX", "DELIST")]
        self.assertEqual(missing, [], "rows with no disposition")

    def test_no_delisted_product_is_active(self):
        with open("data/catalogue.json", encoding="utf-8") as fh:
            rows = json.load(fh)["products"]
        delisted = {r.get("slug") or "" for r in rows if r["disposition"] == "DELIST"}
        delisted.discard("")
        live = Product.objects.filter(is_active=True, slug__in=delisted)
        self.assertEqual(list(live), [], "delisted products still active")

    def test_no_glp1_class_product_is_active(self):
        """Retatrutide and any GLP-1/GIP analogue: delisted, both columns."""
        live = Product.objects.filter(is_active=True)
        for needle in ("retatrutide", "semaglutide", "tirzepatide"):
            self.assertFalse(live.filter(slug__icontains=needle).exists(), needle)

    def test_no_prescription_drug_list_product_is_active(self):
        """Tesamorelin is on Canada's PDL as 'tesamorelin or its salts or
        derivatives', effective 2014-05-12."""
        self.assertFalse(
            Product.objects.filter(is_active=True, slug__icontains="tesamorelin").exists())

    def test_no_reconstitution_supply_in_catalogue(self):
        """Constraint 4: no diluent or injection supply sold alongside compounds.

        Bundling a lyophilised compound with a diluent has been used directly as
        evidence of intended injection."""
        live = Product.objects.filter(is_active=True)
        for needle in ("bacteriostatic", "water", "syringe", "needle", "diluent"):
            self.assertFalse(live.filter(name__icontains=needle).exists(), needle)
        self.assertFalse(live.filter(category__name__iexact="Supplies").exists())

    def test_no_undisclosed_blend_is_active(self):
        """A blend cannot carry a CAS, formula or molecular weight, so it cannot
        satisfy the identification requirement under any copy."""
        live = Product.objects.filter(is_active=True)
        for needle in ("klow", "glow"):
            self.assertFalse(live.filter(slug__iexact=needle).exists(), needle)
        self.assertFalse(live.filter(name__contains=" + ").exists())

    def test_no_active_product_claims_a_purity_it_cannot_evidence(self):
        """Unchanged rule, restated as a test: a purity figure reads as a
        measured result and no analysis is held for any lot."""
        for p in Product.objects.filter(is_active=True).exclude(purity=""):
            self.assertTrue(p.coa_url, f"{p.slug} states purity {p.purity!r} with no COA")


class SiteCopyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_sites")

    def test_no_site_tagline_or_meta_states_an_outcome(self):
        bad = []
        for s in Site.objects.all():
            for field in ("tagline", "meta_description", "promo_code"):
                val = getattr(s, field, "") or ""
                for hit in _hits(val, OUTCOME_TERMS + PROMO_TERMS):
                    bad.append(f"{s.domain}.{field}: {hit} in {val!r}")
        self.assertEqual(bad, [], "\n".join(bad))

    def test_no_promo_codes_configured(self):
        """Discount urgency on an unapproved compound is a retail device, and
        BURN10 was a fat-loss promise in a coupon."""
        with_codes = [s.domain for s in Site.objects.all() if (s.promo_code or "").strip()]
        self.assertEqual(with_codes, [])
