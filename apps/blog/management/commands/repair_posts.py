"""Rescue drafts the guardrails flagged, by showing the writer what it broke.

Every post generated before the repair loop existed got exactly one attempt and
no feedback: if the scanner found a claim, the draft was written to the database
as `flagged` and nothing ever looked at it again. Sixty-five of the network's
sixty-six drafts ended up there, and six of the eight blogs had never published
a single post — not because the guardrails were wrong, but because a gate with
nothing behind it is a wall.

This command walks that backlog and gives each draft the passes it never got:
the model is handed its own violations with a per-rule brief, and whatever
survives that goes through the deterministic sentence scrub. A draft that comes
out clean and long enough is marked `pass` and becomes publishable by the normal
scheduler; a draft that does not is left exactly as it was, with the reason
appended to its notes.

    python manage.py repair_posts --dry-run        # report only, no writes
    python manage.py repair_posts                  # repair, leave as drafts
    python manage.py repair_posts --publish        # repair and publish the winners
    python manage.py repair_posts --site smashfat.ca --limit 5

Bodies are only ever replaced by a *cleaner* version of themselves, and a post
that cannot be cleaned is never edited at all, so a run is safe to repeat.
"""
from django.core.management.base import BaseCommand

from apps.blog import guardrails
from apps.blog.generator import MIN_PUBLISH_WORDS, compose_repair
from apps.blog.models import BlogPost


class Command(BaseCommand):
    help = ("Re-run flagged drafts through the guardrail repair loop and mark "
            "the ones that come out clean as publishable.")

    def add_arguments(self, parser):
        parser.add_argument("--site", default="", help="Limit to one domain.")
        parser.add_argument("--limit", type=int, default=0,
                            help="Stop after N drafts (0 = no limit).")
        parser.add_argument("--dry-run", action="store_true",
                            help="Report what would change; write nothing.")
        parser.add_argument("--publish", action="store_true",
                            help="Publish repaired posts immediately instead of "
                                 "leaving them for the scheduler.")
        parser.add_argument("--include-published", action="store_true",
                            help="Also repair posts that are already live and "
                                 "now fail the current guardrails.")

    def handle(self, *args, **opts):
        qs = BlogPost.objects.filter(compliance_status="flagged")
        if not opts["include_published"]:
            qs = qs.filter(status="needs_review")
        if opts["site"]:
            qs = qs.filter(site__domain=opts["site"])
        qs = qs.select_related("site").order_by("site__domain", "created_at")
        if opts["limit"]:
            qs = qs[:opts["limit"]]

        repaired = published = failed = 0
        for post in qs:
            before = guardrails.review(post.body)
            review, provenance = compose_repair(post.site, post.body,
                                                post.keyword or post.title)
            words = guardrails.word_count(review["text"])
            trail = " · ".join(provenance)

            if review["status"] != "pass":
                failed += 1
                self.stdout.write(self.style.WARNING(
                    f"  ✗ {post.site.domain} “{post.title[:56]}” "
                    f"{before['hard_count']} → {review['hard_count']} issues ({trail})"))
                if not opts["dry_run"]:
                    # Record the attempt so a human reading the queue can see
                    # this was tried and what is still standing in the way.
                    post.compliance_notes = "\n".join(
                        [review["notes"], f"· repair attempted — {trail}"]).strip()
                    post.save(update_fields=["compliance_notes", "updated_at"])
                continue

            if words < MIN_PUBLISH_WORDS:
                failed += 1
                self.stdout.write(self.style.WARNING(
                    f"  ✗ {post.site.domain} “{post.title[:56]}” clean but only "
                    f"{words} words (min {MIN_PUBLISH_WORDS}) — left as a draft"))
                continue

            repaired += 1
            self.stdout.write(self.style.SUCCESS(
                f"  ✓ {post.site.domain} “{post.title[:56]}” "
                f"{before['hard_count']} → 0 issues, {words} words ({trail})"))
            if opts["dry_run"]:
                continue

            from apps.blog.generator import summarise
            post.body = review["text"]
            post.excerpt = summarise(review["text"], post.title, limit=300)
            post.meta_description = summarise(review["text"], post.title)
            post.compliance_status = "pass"
            post.compliance_notes = "\n".join(
                [review["notes"], f"· repaired — {trail}"]).strip()
            post.save(update_fields=["body", "excerpt", "meta_description",
                                     "compliance_status", "compliance_notes",
                                     "updated_at"])
            if opts["publish"] and post.status != "published":
                from apps.blog.management.commands.blog_tick import ensure_hero_image
                ensure_hero_image(post)
                post.publish()
                published += 1

        self.stdout.write(self.style.SUCCESS(
            f"repair_posts: {repaired} repaired, {published} published, "
            f"{failed} still failing."
            + (" (dry run — nothing written)" if opts["dry_run"] else "")))
