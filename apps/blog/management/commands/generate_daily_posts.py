"""Generate one DRAFT SEO post per site per day, rotating each site's keyword list.
Posts are created as `needs_review` (never published) and scanned by guardrails —
a human approves them in the control panel. Schedule this daily (Celery beat/cron
in production). Does NOT publish anything.

  python manage.py generate_daily_posts            # all active sites
  python manage.py generate_daily_posts --site smashfat.ca
"""
from django.core.management.base import BaseCommand

from apps.blog import generator, keywords
from apps.blog.models import BlogPost
from apps.stores.models import Site


class Command(BaseCommand):
    help = "Create one draft SEO blog post per site (rotating keywords). Never publishes."

    def add_arguments(self, parser):
        parser.add_argument("--site", default="", help="Limit to one domain.")

    def handle(self, *args, **opts):
        sites = Site.objects.filter(is_active=True)
        if opts["site"]:
            sites = sites.filter(domain=opts["site"])
        made = flagged = 0
        for site in sites:
            kws = keywords.for_site(site)
            # rotate by how many posts already exist for this site
            kw = kws[BlogPost.objects.filter(site=site).count() % len(kws)]
            post = generator.generate(site, kw)
            made += 1
            flagged += post.compliance_status == "flagged"
            self.stdout.write(f"  {site.domain}: “{post.title}” "
                              f"[{post.compliance_status}] (draft, needs review)")
        self.stdout.write(self.style.SUCCESS(
            f"Generated {made} draft posts ({flagged} flagged by guardrails). "
            "Review + approve them in the control panel — nothing is published automatically."
        ))
