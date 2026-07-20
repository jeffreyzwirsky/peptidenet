"""Assign real lab hero images to blog posts (round-robin from the Canva pool).

  python manage.py assign_blog_images          # only posts without an image
  python manage.py assign_blog_images --all     # reassign every post

Images live at /static/blog/blog-1..4.jpg (curled onto the box from Canva)."""
from django.core.management.base import BaseCommand

from apps.blog.models import BlogPost, BLOG_HERO_POOL


class Command(BaseCommand):
    help = "Assign real hero images to blog posts from the lab-image pool."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true",
                            help="Reassign even posts that already have an image.")

    def handle(self, *args, **opts):
        n = 0
        for i, p in enumerate(BlogPost.objects.all().order_by("id")):
            if opts["all"] or not p.hero_image:
                p.hero_image = BLOG_HERO_POOL[i % len(BLOG_HERO_POOL)]
                p.save(update_fields=["hero_image"])
                n += 1
        self.stdout.write(self.style.SUCCESS(f"Assigned hero images to {n} post(s)."))
