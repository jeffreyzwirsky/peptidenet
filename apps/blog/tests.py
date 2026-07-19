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
