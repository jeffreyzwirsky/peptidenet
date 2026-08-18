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

from apps.blog import generator, guardrails, keywords
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


def publishable(post):
    """Re-scan against TODAY'S guardrails, not the verdict stored at writing.

    `compliance_status` is a snapshot of what the rules said on the day a draft
    was written, and this scheduler drains a backlog that is weeks old. On
    2026-08-15 at 04:14 UTC it published a post generated on 2026-07-28 and
    marked `pass` under the guardrails of that day — putting "≥95% purity",
    "Certificate of Analysis" and "HPLC" live on smashfatbiolabs.com, three
    hours before anyone looked. `rescan_posts` existed to catch exactly that
    after the fact; this stops it happening in the first place.

    Every field a crawler reads is checked, not just the body — a claim in the
    title is the most visible place it can sit.
    """
    for field in (post.title, post.seo_title, post.excerpt,
                  post.meta_description, post.body):
        if guardrails.scan(field or "")[0]:
            return False
    return True


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
        parser.add_argument("--tries", type=int, default=2,
                            help="How many keywords to attempt on a site before "
                                 "giving up for the day (default 2).")

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

            post, stale = None, 0
            for candidate in (BlogPost.objects
                              .filter(site=site, status="needs_review",
                                      compliance_status="pass")
                              .order_by("created_at")):
                if publishable(candidate):
                    post = candidate
                    break
                # The rules moved under it since it was written. Demote it so
                # the queue tells the truth and repair_posts can pick it up.
                stale += 1
                if not opts["dry_run"]:
                    candidate.compliance_status = "flagged"
                    candidate.compliance_notes = "\n".join(filter(None, [
                        candidate.compliance_notes,
                        "· re-scanned at publish time and now fails the current "
                        "guardrails — run manage.py repair_posts"]))
                    candidate.save(update_fields=["compliance_status",
                                                  "compliance_notes", "updated_at"])
            if stale:
                self.stdout.write(self.style.WARNING(
                    f"  {site.domain}: {stale} backlog draft(s) no longer pass "
                    "today's guardrails — demoted to flagged."))
            source = "backlog"
            if post is None:
                if opts["dry_run"]:
                    self.stdout.write(f"  {site.domain}: would generate + publish")
                    continue
                # Try more than one keyword before giving up on the day. The
                # generator repairs its own drafts now, so a flag that survives
                # that means the topic itself keeps steering the model into a
                # claim it is not allowed to make — and the next keyword in the
                # lane usually does not.
                kws = keywords.for_site(site)
                start = BlogPost.objects.filter(site=site).count()
                tries = max(1, min(opts["tries"], len(kws)))
                source, post = "fresh", None
                for offset in range(tries):
                    kw = kws[(start + offset) % len(kws)]
                    candidate = generator.generate(site, kw)
                    generated += 1
                    if candidate.compliance_status == "pass" and publishable(candidate):
                        post = candidate
                        break
                    flagged += 1
                    self.stdout.write(self.style.WARNING(
                        f"  {site.domain}: \"{candidate.title}\" FLAGGED "
                        f"(keyword \"{kw}\") - held in needs_review."))
                if post is None:
                    self.stdout.write(self.style.ERROR(
                        f"  {site.domain}: nothing publishable after {tries} "
                        "attempts - the lane needs a human."))
                    continue
            elif opts["dry_run"]:
                self.stdout.write(f"  {site.domain}: would publish backlog draft "
                                  f"\"{post.title}\"")
                continue

            ensure_hero_image(post)
            post.publish()
            published += 1
            self.stdout.write(self.style.SUCCESS(
                f"  {site.domain}: published ({source}) \"{post.title}\" "
                f"-> /blog/{post.slug}/"))

        self.stdout.write(self.style.SUCCESS(
            f"blog_tick: {published} published, {generated} generated, "
            f"{flagged} flagged (held for review), {skipped} skipped."))
