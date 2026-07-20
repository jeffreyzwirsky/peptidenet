import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.blog import guardrails
from apps.blog.models import BlogPost
from apps.stores.models import Site

# Which site each article is assigned to (one article per site -> no duplicate
# content across the network). Themes chosen for topical fit; flagship gets the
# breakout GLP-1 piece. Falls back to round-robin for anything unmapped.
TITLE_TO_THEME = {
    "Retatrutide Research": "biolabs",
    "Tirzepatide vs Semaglutide vs Retatrutide": "clinical",
    "Cagrilintide": "prairie",
    "How to Read a Peptide Certificate": "guide",
    "Peptide Reconstitution Basics": "neon",
    "BPC-157 and TB-500": "apothecary",
    "GHK-Cu": "editorial",
}


class Command(BaseCommand):
    help = "Import drafted blog posts from data/seed_posts.json as needs_review drafts."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=str(Path(settings.BASE_DIR) / "data" / "seed_posts.json"),
        )
        parser.add_argument("--replace", action="store_true",
                            help="Delete existing imported drafts with the same slug first.")

    def _site_for(self, title, fallback):
        for frag, theme in TITLE_TO_THEME.items():
            if frag.lower() in title.lower():
                s = Site.objects.filter(theme=theme).first()
                if s:
                    return s
        return fallback

    def handle(self, *args, **opts):
        data = json.loads(Path(opts["path"]).read_text(encoding="utf-8"))
        posts = data["posts"]
        sites = list(Site.objects.all().order_by("id"))
        if not sites:
            self.stderr.write("No sites — run seed_sites first.")
            return

        created = flagged = skipped = 0
        for i, p in enumerate(posts):
            site = self._site_for(p["title"], sites[i % len(sites)])
            slug = slugify(p["title"])[:200]
            if BlogPost.objects.filter(site=site, slug=slug).exists():
                if opts["replace"]:
                    BlogPost.objects.filter(site=site, slug=slug).delete()
                else:
                    skipped += 1
                    continue
            review = guardrails.review(p["body"])
            BlogPost.objects.create(
                site=site,
                title=p["title"],
                slug=slug,
                keyword=p.get("keyword", ""),
                excerpt=p.get("excerpt", "")[:320],
                body=review["text"],
                seo_title=p["title"][:200],
                meta_description=p.get("meta_description", "")[:320],
                status="needs_review",              # NEVER auto-published
                compliance_status=review["status"],
                compliance_notes=review["notes"],
                ai_generated=True,
            )
            created += 1
            if review["status"] == "flagged":
                flagged += 1
            self.stdout.write(
                f"  {site.theme:11} · {p['title'][:48]:48} [{review['status']}]"
            )
        self.stdout.write(self.style.SUCCESS(
            f"Imported {created} drafts ({flagged} flagged for review, {skipped} skipped). "
            f"All are needs_review — publish from the control panel after checking."
        ))
