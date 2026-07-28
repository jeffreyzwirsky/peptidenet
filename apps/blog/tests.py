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
        """Clean copy is copy with no unevidenced claim in it.

        This test used to assert that "released at high purity with a
        batch-specific certificate of analysis" PASSED. It encoded the old
        policy. We hold no analysis for anything in the catalogue, so that
        sentence is now exactly what the scanner exists to catch — the test
        moves with the policy rather than being loosened around it.
        """
        good = ("This article describes a research compound supplied as a laboratory "
                "reference material to laboratories in Canada. Orders ship directly "
                "from our manufacturing partner.")
        r = guardrails.review(good)
        self.assertEqual(r["status"], "pass", r["notes"])

    def test_old_marketing_copy_is_now_flagged(self):
        old = ("This article describes a research compound released at high purity with a "
               "batch-specific certificate of analysis, available to laboratories in Canada.")
        r = guardrails.review(old)
        self.assertEqual(r["status"], "flagged")

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


class DisclaimerNotFlaggedTests(TestCase):
    """The mandated disclaimer must not read as a violation of itself.

    Every one of these is real text produced by the live generator. Before
    negation-awareness they flagged 8 posts out of 8 — an all-red queue that a
    reviewer learns to ignore, which is how a genuine claim gets waved through.
    """

    def _labels(self, text):
        from . import guardrails
        hard, _ = guardrails.scan(text)
        return {label for label, _ in hard}

    def test_research_use_disclaimer_passes(self):
        for text in (
            "Compounds supplied by SmashFat BioLabs are intended for laboratory "
            "research use only and are not approved for human consumption, "
            "veterinary use, or any therapeutic, diagnostic, or clinical purpose.",
            "They are not intended for human consumption, veterinary use, medical "
            "diagnosis, treatment, or the prevention of any disease.",
            "This article makes no claim that any compound can diagnose, treat, "
            "cure, or prevent any condition.",
            "These materials are not for human use and carry no guarantee of "
            "efficacy.",
        ):
            self.assertEqual(self._labels(text), set(), text)

    def test_the_actual_claim_still_trips(self):
        """Negation-awareness must not become a blanket amnesty."""
        for text in ("This compound treats inflammation and prevents scarring.",
                     "Approved for human consumption.",
                     "Clinically proven to cure tendon injury."):
            self.assertTrue(self._labels(text), text)

    def test_negation_does_not_leak_across_a_sentence_boundary(self):
        """A full stop ends the negation's scope."""
        text = ("The compound is not a supplement. It treats inflammation "
                "and prevents scarring.")
        self.assertIn("medical/therapeutic claim", self._labels(text))

    def test_origin_claims_get_no_negation_escape(self):
        """Denying an origin still names a country next to this business.

        The standing position is silence on origin, not denial, so the negation
        escape deliberately does not apply to this rule.
        """
        self.assertIn("shipping origin claim",
                      self._labels("We do not ship from China."))
        self.assertIn("shipping origin claim",
                      self._labels("Our products are not manufactured in Canada."))


class QuotedRedFlagTests(TestCase):
    """Buyer-vetting guides quote the claims they warn readers about.

    All real text from the live where-do-i-get-peptides drafts. Scanning a
    quoted red flag as if the site were asserting it turned the network's most
    useful editorial content into its most heavily flagged.
    """

    def _scan(self, text):
        from . import guardrails
        hard, soft = guardrails.scan(text)
        return ({l for l, _ in hard}, {l for l, _ in soft})

    def test_quoted_red_flags_are_surfaced_not_blocked(self):
        for text in (
            'Suppliers who rely on marketing language ("pharmaceutical grade," '
            '"purest available," "clinically validated") should be questioned.',
            'Phrases like "cheapest research peptides," "lowest prices in the '
            'industry," or "unbeatable rates" are a warning sign.',
            'Watch for "clinically proven" or "proven to work" efficacy claims.',
        ):
            hard, soft = self._scan(text)
            self.assertEqual(hard, set(), text)
            self.assertTrue(any(l.startswith("quoted example") for l in soft), text)

    def test_advisory_warnings_are_not_read_as_promises(self):
        hard, _ = self._scan(
            "Avoid suppliers who promise same-day or next-day delivery on "
            "custom compounds.")
        self.assertEqual(hard, set())

    def test_the_same_claim_unquoted_still_blocks(self):
        hard, _ = self._scan("Our compounds are pharmaceutical grade and "
                             "clinically proven.")
        self.assertTrue(hard)

    def test_quoting_does_not_launder_an_origin_claim(self):
        hard, _ = self._scan('Our partner calls them "manufactured in China" '
                             'reference materials.')
        self.assertIn("shipping origin claim", hard)


class UnevidencedAnalyticalClaimTests(TestCase):
    """We hold no certificate of analysis, purity result or identity confirmation.

    Every phrase below was live across all eight storefronts until it turned out
    none of it could be evidenced. The scanner now treats them as hard failures
    so a generated post cannot quietly reintroduce what was just removed by hand.
    """

    def _labels(self, text):
        from . import guardrails
        hard, _ = guardrails.scan(text)
        return {label for label, _ in hard}

    def test_testing_claims_blocked(self):
        for t in ("Every batch is third-party tested by HPLC and mass spectrometry.",
                  "Independently verified for identity.",
                  "Batch-tested against a release purity threshold.",
                  "Purity verified by chromatography."):
            self.assertIn("unsupported testing claim", self._labels(t), t)

    def test_coa_claims_blocked(self):
        for t in ("A batch-specific certificate of analysis ships with every vial.",
                  "COA available on request.",
                  "Ask us for the batch-matched certificate."):
            self.assertIn("unsupported COA claim", self._labels(t), t)

    def test_purity_figures_blocked(self):
        for t in ("Released at ≥99% purity.", "99.4% pure by area.",
                  "High-purity research compounds.", "Reference-grade material."):
            self.assertIn("unsupported purity figure", self._labels(t), t)

    def test_the_honest_replacement_passes(self):
        """The wording that replaced all of it must not trip the scanner.

        If the disclaimer were flagged, every clean post would arrive red and
        the reviewer would stop reading the queue — the same failure the
        negation escape was built to prevent.
        """
        for t in ("We hold no certificate of analysis, no purity result and no identity "
                  "confirmation for any compound in this catalogue.",
                  "No purity figure is published, because no measurement stands behind one.",
                  "Treat the material as uncharacterised and arrange your own analysis.",
                  "Orders ship directly from our manufacturing partner in plain, tracked "
                  "packaging. Allow 10–15 days for delivery."):
            self.assertEqual(self._labels(t), set(), t)
