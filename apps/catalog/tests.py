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


class ProductArtTests(TestCase):
    """Every product page must show a photograph of the vial it is selling.

    The label prints the NET FILL and the powder cake is drawn from the
    milligram mass, so artwork is per-strength, not per-compound. Two earlier
    attempts got this wrong in opposite directions and both shipped:

      * last-wins — every strength rendered to <compound>.png and the last
        entry overwrote the rest, so the page said 10 mg and its own image
        said 5 mg;
      * dedupe first-wins — deterministic, but all eight retatrutide strengths
        then shared a picture of a 10 mg vial, so the 60 mg page sold a 60 mg
        vial under a label reading "10 MG".

    The invariant is: one render per product slug, and the render a product
    points at is its own.
    """

    def test_render_slug_follows_the_explicit_slug_like_seed_catalog_does(self):
        """The renderer must key on the same field the database keys on.

        Slugifying the NAME is what collapsed 87 entries onto 48 filenames.
        seed_catalog uses `p.get("slug") or slugify(p["n"])`; if these two ever
        disagree the file written is not the file the page asks for.
        """
        from apps.catalog.management.commands.generate_product_images import (
            product_slug,
        )
        self.assertEqual(
            product_slug({"n": "Retatrutide", "slug": "retatrutide-60mg"}),
            "retatrutide-60mg")
        self.assertEqual(product_slug({"n": "BPC-157 + TB-500"}), "bpc-157-tb-500")

    def test_every_catalogue_entry_gets_its_own_filename(self):
        """Tests the FUNCTION against the real data, not the data alone — a
        premise-only version of this test stayed green when the code changed."""
        import json
        from pathlib import Path
        from apps.catalog.management.commands.generate_product_images import (
            product_slug,
        )
        products = json.loads(
            Path("data/catalogue.json").read_text(encoding="utf-8"))["products"]
        slugs = [product_slug(p) for p in products]
        self.assertEqual(len(slugs), len(set(slugs)),
                         "two products would render to the same file")
        # And the collapse is really gone: name-slugging still collides.
        from django.utils.text import slugify
        self.assertLess(len({slugify(p["n"]) for p in products}), len(set(slugs)))

    def test_a_slug_collision_raises_instead_of_dropping_a_product(self):
        """Silently skipping the loser is how a product ends up illustrated by
        a different product with nothing in the log to say so."""
        from django.core.management.base import CommandError
        from apps.catalog.management.commands.generate_product_images import (
            assert_unique_slugs,
        )
        with self.assertRaises(CommandError):
            assert_unique_slugs([{"n": "BPC-157", "sizes": ["10mg"]},
                                 {"n": "BPC-157", "sizes": ["5mg"]}])

    def test_every_catalogue_entry_has_a_render_on_disk(self):
        """The check that actually catches a new product shipping unillustrated
        — 49 active products were on the grey SVG fallback until 2026-08-16."""
        import json
        from pathlib import Path
        from apps.catalog.management.commands.generate_product_images import (
            product_slug,
        )
        products = json.loads(
            Path("data/catalogue.json").read_text(encoding="utf-8"))["products"]
        art = Path("static/products")
        missing = sorted(product_slug(p) for p in products
                         if not (art / f"{product_slug(p)}.png").exists())
        self.assertEqual(missing, [], "no render — run generate_product_images "
                                      "--missing-only")
        no_label = sorted(product_slug(p) for p in products
                          if not (art / f"{product_slug(p)}-label.png").exists())
        self.assertEqual(no_label, [], "no label crop for these products")


