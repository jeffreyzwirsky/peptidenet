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
from apps.blog.generator import (MIN_PUBLISH_WORDS, compose_repair,
                                 repair_title, summarise)
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

    @staticmethod
    def _fails(post):
        """Every field a crawler or a regulator can read, not just the body.

        Selecting on `compliance_status == "flagged"` alone was not enough: a
        post whose body had already been repaired was marked `pass` and dropped
        out of the queue while its title still carried the claim. The scanner is
        the authority here, not the stored status.
        """
        for field in (post.title, post.seo_title, post.excerpt,
                      post.meta_description, post.body):
            if guardrails.scan(field or "")[0]:
                return True
        return post.compliance_status == "flagged"

    def handle(self, *args, **opts):
        qs = BlogPost.objects.all()
        if not opts["include_published"]:
            qs = qs.filter(status="needs_review")
        if opts["site"]:
            qs = qs.filter(site__domain=opts["site"])
        qs = qs.select_related("site").order_by("site__domain", "created_at")
        posts = [p for p in qs if self._fails(p)]
        if opts["limit"]:
            posts = posts[:opts["limit"]]
        self.stdout.write(f"{len(posts)} post(s) fail the current guardrails.")

        repaired = published = failed = 0
        for post in posts:
            before = guardrails.review(post.body)
            if before["status"] == "pass":
                # The body is already clean — this post is in the queue for a
                # title or a description, so do not spend four LLM calls
                # rewriting prose that has nothing wrong with it.
                review, provenance = before, ["body already clean"]
            else:
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

            # The body is clean; the title is a different column and was never
            # scanned. 17 of this backlog came out of the loop marked `pass`
            # with headlines like "High Purity Peptides Canada" and "Mass-Spec
            # Verified Peptides" — a claim in the one place Google renders
            # verbatim, on a post whose text no longer made it.
            title = repair_title(post.site, review["text"], post.title,
                                 post.keyword or "")
            if not title:
                failed += 1
                self.stdout.write(self.style.WARNING(
                    f"  ✗ {post.site.domain} “{post.title[:56]}” body is clean "
                    "but the title could not be made compliant — left flagged"))
                continue

            repaired += 1
            retitled = " · retitled" if title != post.title else ""
            self.stdout.write(self.style.SUCCESS(
                f"  ✓ {post.site.domain} “{title[:56]}” "
                f"{before['hard_count']} → 0 issues, {words} words{retitled} ({trail})"))
            if opts["dry_run"]:
                continue

            post.title = title[:200]
            post.seo_title = title[:200]
            post.body = review["text"]
            post.excerpt = summarise(review["text"], title, limit=300)
            post.meta_description = summarise(review["text"], title)
            post.compliance_status = "pass"
            post.compliance_notes = "\n".join(
                [review["notes"], f"· repaired — {trail}"]).strip()
            post.save(update_fields=["title", "seo_title", "body", "excerpt",
                                     "meta_description", "compliance_status",
                                     "compliance_notes", "updated_at"])
            if opts["publish"] and post.status != "published":
                from apps.blog.management.commands.blog_tick import ensure_hero_image
                ensure_hero_image(post)
                post.publish()
                published += 1

        self.stdout.write(self.style.SUCCESS(
            f"repair_posts: {repaired} repaired, {published} published, "
            f"{failed} still failing."
            + (" (dry run — nothing written)" if opts["dry_run"] else "")))
