"""Scan every user-visible text surface on the network against the guardrails.

The lesson of 2026-08-15, learned four separate times in one day: **a fix is only
as wide as the thing you actually scanned.**

- The blog repair loop scanned `body`, so 17 posts kept non-compliant titles.
- `blog_tick` scanned nothing at publish time, so a draft written under July's
  rules went live under August's.
- `rescan_posts` scans blog posts, so nothing ever looked at `Site` rows — and
  "Lab-verified research compounds" sat in peptidesalberta.ca's homepage meta
  description, one clause away from "Sold uncharacterised", for weeks.
- The scanner itself required whitespace before the verb, so "lab verified" was
  caught and "Lab-verified" was not.

Every one of those is the same bug at a different scale, and the answer is not
another targeted patch. It is one command that enumerates *every* place text
reaches a reader and holds all of it to the same rules — so a new surface has to
be deliberately excluded rather than accidentally forgotten.

    python manage.py compliance_check              # everything, report + exit 1
    python manage.py compliance_check --surface site
    python manage.py compliance_check --rendered   # also scan rendered HTML
    python manage.py compliance_check --quiet      # only failures

Exit code is 1 when anything fails, so it gates a deploy or a cron job.
"""
import re

from django.core.management.base import BaseCommand
from django.test import Client

from apps.blog import guardrails

# Text inside a rendered page that belongs to the scanner's own machinery — the
# compliance notes in the console, the disclaimer itself — would otherwise be
# reported as violations of the rules it is stating.
_RENDERED_STRIP = re.compile(
    r"<script.*?</script>|<style.*?</style>|<!--.*?-->", re.S | re.I)
_TAGS = re.compile(r"<[^>]+>")


# Reviewed false positives.
#
# The rule here matters more than the entries: **never widen a compliance regex
# to silence a false positive in one place**, because that weakens it in every
# other place too — including the places nobody has looked at yet. Record the
# exemption instead, with the reason, and let it be re-read.
#
# Keyed by (surface prefix, rule label, matched snippet). A test asserts every
# entry still matches something, so an exemption that outlives the copy it was
# written for gets deleted rather than quietly widening coverage forever.
ACCEPTED = {
    ("region/calgary", "medical/therapeutic claim", "prevent"):
        "\"Both are cheap to prevent at checkout\" — ordinary English about "
        "delivery mishaps, not a claim that a compound prevents anything.",
    ("region/british-columbia", "medical/therapeutic claim", "treats"):
        "\"if an approval process treats analytical documentation as a "
        "precondition\" — the ordinary verb, same reason 'treated' is already "
        "excluded from the pattern.",
    ("region/medicine-hat", "human use / dosing", "take it"):
        "Parcel-handling advice — take it inside, out of the sun. Nothing to "
        "do with administering a compound.",
    ("region/vancouver", "human use / dosing", "take it"):
        "Parcel-handling advice after a delivery is rained on.",
}


