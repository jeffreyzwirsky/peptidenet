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


class BlogTickTests(TestCase):
    """The auto-publish scheduler (policy change 2026-08-12, Jeff-approved):
    guardrail-PASSING posts publish on cadence; flagged posts never do."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog")
        call_command("seed_sites")

    def test_publishes_oldest_passing_backlog_draft(self):
        from .models import BLOG_HERO_POOL
        site = Site.objects.get(domain="smashfat.ca")
        old = BlogPost.objects.create(site=site, title="Old draft", slug="old-draft",
                                      body="research use only", compliance_status="pass")
        BlogPost.objects.create(site=site, title="New draft", slug="new-draft",
                                body="research use only", compliance_status="pass")
        call_command("blog_tick", "--site", "smashfat.ca", "--force")
        old.refresh_from_db()
        self.assertEqual(old.status, "published")
        self.assertIsNotNone(old.published_at)
        self.assertIn(old.hero_image, BLOG_HERO_POOL)  # image guaranteed
        # only one per posting day
        self.assertEqual(BlogPost.objects.filter(site=site, status="published").count(), 1)

    def test_flagged_draft_never_publishes(self):
        site = Site.objects.get(domain="smashfat.ca")
        BlogPost.objects.create(site=site, title="Bad", slug="bad",
                                body="we cure cancer", compliance_status="flagged")
        call_command("blog_tick", "--site", "smashfat.ca", "--force")
        # the flagged draft is skipped; a fresh (stub, clean) post publishes instead
        self.assertEqual(BlogPost.objects.get(slug="bad").status, "needs_review")
        pub = BlogPost.objects.filter(site=site, status="published")
        self.assertEqual(pub.count(), 1)
        self.assertEqual(pub.first().compliance_status, "pass")

    def test_generates_and_publishes_when_no_backlog(self):
        call_command("blog_tick", "--site", "smashfat.ca", "--force")
        pub = BlogPost.objects.filter(site__domain="smashfat.ca", status="published")
        self.assertEqual(pub.count(), 1)
        self.assertTrue(pub.first().hero_image)

    def test_publish_refuses_flagged_post(self):
        site = Site.objects.get(domain="smashfat.ca")
        p = BlogPost.objects.create(site=site, title="x", body="cure",
                                    compliance_status="flagged")
        with self.assertRaises(ValueError):
            p.publish()

    def test_cadence_is_three_days_and_staggered(self):
        from .management.commands.blog_tick import posting_days
        for s in Site.objects.filter(is_active=True):
            days = posting_days(s.domain)
            self.assertEqual(len(days), 3, s.domain)
            self.assertTrue(all(0 <= d <= 6 for d in days), s.domain)

    def test_off_day_publishes_nothing(self):
        from unittest import mock
        site = Site.objects.get(domain="smashfat.ca")
        BlogPost.objects.create(site=site, title="Ready", slug="ready",
                                body="research use only", compliance_status="pass")
        from .management.commands import blog_tick as bt
        with mock.patch.object(bt, "posting_days", return_value=[]):
            call_command("blog_tick", "--site", "smashfat.ca")
        self.assertFalse(BlogPost.objects.filter(status="published").exists())


class BlogFeedTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog")
        call_command("seed_sites")

    def test_feed_serves_only_this_sites_posts(self):
        from django.utils import timezone
        a = Site.objects.get(domain="smashfat.ca")
        b = Site.objects.get(domain="smashfatbiolabs.ca")
        BlogPost.objects.create(site=a, title="Feed A", slug="feed-a",
                                body="research use only", status="published",
                                published_at=timezone.now())
        BlogPost.objects.create(site=b, title="Feed B", slug="feed-b",
                                body="research use only", status="published",
                                published_at=timezone.now())
        r = self.client.get("/blog/feed/", HTTP_HOST="smashfat.ca")
        self.assertEqual(r.status_code, 200)
        self.assertIn("application/rss+xml", r["Content-Type"])
        body = r.content.decode()
        self.assertIn("Feed A", body)
        self.assertNotIn("Feed B", body)
        self.assertIn("https://smashfat.ca/blog/feed-a/",
                      body.replace("http://", "https://"))


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


class ResearchNewsGuardrailTests(TestCase):
    """Attributed research reporting passes; the same words as a bare brand
    claim still block. Attribution never rescues dosing/regulatory/testing."""

    def test_attributed_finding_is_reported_not_blocked(self):
        from apps.blog import guardrails
        r = guardrails.review(
            "A 2023 rodent study reported accelerated tendon healing in rats "
            "given BPC-157, though human relevance remains unknown."
        )
        self.assertEqual(r["status"], "pass")
        self.assertIn("reported research finding", r["notes"])

    def test_trial_weight_finding_is_reported_not_blocked(self):
        from apps.blog import guardrails
        r = guardrails.review(
            "In the phase 2 trial, researchers observed that participants "
            "on retatrutide were reported to lose weight relative to placebo."
        )
        self.assertEqual(r["status"], "pass")

    def test_same_claim_unattributed_still_blocks(self):
        from apps.blog import guardrails
        r = guardrails.review("BPC-157 supports healing and helps you lose weight.")
        self.assertEqual(r["status"], "flagged")

    def test_attribution_never_rescues_dosing(self):
        from apps.blog import guardrails
        r = guardrails.review(
            "The study protocol used a dosage of 10 mg per day in participants."
        )
        self.assertEqual(r["status"], "flagged")

    def test_attribution_never_rescues_testing_claims(self):
        from apps.blog import guardrails
        r = guardrails.review(
            "A study confirmed our products are third-party tested."
        )
        self.assertEqual(r["status"], "flagged")

    def test_disclaimer_carries_do_your_own_research_note(self):
        from apps.blog import guardrails
        r = guardrails.review("A short note on peptide research.")
        self.assertIn("do your own research", r["text"].lower())
        self.assertIn("not medical advice", r["text"].lower())

    def test_news_lane_keywords_generate_passing_drafts(self):
        from django.core.management import call_command

        from apps.blog import generator
        from apps.stores.models import Site
        call_command("seed_catalog"); call_command("seed_sites")
        site = Site.objects.get(domain="smashfatbiolabs.ca")
        p = generator.generate(site, "peptide research news")
        self.assertEqual(p.compliance_status, "pass")


class RetroScanTests(TestCase):
    """`rescan_posts` — the guardrails applied to what is ALREADY live.

    The generation-time scan never revisits a post. When a new rule lands, every
    post that published before it keeps serving the claim. On 2026-08-14 five of
    the six published posts across the network were asserting a "≥99% purity
    threshold", a "batch-specific Certificate of Analysis" and a shipping origin
    — all three already scrubbed from the storefronts — and no command existed
    that would have surfaced it.
    """

    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog")
        call_command("seed_sites")
        cls.site = Site.objects.get(domain="peptidesalberta.ca")

    def _post(self, body, **kw):
        defaults = dict(site=self.site, title="Supplier notes", body=body,
                        status="published", compliance_status="pass")
        defaults.update(kw)
        return BlogPost.objects.create(**defaults)

    # The real sentence, from the real post that was live on peptidesalberta.ca.
    OFFENDING = ("Every compound is released above a documented ≥99% purity threshold "
                 "and independently analyzed by HPLC and mass spectrometry. A "
                 "batch-specific Certificate of Analysis (COA) is available on request.")
    CLEAN = ("We hold no certificate of analysis, no purity result and no identity "
             "confirmation for anything in this catalogue. Assume the vial is "
             "uncharacterised and budget for your own analysis.")

    def test_report_only_is_the_default_and_changes_nothing(self):
        p = self._post(self.OFFENDING)
        call_command("rescan_posts")
        p.refresh_from_db()
        self.assertEqual(p.status, "published", "a bare report must not mutate anything")

    def test_unpublish_takes_down_the_failing_post(self):
        bad = self._post(self.OFFENDING, slug="bad")
        good = self._post(self.CLEAN, slug="good")
        call_command("rescan_posts", unpublish=True)
        bad.refresh_from_db(); good.refresh_from_db()
        self.assertEqual(bad.status, "needs_review")
        self.assertEqual(bad.compliance_status, "flagged")
        self.assertIn("purity", bad.compliance_notes.lower())
        self.assertEqual(good.status, "published", "a clean post must survive the sweep")

    def test_the_body_is_never_edited(self):
        """Unpublishing must be reversible — we flip status, never the text."""
        bad = self._post(self.OFFENDING, slug="bad")
        call_command("rescan_posts", unpublish=True)
        bad.refresh_from_db()
        self.assertEqual(bad.body, self.OFFENDING)

    def test_a_claim_hiding_in_the_meta_description_is_caught(self):
        """A body-only scan misses the field Google actually shows."""
        p = self._post(self.CLEAN, slug="meta",
                       meta_description="Batch-specific certificate of analysis on request.")
        call_command("rescan_posts", unpublish=True)
        p.refresh_from_db()
        self.assertEqual(p.status, "needs_review")

    def test_drafts_are_left_alone_by_unpublish(self):
        d = self._post(self.OFFENDING, slug="draft", status="needs_review")
        call_command("rescan_posts", unpublish=True, all=True)
        d.refresh_from_db()
        self.assertEqual(d.status, "needs_review")


class RepairLoopTests(TestCase):
    """The writer now gets its own violations back and a chance to fix them.

    Before this, a flagged draft was a dead draft: one LLM call, one scan, and
    if the scan found anything the post sat in needs_review forever. Sixty-five
    of the network's sixty-six drafts were stranded there and six of the eight
    blogs had never published a post.
    """

    def setUp(self):
        self.site = Site.objects.create(
            domain="repair-test.ca", brand_name="Repair Test", theme="biolabs",
            country="CA", is_active=True,
        )

    # --- the brief the model is handed ------------------------------------
    def test_remediation_brief_names_the_rule_and_quotes_the_evidence(self):
        text = ("Every batch is HPLC tested and a certificate of analysis is "
                "available on request. We ship from Canada.")
        hard, _ = guardrails.scan(text)
        brief = guardrails.remediation_brief(hard)
        self.assertIn("UNSUPPORTED TESTING CLAIM", brief)
        self.assertIn("UNSUPPORTED COA CLAIM", brief)
        self.assertIn("SHIPPING ORIGIN CLAIM", brief)
        # The evidence is quoted back, not just the rule name — a model told
        # only "no testing claims" patches the wrong sentence.
        self.assertIn("HPLC", brief)
        # And each rule carries an instruction, not just an accusation.
        self.assertIn("uncharacterised", brief)

    def test_brief_groups_repeats_instead_of_listing_every_hit(self):
        text = " ".join(["A certificate of analysis is provided."] * 8)
        hard, _ = guardrails.scan(text)
        brief = guardrails.remediation_brief(hard)
        self.assertEqual(brief.count("UNSUPPORTED COA CLAIM"), 1)

    # --- the deterministic last resort -------------------------------------
    def test_scrub_removes_only_the_offending_sentence(self):
        text = ("Peptides are supplied as lyophilised powder. "
                "Every batch is HPLC tested to ≥99% purity. "
                "Store the vial below freezing until reconstitution.")
        cleaned = guardrails.scrub(text)
        self.assertIn("lyophilised powder", cleaned)
        self.assertIn("below freezing", cleaned)
        self.assertNotIn("HPLC", cleaned)
        self.assertEqual(guardrails.review(cleaned)["status"], "pass")

    def test_scrub_also_cleans_headings(self):
        """A claim in an H2 is the most visible place it can sit."""
        text = ("# Sourcing notes\n\n"
                "## Our HPLC tested catalogue\n\n"
                "The catalogue lists research categories and vial sizes.\n")
        cleaned = guardrails.scrub(text)
        self.assertNotIn("HPLC", cleaned)
        self.assertIn("Sourcing notes", cleaned)
        self.assertIn("research categories", cleaned)

    def test_scrub_output_always_passes_the_scanner(self):
        text = ("Our GMP-certified facility ships from Canada. "
                "This compound cures inflammation and is FDA-approved. "
                "Vials are supplied for laboratory research.")
        self.assertEqual(guardrails.review(guardrails.scrub(text))["status"], "pass")

    def test_word_count_gate_ignores_markdown(self):
        self.assertEqual(guardrails.word_count("# Title\n\n**bold** words here"), 4)

    # --- the loop itself ----------------------------------------------------
    def test_repair_loop_recovers_a_flagged_body(self):
        """With AI stubbed there is no rewrite, so the scrub must carry it.

        This is the important half of the guarantee: the loop cannot depend on
        a model being reachable. A long draft with two bad sentences still ends
        up publishable with no API call at all.
        """
        filler = ("Researchers evaluating a supplier should record the vial "
                  "size, the storage temperature and the date of receipt in "
                  "their own inventory system before any bench work begins. ")
        body = ("# Evaluating a research supplier\n\n"
                + filler * 40
                + "\nEvery batch is HPLC tested to ≥99% purity.\n"
                + "A certificate of analysis is available on request.\n")
        review, provenance = generator.compose_repair(self.site, body, "research peptides")
        self.assertEqual(review["status"], "pass")
        self.assertNotIn("HPLC", review["text"])
        self.assertGreaterEqual(guardrails.word_count(review["text"]),
                                generator.MIN_PUBLISH_WORDS)
        self.assertTrue(any("scrubbed" in p for p in provenance), provenance)

    def test_a_short_draft_is_held_rather_than_published_thin(self):
        body = "# Note\n\nEvery batch is HPLC tested to ≥99% purity.\n"
        review, provenance = generator.compose_repair(self.site, body, "research peptides")
        self.assertTrue(any("held for a human" in p for p in provenance), provenance)

    def test_repair_never_edits_a_body_it_cannot_clean(self):
        """A post that stays flagged keeps its original text, so a rewrite is
        still possible later from the words the author actually wrote."""
        body = "# Note\n\nWe ship from Canada.\n"
        review, _ = generator.compose_repair(self.site, body, "research peptides")
        if review["status"] != "pass":
            self.assertIn("ship from Canada", review["text"])


class KeywordSafetyTests(TestCase):
    def test_no_shipped_keyword_trips_its_own_guardrail(self):
        """A keyword the writer must include, that the scanner must reject, is
        a permanent flag. `batch tested research compounds` was one for weeks."""
        from . import keywords
        every = list(keywords.DEFAULT_CA) + list(keywords.DEFAULT_US)
        for lane in keywords.BY_DOMAIN.values():
            every += list(lane)
        for kw in every:
            with self.subTest(keyword=kw):
                self.assertEqual(guardrails.scan(kw)[0], [], f"{kw!r} trips a guardrail")

    def test_for_site_filters_an_unwritable_keyword(self):
        from . import keywords
        site = Site.objects.create(domain="kwsafe.ca", brand_name="KW", theme="biolabs",
                                   country="CA", is_active=True)
        keywords.BY_DOMAIN["kwsafe.ca"] = ["batch tested compounds", "peptide storage"]
        try:
            self.assertEqual(keywords.for_site(site), ["peptide storage"])
        finally:
            del keywords.BY_DOMAIN["kwsafe.ca"]

    def test_for_site_never_returns_empty(self):
        from . import keywords
        site = Site.objects.create(domain="kwempty.com", brand_name="KW", theme="biolabs",
                                   country="US", is_active=True)
        keywords.BY_DOMAIN["kwempty.com"] = ["batch tested compounds"]
        try:
            self.assertTrue(keywords.for_site(site))
        finally:
            del keywords.BY_DOMAIN["kwempty.com"]


class MetaDescriptionTests(TestCase):
    """The description stored on a post used to be the first 300 characters of
    the body — which, because the body opens with its own H1, meant every
    description in the network began by repeating the title and then stopped
    mid-word."""

    def test_summary_skips_the_title_and_headings(self):
        body = ("# Reconstitution of research peptides\n\n"
                "Lyophilised material is reconstituted with bacteriostatic water "
                "before any bench work, and the vial is labelled immediately.\n\n"
                "## Storage\n\nKeep the vial cold.\n")
        s = generator.summarise(body, "Reconstitution of research peptides")
        self.assertFalse(s.lower().startswith("reconstitution of research peptides"))
        self.assertNotIn("#", s)
        self.assertTrue(s.startswith("Lyophilised material"))

    def test_summary_trims_on_a_word_boundary(self):
        body = "# T\n\n" + ("supplier documentation " * 40)
        s = generator.summarise(body, "T", limit=158)
        self.assertLessEqual(len(s), 159)
        self.assertTrue(s.endswith("…"))
        self.assertNotIn("suppli…", s)

    def test_summary_strips_inline_markdown_and_links(self):
        body = "# T\n\nSee the **catalogue** and the [shipping policy](/shipping/) page.\n"
        s = generator.summarise(body, "T")
        self.assertNotIn("*", s)
        self.assertNotIn("](", s)
        self.assertIn("shipping policy", s)


class TitleComplianceTests(TestCase):
    """The repair loop scanned the body and nothing else.

    Seventeen posts came out of the first production run marked `pass` while
    their titles still read "High Purity Peptides Canada", "Mass-Spec Verified
    Peptides" and "Lab Verified Peptides Canada" — the claim removed from the
    prose, still sitting in the one string Google renders verbatim.
    """

    def setUp(self):
        self.site = Site.objects.create(
            domain="title-test.ca", brand_name="Title Test", theme="biolabs",
            country="CA", is_active=True)
        filler = ("Researchers should record the vial size, the storage "
                  "temperature and the date of receipt before any bench work. ")
        self.clean_body = ("# Evaluating a research supplier\n\n" + filler * 40)

    def test_a_clean_title_is_returned_unchanged(self):
        out = generator.repair_title(self.site, self.clean_body,
                                     "Evaluating a research supplier", "peptides")
        self.assertEqual(out, "Evaluating a research supplier")

    def test_a_bad_title_falls_back_to_the_scrubbed_h1(self):
        """The H1 survived the scrub, so it is already known clean — try it
        before spending an API call."""
        out = generator.repair_title(self.site, self.clean_body,
                                     "High Purity Peptides Canada", "peptides")
        self.assertEqual(out, "Evaluating a research supplier")
        self.assertEqual(guardrails.scan(out)[0], [])

    def test_an_unfixable_title_returns_empty_so_the_post_stays_flagged(self):
        """With AI stubbed and no clean H1 there is no compliant title to be
        had, and publishing beats nothing is NOT the trade here."""
        body = "## Mass-Spec Verified Peptides\n\nSome prose about vials.\n"
        self.assertEqual(
            generator.repair_title(self.site, body, "HPLC Purity Testing", "x"), "")

    def test_scan_catches_the_real_titles_that_slipped_through(self):
        for title in ("High Purity Peptides Canada: Understanding Analytical Standards",
                      "Mass-Spec Verified Peptides: Understanding Documentation",
                      "Lab Verified Peptides Canada: Understanding Analytical Standards",
                      "Reference Grade Research Peptides: Understanding Standards",
                      "HPLC Purity Testing for Peptides: What Researchers Need to Know"):
            with self.subTest(title=title):
                self.assertTrue(guardrails.scan(title)[0], f"{title!r} should flag")

    def test_repair_posts_selects_a_passing_post_with_a_bad_title(self):
        """The command used to filter on compliance_status='flagged', so a post
        whose body was already repaired dropped out of the queue with its bad
        title intact. The scanner is the authority, not the stored status."""
        from apps.blog.management.commands.repair_posts import Command
        post = BlogPost.objects.create(
            site=self.site, title="High Purity Peptides Canada", slug="hp",
            body=self.clean_body, excerpt="x", meta_description="x",
            seo_title="High Purity Peptides Canada",
            status="needs_review", compliance_status="pass")
        self.assertTrue(Command._fails(post))
        post.title = post.seo_title = "Evaluating a research supplier"
        self.assertFalse(Command._fails(post))


class HeadlineCleanupTests(TestCase):
    """A model asked for "the headline alone" still wraps it.

    Three titles in the first live run reached the database as
    "# Peptides for Laboratory Research: Analytical Standards" — the markdown
    hash included, which is what would have been rendered inside <title>.
    """

    def test_strips_a_markdown_heading_marker(self):
        self.assertEqual(
            generator._clean_headline("# Peptides for Laboratory Research"),
            "Peptides for Laboratory Research")
        self.assertEqual(generator._clean_headline("###   Deep heading"),
                         "Deep heading")

    def test_strips_quotes_and_a_label(self):
        self.assertEqual(generator._clean_headline('"A Quoted Headline"'),
                         "A Quoted Headline")
        self.assertEqual(generator._clean_headline("Title: A Labelled Headline"),
                         "A Labelled Headline")
        self.assertEqual(generator._clean_headline("“Smart quotes”"),
                         "Smart quotes")

    def test_keeps_only_the_first_line(self):
        self.assertEqual(
            generator._clean_headline("The Real One\nAn alternative\nAnother"),
            "The Real One")

    def test_does_not_eat_characters_the_way_lstrip_would(self):
        """`lstrip("#")` strips characters, not a prefix — the same trap that
        turned "where-do-i-get-peptides.ca".lstrip("www.") into
        "here-do-i-get-peptides.ca"."""
        self.assertEqual(generator._clean_headline("Handling Hashes # In Titles"),
                         "Handling Hashes # In Titles")

    def test_empty_input_is_empty_output(self):
        for value in ("", "   ", None):
            self.assertEqual(generator._clean_headline(value), "")


class PublishTimeRescanTests(TestCase):
    """The scheduler trusted a verdict that could be weeks old.

    `compliance_status` records what the rules said on the day a draft was
    written, and blog_tick drains a backlog that is weeks deep. At 04:14 UTC on
    2026-08-15 it published a post generated 2026-07-28 and marked `pass` under
    the guardrails of that day, putting "≥95% purity", "Certificate of Analysis"
    and "HPLC" live on smashfatbiolabs.com. rescan_posts caught it after the
    fact; these tests are the version that stops it going out.
    """

    def setUp(self):
        self.site = Site.objects.create(
            domain="tick-rescan.ca", brand_name="Tick Rescan", theme="biolabs",
            country="CA", is_active=True)

    def _draft(self, **kwargs):
        defaults = dict(
            site=self.site, slug=f"d{BlogPost.objects.count()}",
            title="A clean title", seo_title="A clean title",
            excerpt="Clean excerpt.", meta_description="Clean description.",
            body="# A clean title\n\nOrdinary prose about vials.\n",
            status="needs_review", compliance_status="pass")
        defaults.update(kwargs)
        return BlogPost.objects.create(**defaults)

    def test_a_clean_draft_is_publishable(self):
        from apps.blog.management.commands.blog_tick import publishable
        self.assertTrue(publishable(self._draft()))

    def test_a_stale_pass_is_not_publishable(self):
        from apps.blog.management.commands.blog_tick import publishable
        post = self._draft(body="# T\n\nEvery batch is HPLC tested to ≥99% purity.\n")
        self.assertEqual(post.compliance_status, "pass")   # what the DB claims
        self.assertFalse(publishable(post))                # what the rules say

    def test_a_stale_pass_in_the_title_alone_is_caught(self):
        from apps.blog.management.commands.blog_tick import publishable
        self.assertFalse(publishable(self._draft(title="High Purity Peptides Canada")))
        self.assertFalse(publishable(self._draft(seo_title="Mass-Spec Verified Peptides")))
        self.assertFalse(publishable(self._draft(meta_description="≥99% pure.")))

    def test_blog_tick_demotes_a_stale_draft_instead_of_publishing_it(self):
        stale = self._draft(slug="stale",
                            body="# T\n\nA batch-specific certificate of analysis "
                                 "is available on request.\n")
        call_command("blog_tick", "--force", "--site", self.site.domain, verbosity=0)
        stale.refresh_from_db()
        self.assertEqual(stale.status, "needs_review")
        self.assertEqual(stale.compliance_status, "flagged")
        self.assertIn("re-scanned at publish time", stale.compliance_notes)

    def test_blog_tick_still_publishes_the_clean_one_behind_it(self):
        self._draft(slug="stale2", body="# T\n\nEvery batch is HPLC tested.\n")
        clean = self._draft(slug="clean2")
        call_command("blog_tick", "--force", "--site", self.site.domain, verbosity=0)
        clean.refresh_from_db()
        self.assertEqual(clean.status, "published")
