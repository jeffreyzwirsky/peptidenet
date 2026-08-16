from django.test import TestCase

class ProductLabelComplianceTests(TestCase):
    """The vial label is a published surface and must carry no claim the
    business cannot support.

    Until 2026-08-16 every product image printed "≥99% PURITY HPLC" — on a
    catalogue whose own system prompt says it holds no certificate of analysis,
    no purity result and no identity confirmation for any compound. It is the
    same claim class that got a blog post pulled the day before.

    It survived because compliance_check scans TEXT and this was baked into a
    PNG: 1027 surfaces, 0 failures, while the claim sat on 36 images across 8
    storefronts. A scanner that cannot see a surface will always call it clean.
    """

    def _label_text(self):
        import re
        from apps.catalog.management.commands.generate_product_images import VIAL
        markup = re.sub(r"<!--.*?-->", " ", VIAL.template, flags=re.S)
        text = re.sub(r"<[^>]+>", " ", markup)
        return " ".join(re.sub(r"\$\{?\w+\}?", " ", text).split())

    def test_the_label_passes_the_guardrail_scan(self):
        from apps.blog import guardrails
        hard = guardrails.scan(self._label_text())[0]
        self.assertEqual(hard, [], f"vial label makes a blocked claim: {hard}")

    def test_the_label_names_no_purity_or_testing_method(self):
        """Belt and braces: the guardrail scan needs a figure to flag a purity
        claim, but an empty 'PURITY HPLC' slot still implies testing exists."""
        t = self._label_text().upper()
        for banned in ("PURITY", "HPLC", "COA", "CERTIFICATE OF ANALYSIS", "ASSAY"):
            self.assertNotIn(banned, t, f"label still references {banned!r}")

    def test_the_label_keeps_the_research_use_notice(self):
        self.assertIn("NOT FOR HUMAN CONSUMPTION", self._label_text().upper())

    def test_the_renderer_dedupes_first_wins_like_the_database(self):
        """Tests the RENDERER, not the data. An earlier version of this test only
        asserted the JSON had duplicates, so deleting the dedupe left it green
        while images went back to disagreeing with their pages."""
        from apps.catalog.management.commands.generate_product_images import (
            dedupe_by_slug,
        )
        products = [
            {"n": "BPC-157", "sizes": ["10mg"]},
            {"n": "BPC-157", "sizes": ["5mg"]},
            {"n": "Retatrutide", "sizes": ["10mg"]},
            {"n": "Retatrutide", "sizes": ["60mg"]},
        ]
        out = dedupe_by_slug(products)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["sizes"], ["10mg"])   # first wins, as the DB does
        self.assertEqual(out[1]["sizes"], ["10mg"])

    def test_image_slugs_are_unique_so_labels_match_their_page(self):
        """catalogue.json has 28 duplicated slugs (retatrutide appears 8 times).
        Every duplicate rendered to the same <slug>.png so the LAST won, while
        seed_catalog keeps the FIRST — the page said 10mg and its own image said
        5 mg. The renderer must dedupe the same way the database does."""
        import json
        from pathlib import Path
        from django.utils.text import slugify
        products = json.loads(
            Path("data/catalogue.json").read_text(encoding="utf-8"))["products"]
        seen, unique = set(), []
        for p in products:
            s = slugify(p["n"])
            if s not in seen:
                seen.add(s)
                unique.append(p)
        first = {slugify(p["n"]): (p.get("sizes") or [None])[0] for p in unique}
        last = {}
        for p in products:
            last[slugify(p["n"])] = (p.get("sizes") or [None])[0]
        differ = {k for k in first if first[k] != last[k]}
        self.assertTrue(differ, "test premise: some slug must differ first vs last")
        self.assertEqual(first["bpc-157"], "10mg")   # what the DB keeps
        self.assertNotEqual(last["bpc-157"], "10mg")  # what last-wins would print
