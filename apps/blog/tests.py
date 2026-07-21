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
