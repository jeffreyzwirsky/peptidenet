"""Generate OpenAI hero images for blog posts (replaces the stock Canva pool with
a real per-post image). Requires PEPTIDENET_AI_LIVE=1 + OPENAI_API_KEY on the box
(and `pip install openai`). Offline it no-ops gracefully and tells you why.

  python manage.py generate_blog_images                 # posts without an AI image
  python manage.py generate_blog_images --all           # regenerate every post
  python manage.py generate_blog_images --site smashfat.ca
"""
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.ai import images
from apps.blog.models import BlogPost


class Command(BaseCommand):
    help = "Generate OpenAI hero images for blog posts (falls back cleanly when AI is offline)."

    def add_arguments(self, parser):
        parser.add_argument("--site", default="", help="Limit to one domain.")
        parser.add_argument("--all", action="store_true",
                            help="Regenerate even posts that already have an AI image.")

    def handle(self, *args, **opts):
        qs = BlogPost.objects.select_related("site")
        if opts["site"]:
            qs = qs.filter(site__domain=opts["site"])
        done = skipped = offline = 0
        for p in qs:
            if p.hero_image.startswith("/static/blog/ai-") and not opts["all"]:
                skipped += 1
                continue
            accent = (p.site.palette or {}).get("accent", "#4f8ff7")
            img = images.generate_blog_image(
                p.keyword or p.title, site=p.site, accent=accent,
                slug=p.slug or slugify(p.title))
            if img:
                p.hero_image = img
                p.save(update_fields=["hero_image"])
                done += 1
                self.stdout.write(f"  {p.site.domain}: {p.slug} -> {img}")
            else:
                offline += 1
        if offline and not done:
            self.stdout.write(self.style.WARNING(
                "No images generated - AI is offline. Set PEPTIDENET_AI_LIVE=1 + "
                "OPENAI_API_KEY (and pip install openai) on the server, then re-run."))
        self.stdout.write(self.style.SUCCESS(
            f"AI blog images: {done} generated, {skipped} already had one, "
            f"{offline} skipped (AI offline)."))
