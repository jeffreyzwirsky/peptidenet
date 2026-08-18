"""Re-run the current guardrails against posts that are ALREADY published.

Why this exists
---------------
The guardrails only ever ran at generation time. That is fine for the post
being written and useless for the post written last month: when a new rule
lands — the origin-claim rule, the testing/COA rule, the purity-figure rule —
every post that published before it keeps serving the claim, and nothing in
the system ever looks at it again.

That is exactly what happened. On 2026-08-14 a live sweep of the network found
five of the six published posts asserting things the storefronts had already
been scrubbed of: a "documented ≥99% purity threshold", a "batch-specific
Certificate of Analysis available on request", and a shipping origin. The code
was correct and the content was stale, and there was no command that would
have told anyone.

Usage
-----
    manage.py rescan_posts                 # report only (safe, default)
    manage.py rescan_posts --unpublish     # move failing published posts back
                                           # to needs_review + flagged
    manage.py rescan_posts --all           # include drafts in the report

Unpublishing is deliberately reversible: the body is never touched, only
`status`, `compliance_status` and `compliance_notes`. Restoring a post is a
status flip in the control panel once its text is fixed.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.blog.guardrails import scan
from apps.blog.models import BlogPost


def _ascii(text):
    return str(text).encode("ascii", "replace").decode("ascii")


def _scannable(post):
    """Everything that reaches a reader, not just the body.

    A claim in the meta description is served to every search result and was
    invisible to a body-only scan.
    """
    return " ".join([
        post.title or "",
        post.excerpt or "",
        post.meta_description or "",
        post.seo_title or "",
        post.body or "",
    ])


class Command(BaseCommand):
    help = "Re-scan existing blog posts against the current compliance guardrails."

    def add_arguments(self, parser):
        parser.add_argument(
            "--unpublish", action="store_true",
            help="Move failing PUBLISHED posts back to needs_review and flag them.",
        )
        parser.add_argument(
            "--all", action="store_true",
            help="Report on drafts too, not just published posts.",
        )

    def handle(self, *args, **opts):
        qs = BlogPost.objects.select_related("site").order_by("site__domain", "slug")
        if not opts["all"]:
            qs = qs.filter(status="published")

        stamp = timezone.now().strftime("%Y-%m-%d")
        checked = failing = pulled = 0

        for post in qs:
            checked += 1
            hard, _soft = scan(_scannable(post))
            if not hard:
                continue
            failing += 1

            by_label = {}
            for label, snippet in hard:
                by_label.setdefault(label, set()).add(snippet.strip()[:40])

            self.stdout.write(self.style.WARNING(
                f"[{post.status}] https://{post.site.domain}/blog/{post.slug}/"))
            for label, snippets in sorted(by_label.items()):
                joined = ", ".join(sorted(snippets))[:160]
                self.stdout.write(f"    {label}: {_ascii(joined)}")

            if opts["unpublish"] and post.status == "published":
                notes = [
                    f"Retro-scan {stamp}: published before these guardrails existed. "
                    f"Unpublished pending rewrite."
                ]
                notes += [f"❌ {label}: {', '.join(sorted(snippets))[:160]}"
                          for label, snippets in sorted(by_label.items())]
                post.status = "needs_review"
                post.compliance_status = "flagged"
                post.compliance_notes = "\n".join(notes)
                post.save(update_fields=["status", "compliance_status", "compliance_notes"])
                pulled += 1
                self.stdout.write(self.style.ERROR("    -> unpublished"))

        still_live = BlogPost.objects.filter(status="published").count()
        summary = (f"checked={checked} failing={failing} unpublished={pulled} "
                   f"still_published={still_live}")
        self.stdout.write(self.style.SUCCESS(summary) if not failing
                          else self.style.WARNING(summary))
        if failing and not opts["unpublish"]:
            self.stdout.write("Re-run with --unpublish to take the failing posts down.")
