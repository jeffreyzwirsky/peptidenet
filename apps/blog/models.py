from django.db import models
from django.utils.text import slugify

# Real lab hero images (curled onto the box from Canva → static/blog/).
BLOG_HERO_POOL = [
    "/static/blog/blog-1.jpg",  # cinematic clear vials + molecular bokeh
    "/static/blog/blog-2.jpg",  # macro clear research vials
    "/static/blog/blog-3.jpg",  # glowing neon vials
    "/static/blog/blog-4.jpg",  # amber vials on slate
]


class BlogPost(models.Model):
    """A per-site SEO blog post. Never auto-published — created as needs_review,
    scanned by guardrails, and only a human can publish."""

    STATUS = [
        ("needs_review", "Needs review"),
        ("published", "Published"),
        ("archived", "Archived"),
    ]
    COMPLIANCE = [("pass", "Passed guardrails"), ("flagged", "Flagged — needs fix")]

    site = models.ForeignKey("stores.Site", on_delete=models.CASCADE, related_name="posts")
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, blank=True)
    keyword = models.CharField(max_length=120, blank=True, help_text="Target SEO keyword.")
    excerpt = models.CharField(max_length=320, blank=True)
    body = models.TextField(help_text="Markdown.")
    seo_title = models.CharField(max_length=200, blank=True)
    meta_description = models.CharField(max_length=320, blank=True)
    hero_svg = models.TextField(blank=True, help_text="Inline SVG banner (fallback).")
    hero_image = models.CharField(
        max_length=300, blank=True,
        help_text="URL/path to a real hero image (e.g. /static/blog/blog-1.jpg). "
                  "Takes precedence over the SVG banner.")

    status = models.CharField(max_length=14, choices=STATUS, default="needs_review")
    compliance_status = models.CharField(max_length=8, choices=COMPLIANCE, default="pass")
    compliance_notes = models.TextField(blank=True)
    ai_generated = models.BooleanField(default=False)

    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]
        unique_together = ("site", "slug")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)[:200]
        if not self.seo_title:
            self.seo_title = self.title[:200]
        super().save(*args, **kwargs)

    @property
    def is_published(self):
        return self.status == "published"

    @property
    def can_publish(self):
        # Guardrail: a flagged post cannot be published until fixed + re-scanned.
        return self.compliance_status == "pass"

    def __str__(self):
        return f"{self.title} ({self.site.domain})"
