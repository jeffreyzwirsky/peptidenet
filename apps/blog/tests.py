from django.core.management import call_command
from django.test import TestCase

from apps.stores.models import Site

from . import generator, guardrails
from .models import BlogPost


class GuardrailTests(TestCase):
    def test_flags_medical_claims(self):
        bad = "This peptide can cure disease and treat inflammation. It is FDA approved."
        r = guardrails.review(bad)
        self.assertEqual(r["status"], "flagged")
        self.assertGreaterEqual(r["hard_count"], 2)

    def test_flags_dosing_and_weight_loss(self):
        bad = "Take 10 mg per day to lose weight fast — guaranteed results."
        r = guardrails.review(bad)
        self.assertEqual(r["status"], "flagged")

    def test_clean_research_copy_passes(self):
        good = ("This article describes a research compound released at high purity with a "
                "batch-specific certificate of analysis, available to laboratories in Canada.")
        r = guardrails.review(good)
        self.assertEqual(r["status"], "pass")

    def test_disclaimer_always_added(self):
        r = guardrails.review("A short note with no disclaimer.")
        self.assertIn("research use only", r["text"].lower())


class GeneratorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog")
        call_command("seed_sites")

    def test_generated_post_is_draft_and_compliant(self):
        site = Site.objects.get(domain="smashfat.ca")
        post = generator.generate(site, "metabolic research peptides Canada")
        self.assertEqual(post.status, "needs_review")     # NEVER auto-published
        self.assertEqual(post.compliance_status, "pass")  # stub copy is clean
        self.assertIn("research use only", post.body.lower())
        self.assertTrue(post.hero_svg.startswith("<svg"))
        self.assertIn("metabolic research peptides", post.keyword)

    def test_generated_post_gets_real_hero_image(self):
        from .models import BLOG_HERO_POOL
        site = Site.objects.get(domain="smashfat.ca")
        post = generator.generate(site, "retatrutide research")
        self.assertIn(post.hero_image, BLOG_HERO_POOL)

    def test_assign_blog_images_backfills(self):
        from .models import BLOG_HERO_POOL
        site = Site.objects.get(domain="smashfat.ca")
        p = BlogPost.objects.create(site=site, title="no img", slug="no-img",
                                    body="research use only")
        self.assertEqual(p.hero_image, "")
        call_command("assign_blog_images")
        p.refresh_from_db()
        self.assertIn(p.hero_image, BLOG_HERO_POOL)

    def test_flagged_post_cannot_publish(self):
        site = Site.objects.get(domain="smashfat.ca")
        p = BlogPost.objects.create(site=site, title="x", body="we cure cancer, FDA approved",
                                    compliance_status="flagged")
        self.assertFalse(p.can_publish)

    def test_daily_command_creates_drafts_only(self):
        call_command("generate_daily_posts", "--site", "smashfat.ca")
        posts = BlogPost.objects.filter(site__domain="smashfat.ca")
        self.assertTrue(posts.exists())
        self.assertFalse(posts.filter(status="published").exists())


class BlogStorefrontTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog")
        call_command("seed_sites")

    def test_only_published_posts_show(self):
        from django.utils import timezone
        site = Site.objects.get(domain="smashfat.ca")
        BlogPost.objects.create(site=site, title="Draft one", slug="draft-one",
                                body="research note. research use only.", status="needs_review")
        BlogPost.objects.create(site=site, title="Live one", slug="live-one",
                                body="research note. research use only.", status="published",
                                published_at=timezone.now())
        r = self.client.get("/blog/", HTTP_HOST="smashfat.ca")
        self.assertContains(r, "Live one")
        self.assertNotContains(r, "Draft one")
        # a draft's detail page 404s
        self.assertEqual(self.client.get("/blog/draft-one/", HTTP_HOST="smashfat.ca").status_code, 404)