class Command(BaseCommand):
    help = "Scan every user-visible text surface against the compliance guardrails."

    SURFACES = ("site", "category", "region", "policy", "product", "blog", "keyword")

    def add_arguments(self, parser):
        parser.add_argument("--surface", default="", choices=("",) + self.SURFACES,
                            help="Limit to one surface (default: all).")
        parser.add_argument("--rendered", action="store_true",
                            help="Also fetch and scan the rendered HTML of every "
                                 "sitemap URL. Slower, but it is the only check "
                                 "that sees text hardcoded in a theme template.")
        parser.add_argument("--quiet", action="store_true",
                            help="Print only failures.")
        parser.add_argument("--allow-empty", action="store_true",
                            help="Permit a surface to scan zero items. Use only "
                                 "when you know why it is empty (e.g. a dev "
                                 "database with no blog posts).")

    # -----------------------------------------------------------------
    def handle(self, *args, **opts):
        self.failures = []
        self.checked = 0
        self.counts = {}
        self.quiet = opts["quiet"]
        wanted = (opts["surface"],) if opts["surface"] else self.SURFACES

        for surface in wanted:
            before = self.checked
            getattr(self, f"_check_{surface}")()
            scanned = self.checked - before
            self.counts[surface] = scanned
            if scanned == 0 and not opts["allow_empty"]:
                # C2 check 5, earned here on 2026-08-15: this command reported
                # "727 text surfaces, 0 failures" from a dev database with no
                # blog posts in it. The `blog` surface scanned NOTHING, and the
                # total read as network-wide coverage when it excluded all 60
                # published posts. A zero means the path or the filter is wrong
                # far more often than it means the answer is zero, and a clean
                # bill of health from a surface that looked at nothing is worse
                # than no check at all.
                self.failures.append((surface, "EMPTY SURFACE", []))
                self.stdout.write(self.style.ERROR(
                    f"  ✗ {surface}: scanned 0 items — this surface is empty or "
                    "mis-wired. Pass --allow-empty only if you know why."))
        if opts["rendered"]:
            self._check_rendered()

        self.stdout.write("")
        if self.failures:
            breakdown = " · ".join(f"{k}={v}" for k, v in self.counts.items())
            self.stdout.write(self.style.ERROR(
                f"compliance_check: {len(self.failures)} failure(s) "
                f"across {self.checked} text surfaces ({breakdown})"))
            raise SystemExit(1)
        # State the pattern set with the count, always — a bare total invites
        # exactly the misreading that produced this rule.
        breakdown = " · ".join(f"{k}={v}" for k, v in self.counts.items())
        self.stdout.write(self.style.SUCCESS(
            f"compliance_check: {self.checked} text surfaces, 0 failures "
            f"({breakdown})"))

    # -----------------------------------------------------------------
    def _scan(self, where, label, text):
        """Scan one string. `where` groups the report, `label` identifies it."""
        self.checked += 1
        hard, _ = guardrails.scan(text or "")
        hard = [(rule, snip) for rule, snip in hard
                if (where, rule, snip.lower()) not in ACCEPTED]
        if not hard:
            return
        self.failures.append((where, label, hard))
        self.stdout.write(self.style.ERROR(f"  ✗ {where} · {label}"))
        for rule, snippet in hard[:6]:
            self.stdout.write(f"      {rule}: “{snippet}”")

    def _heading(self, name):
        if not self.quiet:
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n=== {name} ==="))

    # --- the surfaces -------------------------------------------------
    def _check_site(self):
        """Site rows. Every one of these renders on a homepage."""
        from apps.stores.models import Site
        self._heading("Site rows (brand, tagline, meta description)")
        for site in Site.objects.all().order_by("domain"):
            for field in ("brand_name", "tagline", "meta_description",
                          "shipping_notice", "customs_notice"):
                self._scan(site.domain, field, getattr(site, field, "") or "")

    def _check_category(self):
        from apps.catalog import copy
        self._heading("Category copy + per-site framing")
        for slug, block in copy.CATEGORIES.items():
            self._scan(f"category/{slug}", "lede", block["lede"])
            for i, para in enumerate(block["body"]):
                self._scan(f"category/{slug}", f"body[{i}]", para)
            for i, note in enumerate(block.get("considerations", [])):
                self._scan(f"category/{slug}", f"consideration[{i}]", note)
        for domain, para in copy.SITE_FRAMING.items():
            self._scan(f"framing/{domain}", "paragraph", para)

    def _check_region(self):
        from apps.stores import regions
        self._heading("Region pages")
        for r in getattr(regions, "REGIONS", []):
            for key in ("title", "meta_description", "intro", "body"):
                value = r.get(key)
                if isinstance(value, str):
                    self._scan(f"region/{r.get('slug')}", key, value)
                elif isinstance(value, (list, tuple)):
                    for i, part in enumerate(value):
                        self._scan(f"region/{r.get('slug')}", f"{key}[{i}]", str(part))
            # Q and A scan as ONE string. A reader never meets the question
            # "Do you provide a certificate of analysis?" without the answer
            # "No. Nothing of that kind exists here to send" — and neither
            # should the scanner, whose negation escape needs the cue nearby.
            # Splitting them produced four false positives on copy that is not
            # merely compliant but is the compliance message.
            for i, faq in enumerate(r.get("faqs", []) or []):
                pair = f"{faq.get('q', '')} {faq.get('a', '')}"
                self._scan(f"region/{r.get('slug')}", f"faq[{i}]", pair)

    def _check_policy(self):
        from apps.stores import policies
        from apps.stores.models import Site
        self._heading("Policy pages")
        site = Site.objects.filter(is_active=True).first()
        if site is None:
            return
        for slug in getattr(policies, "POLICY_SLUGS", []):
            doc = policies.get(slug, site)
            if not doc:
                continue
            self._scan(f"policy/{slug}", "title", doc.get("title", ""))
            self._scan(f"policy/{slug}", "summary", doc.get("summary", ""))
            for i, section in enumerate(doc.get("sections", []) or []):
                self._scan(f"policy/{slug}", f"section[{i}].heading",
                           section.get("heading", ""))
                for j, para in enumerate(section.get("body", []) or []):
                    self._scan(f"policy/{slug}", f"section[{i}].body[{j}]", str(para))

    def _check_product(self):
        from apps.catalog.models import Product
        self._heading("Product catalogue")
        for p in Product.objects.filter(is_active=True).only(
                "name", "slug", "description", "research_area", "purity"):
            for field in ("name", "description", "research_area", "purity"):
                self._scan(f"product/{p.slug}", field, getattr(p, field, "") or "")

    def _check_blog(self):
        from apps.blog.models import BlogPost
        self._heading("Published blog posts")
        for post in BlogPost.objects.filter(status="published").select_related("site"):
            for field in ("title", "seo_title", "excerpt", "meta_description", "body"):
                self._scan(f"{post.site.domain}/blog/{post.slug}", field,
                           getattr(post, field, "") or "")

    def _check_keyword(self):
        """A keyword the writer is told to include, that the scanner rejects,
        is a permanently flagged post. `batch tested research compounds` was one
        for weeks before anyone noticed."""
        from apps.blog import keywords
        self._heading("Blog keyword lanes")
        lanes = dict(keywords.BY_DOMAIN)
        lanes["_default_ca"] = keywords.DEFAULT_CA
        lanes["_default_us"] = keywords.DEFAULT_US
        for lane, kws in lanes.items():
            for kw in kws:
                self._scan(f"keywords/{lane}", kw, kw)

    def _check_rendered(self):
        """The only check that sees copy hardcoded in a theme template.

        Everything above reads the database or a Python module. A claim typed
        directly into `templates/themes/<t>/home.html` is invisible to all of
        it, and the homepage is the highest-traffic page on every domain.
        """
        import xml.etree.ElementTree as ET

        from apps.stores.models import Site
        self._heading("Rendered HTML (theme templates + everything above)")
        client = Client()
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        for site in Site.objects.filter(is_active=True).order_by("domain"):
            try:
                sm = client.get("/sitemap.xml", HTTP_HOST=site.domain, secure=True)
                urls = [re.sub(r"^https?://[^/]+", "", (loc.text or "").strip())
                        for loc in ET.fromstring(sm.content).findall(".//s:url/s:loc", ns)]
            except Exception as e:
                self.stdout.write(self.style.WARNING(
                    f"  {site.domain}: could not read sitemap ({e})"))
                continue
            for url in urls:
                try:
                    r = client.get(url, HTTP_HOST=site.domain, secure=True)
                except Exception:
                    continue
                if r.status_code != 200:
                    continue
                html = r.content.decode("utf-8", "replace")
                text = _TAGS.sub(" ", _RENDERED_STRIP.sub(" ", html))
                text = " ".join(text.split())
                self._scan(f"{site.domain}{url}", "rendered text", text)