class ArtResolutionTests(TestCase):
    """seed_catalog and assign_product_images must resolve art identically.

    They did not: the seeder went through the size family, the assigner looked
    only for <slug>.png. A sibling was illustrated by one command and left bare
    by the other, which is the whole reason 49 products had no image while the
    seeder reported success. apps.catalog.images is now the one definition;
    these tests pin its three outcomes.
    """

    def _dir(self, *names):
        import tempfile
        from pathlib import Path
        d = Path(tempfile.mkdtemp(prefix="art-"))
        for n in names:
            (d / n).write_bytes(b"png")
        self.addCleanup(__import__("shutil").rmtree, d, True)
        return d

    def test_a_products_own_render_wins_over_its_familys(self):
        from apps.catalog import images
        d = self._dir("retatrutide.png", "retatrutide-60mg.png",
                      "retatrutide-60mg-label.png")
        primary, label = images.art_urls("retatrutide-60mg", "retatrutide", d)
        self.assertEqual(primary, "/static/products/retatrutide-60mg.png")
        self.assertEqual(label, "/static/products/retatrutide-60mg-label.png")
        self.assertFalse(images.is_family_fallback("retatrutide-60mg",
                                                   "retatrutide", d))

    def test_the_family_render_is_a_flagged_fallback_not_the_default(self):
        """Better than a grey placeholder, worse than a correct render — so it
        must be reported, because the net fill it prints is another size."""
        from apps.catalog import images
        d = self._dir("retatrutide.png", "retatrutide-label.png")
        primary, _ = images.art_urls("retatrutide-60mg", "retatrutide", d)
        self.assertEqual(primary, "/static/products/retatrutide.png")
        self.assertTrue(images.is_family_fallback("retatrutide-60mg",
                                                  "retatrutide", d))

    def test_no_file_means_no_image_so_the_svg_fallback_stays(self):
        from apps.catalog import images
        d = self._dir()
        self.assertEqual(images.art_urls("dihexa", "", d), (None, None))
        self.assertFalse(images.is_family_fallback("dihexa", "", d))

    def test_a_missing_label_crop_does_not_invent_a_gallery_entry(self):
        from apps.catalog import images
        d = self._dir("dihexa.png")
        self.assertEqual(images.art_urls("dihexa", "", d),
                         ("/static/products/dihexa.png", None))

    def test_assign_gives_a_size_sibling_its_own_art(self):
        """End-to-end through the command, because the bug was in the command's
        lookup, not in any helper it called."""
        from io import StringIO
        from django.core.management import call_command
        from apps.catalog.models import Category, Product
        cat = Category.objects.create(name="Metabolic", slug="metabolic")
        Product.objects.create(
            name="Retatrutide", slug="retatrutide-60mg", category=cat,
            family="retatrutide", sizes=["60mg"], price=159, purity="")
        d = self._dir("retatrutide.png", "retatrutide-60mg.png",
                      "retatrutide-60mg-label.png")
        with self.settings(STATICFILES_DIRS=[str(d.parent)]):
            # products_dir() appends "products/", so point it at a dir whose
            # child is the fixture dir.
            import apps.catalog.images as images
            orig = images.products_dir
            images.products_dir = lambda: d
            try:
                call_command("assign_product_images", stdout=StringIO())
            finally:
                images.products_dir = orig
        p = Product.objects.get(slug="retatrutide-60mg")
        self.assertEqual(p.image, "/static/products/retatrutide-60mg.png")
        self.assertTrue(p.gallery)
        self.assertEqual(p.gallery[0]["src"],
                         "/static/products/retatrutide-60mg-label.png")

    def test_assign_falls_back_to_family_art_instead_of_leaving_a_gap(self):
        """THE 49-product bug, through the command.

        A sibling whose own render has not been made yet must still get the
        family's picture, because that is what seed_catalog already gives it —
        when the two disagree, whichever ran last decides, and the catalogue
        silently half-fills. The previous version of this command looked only
        for <slug>.png and left every such product on the SVG fallback.

        Passing the family through is the entire point, so this test must fail
        if that argument is dropped.
        """
        from io import StringIO
        from django.core.management import call_command
        from apps.catalog.models import Category, Product
        cat = Category.objects.create(name="Growth Factors", slug="growth-factors")
        Product.objects.create(
            name="Sermorelin", slug="sermorelin-5mg", category=cat,
            family="sermorelin", sizes=["5mg"], price=30, purity="")
        d = self._dir("sermorelin.png", "sermorelin-label.png")  # no -5mg render
        import apps.catalog.images as images
        orig = images.products_dir
        images.products_dir = lambda: d
        try:
            out = StringIO()
            call_command("assign_product_images", stdout=out)
        finally:
            images.products_dir = orig
        p = Product.objects.get(slug="sermorelin-5mg")
        self.assertEqual(p.image, "/static/products/sermorelin.png")
        # and it must SAY so — a borrowed photograph prints the wrong net fill
        self.assertIn("family fallback", out.getvalue())