class BlogCreatorFixTests(TestCase):
    """Regression: the creator used to 500 on a duplicate (site, slug); and blog
    images can now come from OpenAI, degrading to the stock pool when offline."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog")
        call_command("seed_sites")

    def test_regenerating_same_keyword_does_not_crash(self):
        site = Site.objects.get(domain="smashfat.ca")
        p1 = generator.generate(site, "bpc-157 research")
        p2 = generator.generate(site, "bpc-157 research")   # used to raise IntegrityError
        self.assertNotEqual(p1.slug, p2.slug)
        self.assertEqual(BlogPost.objects.filter(site=site).count(), 2)

    def test_image_generation_stubs_when_ai_offline(self):
        from apps.ai import images
        from apps.ai.models import AgentRun
        site = Site.objects.get(domain="smashfat.ca")
        with self.settings(AI_LIVE=False):
            path = images.generate_blog_image("bpc-157 research", site=site)
        self.assertIsNone(path)  # offline -> caller falls back to stock/SVG
        self.assertTrue(
            AgentRun.objects.filter(purpose="blog_image", provider="stub").exists())

    def test_offline_generate_falls_back_to_stock_pool(self):
        from .models import BLOG_HERO_POOL
        site = Site.objects.get(domain="smashfat.ca")
        with self.settings(AI_LIVE=False):
            post = generator.generate(site, "tirzepatide research")
        self.assertIn(post.hero_image, BLOG_HERO_POOL)


class ClaimGuardrailTests(TestCase):
    """The claims a generated post must never be able to make.

    Every string below is something a well-intentioned model produces readily,
    because each one reads as reassurance rather than as a claim. The origin
    cases are the sharpest: the network makes no representation about where
    goods ship from in either direction, and a model told its audience is
    Canadian will volunteer "ships from Canada" unprompted.
    """

    def _labels(self, text):
        from . import guardrails
        hard, _ = guardrails.scan(text)
        return {label for label, _ in hard}

    def test_origin_claims_are_blocked_in_both_directions(self):
        for text in (
            "All orders ship from Canada in plain packaging.",
            "Our compounds are shipped from Alberta the same week.",
            "Stock is warehoused in Canada for fast fulfilment.",
            "These peptides are manufactured in China to our specification.",
            "Product is sourced from China and inspected on arrival.",
            "Dispatched from the United States within one business day.",
        ):
            self.assertIn("shipping origin claim", self._labels(text), text)

    def test_domestic_stock_phrasings_are_blocked(self):
        for text in ("Canadian-made research compounds.",
                     "We hold domestic stock of every catalogue item.",
                     "Made in Canada, tested independently."):
            self.assertTrue(
                {"shipping origin claim", "domestic-stock claim"} & self._labels(text),
                text)

    def test_approved_origin_neutral_wording_passes(self):
        """The sanctioned substitute must not trip the scanner.

        If the compliant phrasing were flagged, every clean post would arrive
        with a false positive and the reviewer would stop trusting the flag.
        """
        text = ("Orders ship directly from our manufacturing partner in plain, "
                "tracked packaging. Allow 10–15 days for delivery; shipments may "
                "be subject to customs clearance. Serving research laboratories "
                "across Canada.")
        self.assertEqual(self._labels(text), set())

    def test_unverifiable_superlatives_and_price_claims_blocked(self):
        for text in ("The cheapest research peptides in Canada.",
                     "We offer the best price on BPC-157.",
                     "The purest compounds on the market."):
            self.assertIn("unverifiable superlative", self._labels(text), text)

    def test_uncertified_credentials_blocked(self):
        for text in ("Produced in a GMP-certified facility.",
                     "Our ISO 17025 accredited partner lab.",
                     "Pharmaceutical-grade material."):
            self.assertIn("unheld certification", self._labels(text), text)

    def test_off_policy_delivery_promises_blocked(self):
        for text in ("Expect 2-3 days delivery on all orders.",
                     "Next-day delivery available.",
                     "Free express shipping over $200."):
            self.assertIn("off-policy delivery promise", self._labels(text), text)

    def test_the_real_delivery_window_passes(self):
        self.assertEqual(self._labels("Allow 10–15 days delivery."), set())
        self.assertEqual(self._labels("Allow 10-15 days delivery."), set())

    def test_in_vitro_language_is_not_flagged_as_a_medical_claim(self):
        """'cells treated with' is ordinary bench description, not a claim."""
        self.assertNotIn(
            "medical/therapeutic claim",
            self._labels("Cultures were treated with the compound for 24 hours."))
        self.assertIn(
            "medical/therapeutic claim",
            self._labels("This compound treats inflammation."))


class BlogMarketTargetingTests(TestCase):
    """US storefronts were being handed Canada-targeted prompts."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog")
        call_command("seed_sites")

    def test_us_sites_are_not_prompted_as_canadian(self):
        us = Site.objects.get(domain="smashfatbiolabs.com")
        prompt = generator.build_system(us)
        self.assertIn("United States", prompt)
        self.assertNotIn("Canadian research-compound", prompt)

    def test_ca_sites_still_target_canada(self):
        ca = Site.objects.get(domain="smashfatbiolabs.ca")
        self.assertIn("Canada", generator.build_system(ca))

    def test_prompt_forbids_naming_any_origin(self):
        prompt = generator.build_system(Site.objects.get(domain="smashfat.ca"))
        self.assertIn("NEVER state or imply a country", prompt)
        self.assertIn("manufacturing partner", prompt)

    def test_every_domain_has_its_own_editorial_angle(self):
        from . import keywords
        angles = [keywords.angle_for(s) for s in Site.objects.all()]
        self.assertTrue(all(angles), "a site with no angle writes the same post as its twin")
        self.assertEqual(len(set(angles)), len(angles), "two sites share an angle")
