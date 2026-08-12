"""The blog scheduler — the one command the daily timer runs.

Policy (changed 2026-08-12 with Jeff's explicit approval): posts that PASS the
compliance guardrails now publish automatically, on a per-site cadence. Posts
that trip a hard guardrail still land in `needs_review` and wait for a human —
the guardrails remain the gate; what changed is that a clean post no longer
waits for a keystroke that never came.

Cadence: each site posts on 3 fixed weekdays derived from its domain hash, so
the 8 sites are staggered across the week instead of all posting at once
(2–3 posts/site/week). One post per site per posting day, maximum.

Order of preference on a posting day:
  1. Drain the backlog — the oldest guardrail-passing draft is published first
     (there are weeks of accumulated drafts; no need to spend API credits while
     they exist).
  2. Otherwise generate a fresh post. If it passes guardrails it publishes
     immediately; if flagged it stays in needs_review for a human.

Every published post is guaranteed a hero image: the AI-generated one from the
generator when available, else the stock lab-photo pool.

  python manage.py blog_tick               # normal daily run (cadence-aware)
  python manage.py blog_tick --force       # ignore cadence: post on every site today
  python manage.py blog_tick --site X      # limit to one domain
  python manage.py blog_tick --dry-run     # say what would happen, change nothing
"""
import zlib

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.blog import generator, keywords
from apps.blog.models import BLOG_HERO_POOL, BlogPost
from apps.stores.models import Site


def posting_days(domain):
    """3 deterministic weekdays (0=Mon..6=Sun) per domain, staggered by hash."""
    h = zlib.crc32(domain.lower().encode())
    days = {h % 7, (h // 7) % 7, (h // 49) % 7}
    step = 3
    while len(days) < 3:
        days.add((max(days) + step) % 7)
        step += 1
    return sorted(days)


def ensure_hero_image(post):
    """A published post must carry a real hero image. Prefer the AI generator
    (when live), fall back to the stock lab-photo pool. Never leaves it blank."""
    if post.hero_image:
        return
    from apps.ai import images
    accent = (post.site.palette or {}).get("accent", "#4f8ff7")
    img = images.generate_blog_image(post.keyword or post.title,
                                     site=post.site, accent=accent, slug=post.slug)
    post.hero_image = img or BLOG_HERO_POOL[
        zlib.crc32((post.keyword or post.title).encode()) % len(BLOG_HERO_POOL)]
    post.save(update_fields=["hero_image", "updated_at"])


class Command(BaseCommand):
    help = ("Cadence-aware blog scheduler: publishes guardrail-passing posts "
            "(backlog first, else generates). Flagged posts still need a human.")

    def add_arguments(self, parser):
        parser.add_argument("--site", default="", help="Limit to one domain.")
        parser.add_argument("--force", action="store_true",
                            help="Ignore the weekday cadence — treat today as a "
                                 "posting day for every selected site.")
        parser.add_argument("--dry-run", action="store_true",
                            help="Report what would happen without changing anything.")

    def handle(self, *args, **opts):
        today = timezone.localdate()
        wd = today.weekday()
        sites = Site.objects.filter(is_active=True)
        if opts["site"]:
            sites = sites.filter(domain=opts["site"])

        published = generated = flagged = skipped = 0
        for site in sites:
            days = posting_days(site.domain)
            if not opts["force"] and wd not in days:
                skipped += 1
                self.stdout.write(f"  {site.domain}: not a posting day "
                                  f"(posts on weekdays {days})")
                continue
            if BlogPost.objects.filter(site=site, status="published",
                                       published_at__date=today).exists():
                skipped += 1
                self.stdout.write(f"  {site.domain}: already published today")
                continue

            post = (BlogPost.objects
                    .filter(site=site, status="needs_review", compliance_status="pass")
                    .order_by("created_at").first())
            source = "backlog"
            if post is None:
                if opts["dry_run"]:
                    self.stdout.write(f"  {site.domain}: would generate + publish")
                    continue
                kws = keywords.for_site(site)
                kw = kws[BlogPost.objects.filter(site=site).count() % len(kws)]
                post = generator.generate(site, kw)
                generated += 1
                source = "fresh"
                if post.compliance_status != "pass":
                    flagged += 1
                    self.stdout.write(self.style.WARNING(
                        f"  {site.domain}: “{post.title}” FLAGGED by guardrails — "
                        "held in needs_review for a human."))
                    continue
            elif opts["dry_run"]:
                self.stdout.write(f"  {site.domain}: would publish backlog draft "
                                  f"“{post.title}”")
                continue

            ensure_hero_image(post)
            post.publish()
            published += 1
            self.stdout.write(self.style.SUCCESS(
                f"  {site.domain}: published ({source}) “{post.title}” "
                f"→ /blog/{post.slug}/"))

        self.stdout.write(self.style.SUCCESS(
            f"blog_tick: {published} published, {generated} generated, "
            f"{flagged} flagged (held for review), {skipped} skipped."))
