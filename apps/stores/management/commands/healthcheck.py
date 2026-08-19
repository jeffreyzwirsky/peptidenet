"""The standing loop: everything that must stay true, checked on a timer.

Three silent failures on 2026-08-14 and a fourth on 2026-08-15 share one shape —
nothing was watching. The origin served 520s for 35 minutes, the bot-trap banned
186 innocent visitors, the security audit trail died for three days, and a blog
post published a purity claim at 04:14 UTC. Every one was found because a human
happened to look, hours or days later.

This is what looks instead. It runs the checks that already exist, from the box
that already has the code and the database, on a timer, and emails when
something is wrong:

  1. **Reachability** — every domain, over the real nginx/Cloudflare stack.
     The only check that sees a missing 443 vhost or an edge misconfiguration.
  2. **rescan_posts** — published posts re-scanned against TODAY'S guardrails.
  3. **compliance_check** — every user-visible text surface on the network.
  4. **seo_audit** — every URL in every sitemap.

    python manage.py healthcheck                # report, email only on failure
    python manage.py healthcheck --email always # email regardless
    python manage.py healthcheck --no-email     # print only
    python manage.py healthcheck --quick        # skip the full SEO crawl

Exit code is 1 if anything failed, so systemd records it and `OnFailure=` fires.
"""
import io
import re
import urllib.error
import urllib.request
from contextlib import redirect_stdout

from django.core.management import call_command
from django.core.management.base import BaseCommand

# Checked on every domain. Cheap, and between them they catch the failures that
# have actually happened here: origin down, blog broken, sitemap unparseable,
# robots.txt replaced at the edge.
PATHS = ("/", "/blog/", "/sitemap.xml", "/robots.txt")
TIMEOUT = 25


class Command(BaseCommand):
    help = "Run every standing check and alert when one fails."

    def add_arguments(self, parser):
        parser.add_argument("--email", choices=("auto", "always", "never"),
                            default="auto",
                            help="auto (default) emails only on failure.")
        parser.add_argument("--no-email", action="store_const", const="never",
                            dest="email", help="Alias for --email never.")
        parser.add_argument("--quick", action="store_true",
                            help="Skip the full sitemap crawl.")

    # -----------------------------------------------------------------
    def handle(self, *args, **opts):
        self.results = []
        self._check_reachable()
        self._run("rescan_posts", "Published posts vs current guardrails")
        self._run("compliance_check", "Every text surface", quiet=True)
        if not opts["quick"]:
            self._run("seo_audit", "Every sitemap URL")

        failed = [r for r in self.results if not r["ok"]]
        report = self._report(failed)
        self.stdout.write(report)

        if opts["email"] == "always" or (opts["email"] == "auto" and failed):
            self._email(failed, report)
        if failed:
            raise SystemExit(1)

    # -----------------------------------------------------------------
    def _add(self, name, ok, detail):
        self.results.append({"name": name, "ok": ok, "detail": detail})
        mark = self.style.SUCCESS("  ✓") if ok else self.style.ERROR("  ✗")
        self.stdout.write(f"{mark} {name} — {detail}")

    def _check_reachable(self):
        from apps.stores.models import Site
        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Reachability ==="))
        for site in Site.objects.filter(is_active=True).order_by("domain"):
            bad = []
            for path in PATHS:
                url = f"https://{site.domain}{path}"
                req = urllib.request.Request(
                    url, headers={"User-Agent": "peptidenet-healthcheck/1.0"})
                try:
                    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                        if resp.status != 200:
                            bad.append(f"{path}={resp.status}")
                except urllib.error.HTTPError as e:
                    bad.append(f"{path}={e.code}")
                except Exception as e:
                    bad.append(f"{path}={type(e).__name__}")
            self._add(f"reachable: {site.domain}", not bad,
                      "all 200" if not bad else ", ".join(bad))

    def _run(self, command, label, **kwargs):
        """Run another management command, capturing its output and exit code."""
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n=== {label} ==="))
        buf = io.StringIO()
        ok, detail = True, ""
        try:
            with redirect_stdout(buf):
                call_command(command, stdout=buf, verbosity=0, **kwargs)
        except SystemExit as e:
            ok = not e.code
        except Exception as e:                      # a broken check is a failure
            ok, detail = False, f"{type(e).__name__}: {e}"
        out = buf.getvalue().strip().splitlines()
        if not detail:
            detail = out[-1] if out else "no output"
        # C2 check 5 again, at the harness level: "checked=0 failing=0" is not a
        # pass, it is a check that looked at nothing. rescan_posts says exactly
        # that against an empty database and reads like a clean bill of health.
        if ok and re.search(r"\bchecked=0\b|\b0 text surfaces\b", detail):
            ok = False
            detail += "  ← scanned NOTHING; treat as a failure until explained"
        self._add(command, ok, detail)
        if not ok:
            for line in self._failure_excerpt(out):
                self.stdout.write(f"      {line}")
        self.results[-1]["output"] = "\n".join(
            self._failure_excerpt(out, tail=40, limit=60))

    @staticmethod
    def _failure_excerpt(lines, tail=25, limit=40):
        """Preserve root-cause lines even when a noisy check ends in warnings."""
        priority = [line for line in lines if re.search(r"\[ERROR\]|\bERROR\b", line)]
        excerpt = priority + list(lines[-tail:])
        deduplicated = []
        for line in excerpt:
            if line not in deduplicated:
                deduplicated.append(line)
        return deduplicated[:limit]

    # -----------------------------------------------------------------
    def _report(self, failed):
        lines = ["", "=" * 60]
        if failed:
            lines.append(f"HEALTHCHECK FAILED — {len(failed)} of "
                         f"{len(self.results)} checks")
        else:
            lines.append(f"HEALTHCHECK OK — {len(self.results)} checks passed")
        lines.append("=" * 60)
        for r in self.results:
            lines.append(f"{'ok  ' if r['ok'] else 'FAIL'}  {r['name']}: {r['detail']}")
        for r in failed:
            if r.get("output"):
                lines += ["", f"--- {r['name']} ---", r["output"]]
        return "\n".join(lines)

    def _email(self, failed, report):
        try:
            from apps.mailer import mailer
            subject = ("peptidenet healthcheck FAILED — "
                       f"{len(failed)} check(s)" if failed
                       else "peptidenet healthcheck OK")
            sent = mailer.health_alert(subject, report)
            self.stdout.write(f"\nalert email: {'sent' if sent else 'not sent'}")
        except Exception as e:
            # An alerting failure must never mask the thing being alerted about.
            self.stdout.write(self.style.WARNING(f"\nalert email failed: {e}"))
