"""Minify the collected CSS in STATIC_ROOT, in place, after collectstatic.

  python manage.py minify_css            # minify anything not already minified
  python manage.py minify_css --check    # report only, change nothing (exit 1 if work is pending)
  python manage.py minify_css --force    # re-minify everything

Run AFTER `collectstatic`, never before: collectstatic copies the readable
sources over the top of whatever is here, so the order is copy-then-minify. Both
are in scripts/update.sh in that order. Sources under static/ are never touched
— the repo keeps CSS a human can read, and re-running is idempotent because
rcssmin on already-minified input is a no-op.

Why rcssmin and not clean-css / a hand-rolled regex:

  Measured on this codebase's 11 stylesheets, 2026-08-16. The number that
  matters is bytes ON THE WIRE, so it is measured after compression, and against
  brotli because that is what Cloudflare actually serves:

    flagship homepage CSS (base.css + biolabs/theme.css)
      brotli            19.62 KB
      rcssmin + brotli  12.29 KB     -7.34 KB  (-37.4%)

    rcssmin + gzip      14.02 KB
    clean-css -O2 + gzip 14.01 KB    <- 10 bytes better, network-wide

  clean-css's extra 10 bytes come from selector merging and rule restructuring,
  which can change cascade order and is the kind of change that breaks one of
  eight themes in a way nobody notices for a month. rcssmin only removes
  comments and collapses whitespace; it cannot reorder a rule. Ten bytes is not
  worth that, and rcssmin is pure Python, so the box gains no Node runtime.

A hand-rolled regex was rejected outright: CSS minification has to understand
strings, url() tokens, data: URIs and `content:` values, and getting any of
those wrong corrupts a stylesheet silently.

ONE known rcssmin behaviour, found by testing it rather than by trusting it:
it strips whitespace INSIDE url() tokens, so `url("/static/x y.png")` becomes
`url("/static/xy.png")` — a broken path. Quoted `content:` strings are left
alone; this is specific to url(). Today it cannot bite: these 11 stylesheets
contain **zero** url() tokens (all 41 background declarations are gradients,
and no file under static/ has a space in its name). Verified with a control —
the same search finds 112 @media tokens in the same files, so that zero is a
real absence and not a broken grep. Because "today" is not "forever", every
file's url() tokens are compared before and after below, and a file whose
tokens changed is left untouched and reported loudly.
"""
import re
from pathlib import Path

# Whole url(...) tokens, so a change inside one is detectable.
_URL_TOKEN = re.compile(r"url\([^)]*\)", re.I)

from django.conf import settings
from django.core.management.base import BaseCommand

# A file already at or below this ratio of its own stripped length is treated as
# minified. Only used for reporting; rcssmin is idempotent either way.
ALREADY_MIN_RATIO = 1.02


class Command(BaseCommand):
    help = "Minify collected CSS in STATIC_ROOT (run after collectstatic)."

    def add_arguments(self, parser):
        parser.add_argument("--check", action="store_true",
                            help="Report only; write nothing. Exit 1 if bytes are still recoverable.")
        parser.add_argument("--force", action="store_true",
                            help="Re-minify every file, even ones that look done.")

    def handle(self, *args, **opts):
        try:
            import rcssmin
        except ImportError:
            # Not a clean result. A missing minifier must never look like
            # "nothing to save" — that is the failure-as-absence pattern that
            # hid the empty voicemail transcripts for a month.
            self.stderr.write(self.style.ERROR(
                "rcssmin is not installed — NOTHING WAS MINIFIED. It is in "
                "requirements.txt; run pip install -r requirements.txt. This is "
                "a failure, not a no-op."))
            raise SystemExit(1)

        root = Path(getattr(settings, "STATIC_ROOT", "") or "")
        if not root or not root.is_dir():
            self.stderr.write(self.style.ERROR(
                f"STATIC_ROOT ({root or 'unset'}) is not a directory — run "
                "collectstatic first. Nothing was minified."))
            raise SystemExit(1)

        files = sorted(root.rglob("*.css"))
        if not files:
            # A zero here is a claim about the search, not about the world.
            self.stderr.write(self.style.ERROR(
                f"No .css found under {root}. Nothing was checked — this is NOT "
                "a clean result."))
            raise SystemExit(1)

        saved = done = skipped = 0
        for p in files:
            try:
                src = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as e:
                self.stderr.write(self.style.WARNING(f"  skipped {p.name}: {e}"))
                skipped += 1
                continue
            out = rcssmin.cssmin(src)

            # Refuse rather than corrupt. rcssmin strips whitespace inside
            # url(), which silently breaks a path containing a space. If the
            # url() tokens are not identical before and after, this file does
            # not get written — a loud skip beats a stylesheet that looks fine
            # and 404s one background image.
            if _URL_TOKEN.findall(src) != _URL_TOKEN.findall(out):
                self.stderr.write(self.style.ERROR(
                    f"  REFUSED {p.relative_to(root)}: minification altered a "
                    "url() token. Left unminified. Check for a space or an "
                    "unquoted special character inside url()."))
                skipped += 1
                continue

            delta = len(src.encode()) - len(out.encode())
            if delta <= 0 and not opts["force"]:
                continue
            saved += delta
            done += 1
            if not opts["check"]:
                p.write_text(out, encoding="utf-8")
            if delta > 512:
                self.stdout.write(
                    f"  {p.relative_to(root)}: {len(src):,} -> {len(out):,} "
                    f"(-{delta:,} B)")

        verb = "recoverable" if opts["check"] else "removed"
        msg = (f"minify_css: {done} file(s) of {len(files)} scanned, "
               f"{saved:,} bytes {verb}"
               + (f", {skipped} unreadable" if skipped else "") + ".")

        if opts["check"] and saved:
            self.stderr.write(self.style.ERROR(
                msg + " Run without --check, or collectstatic ran after minify_css."))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS(msg))
