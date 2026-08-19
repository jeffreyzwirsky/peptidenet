"""Crawl every URL in every site's sitemap and report what would cost rankings.

Eight domains serving one catalogue is a structure Google is entitled to read as
a doorway network, so the on-page signals that say "these are eight separate,
genuinely different sites" are not polish here — they are the thing keeping the
network indexed at all. That makes an SEO regression expensive and invisible,
which is exactly the combination worth a command rather than a checklist.

It renders each page in-process through Django's test client with the right Host
header, so it sees precisely what a crawler would be served by the origin, and
it is fast enough to sweep the whole network. `--live` additionally fetches each
URL over HTTP through nginx and Cloudflare, which is the only way to catch the
problems that live in front of Django — a bad 301, a missing 443 vhost, an edge
robots.txt overriding ours.

    python manage.py seo_audit                    # whole network, in-process
    python manage.py seo_audit --site smashfat.ca # one domain
    python manage.py seo_audit --live             # also fetch over the real stack
    python manage.py seo_audit --json out.json    # machine-readable

Exit code is 1 when any ERROR-level finding exists, so it can gate a deploy.
"""
import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from html.parser import HTMLParser
from urllib.parse import urlsplit

from django.core.management.base import BaseCommand
from django.test import Client

from apps.stores.models import Site

# Google truncates a title around 580px (~60 characters) and a description
# around 155–160. Under-length is not an error — an honest short title beats a
# padded one — but a title that gets cut mid-word is a wasted result snippet.
TITLE_MAX = 60
TITLE_MIN = 15
DESC_MAX = 160
DESC_MIN = 70
THIN_WORDS = 250


class PageParser(HTMLParser):
    """Pulls the SEO-relevant surface out of a rendered page.

    Deliberately a stdlib parser rather than BeautifulSoup: this has to run on
    the production box, and an audit tool that needs its own dependency tree
    installed on prod is an audit tool that stops being run.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.headings = []          # [(level, text)]
        self.canonical = ""
        self.hreflang = []          # [(lang, href)]
        self.meta = {}              # name/property → content
        self.images = []            # [(src, alt_or_None)]
        self.links = []             # hrefs
        self.jsonld = []            # raw strings
        self.robots = ""
        self._stack = []
        self._buf = []
        self._in_title = False
        self._in_jsonld = False
        self._text = []

    # --- tags -------------------------------------------------------------
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self._in_title = True
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._stack.append(tag)
            self._buf = []
        elif tag == "link":
            rel = (a.get("rel") or "").lower()
            if rel == "canonical":
                self.canonical = a.get("href", "")
            elif rel == "alternate" and a.get("hreflang"):
                self.hreflang.append((a["hreflang"], a.get("href", "")))
        elif tag == "meta":
            key = a.get("name") or a.get("property") or ""
            if key:
                self.meta[key.lower()] = a.get("content", "")
            if (a.get("name") or "").lower() == "robots":
                self.robots = (a.get("content") or "").lower()
        elif tag == "img":
            self.images.append((a.get("src", ""), a.get("alt")))
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])
        elif tag == "script" and (a.get("type") or "").lower() == "application/ld+json":
            self._in_jsonld = True
            self._buf = []

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6") and self._stack:
            self._stack.pop()
            self.headings.append((int(tag[1]), " ".join("".join(self._buf).split())))
            self._buf = []
        elif tag == "script" and self._in_jsonld:
            self._in_jsonld = False
            self.jsonld.append("".join(self._buf))
            self._buf = []

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._stack or self._in_jsonld:
            self._buf.append(data)
        self._text.append(data)

    @property
    def text(self):
        return " ".join("".join(self._text).split())


class Command(BaseCommand):
    help = "Audit on-page SEO across every site and every URL in its sitemap."

    def add_arguments(self, parser):
        parser.add_argument("--site", default="", help="Limit to one domain.")
        parser.add_argument("--live", action="store_true",
                            help="Also fetch each URL over HTTP through the "
                                 "real nginx/Cloudflare stack.")
        parser.add_argument("--json", default="", help="Write findings to a JSON file.")
        parser.add_argument("--limit", type=int, default=0,
                            help="Cap URLs per site (0 = all). Useful for a smoke run.")

    # -----------------------------------------------------------------
    def handle(self, *args, **opts):
        self.findings = []
        self.client = Client()
        all_sites = list(Site.objects.filter(is_active=True).order_by("domain"))
        sites = all_sites
        if opts["site"]:
            sites = [site for site in all_sites if site.domain == opts["site"]]
        # A one-site audit still needs the twin in this map so it can validate
        # the declared cross-domain alternate instead of falsely reporting it
        # as inactive merely because --site narrowed the pages being audited.
        self.sites_by_domain = {site.domain: site for site in all_sites}

        # Network-wide duplicate detection needs every page seen first.
        seen_titles = defaultdict(list)
        seen_descs = defaultdict(list)
        seen_bodies = defaultdict(list)
        pages_checked = 0

        for site in sites:
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n=== {site.domain} ==="))
            urls = self._sitemap_urls(site)
            if not urls:
                self._add("ERROR", site.domain, "/sitemap.xml",
                          "sitemap is empty or unparseable")
                continue
            if opts["limit"]:
                urls = urls[:opts["limit"]]
            self.stdout.write(f"  {len(urls)} URLs in sitemap")

            self._check_infra(site, urls)
            if opts["live"]:
                self._check_live(site, urls)

            linked = set()
            for url in urls:
                page = self._audit_page(site, url)
                pages_checked += 1
                if page is None:
                    continue
                if page.title:
                    seen_titles[page.title.strip()].append(f"{site.domain}{url}")
                desc = page.meta.get("description", "").strip()
                if desc:
                    seen_descs[desc].append(f"{site.domain}{url}")
                body = re.sub(r"\W+", " ", page.text.lower())[:4000]
                if len(body) > 500:
                    seen_bodies[body].append(f"{site.domain}{url}")
                for href in page.links:
                    if href.startswith("/"):
                        linked.add(href.split("#")[0].split("?")[0])

            # A sitemap URL nothing links to is a page Google is told about but
            # given no reason to value. Home is exempt (it is the root).
            orphans = [u for u in urls if u not in linked and u != "/"]
            for u in orphans:
                self._add("WARN", site.domain, u,
                          "in sitemap but not linked from any audited page (orphan)")

        # --- cross-network duplicates -----------------------------------
        #
        # Twinned .ca/.com pairs are SUPPOSED to share a title. They serve the
        # same page to two markets and declare each other with hreflang, which
        # is the mechanism that tells Google to pick one per market rather than
        # treat them as duplicates. Flagging those buries the duplicates that
        # actually matter — the ones on unrelated domains with no hreflang
        # relationship — under 200 lines of expected noise.
        twins = self._twin_groups(sites)
        for title, where in seen_titles.items():
            if len(where) > 1 and not self._is_twin_set(where, twins):
                self._add("ERROR", "network", where[0],
                          f"duplicate <title> on {len(where)} URLs: {title[:60]!r} "
                          f"→ {', '.join(where[:4])}")
        for desc, where in seen_descs.items():
            if len(where) > 1 and not self._is_twin_set(where, twins):
                self._add("WARN", "network", where[0],
                          f"duplicate meta description on {len(where)} URLs "
                          f"→ {', '.join(where[:4])}")
        for _, where in seen_bodies.items():
            if len(where) > 1 and not self._is_twin_set(where, twins):
                self._add("ERROR", "network", where[0],
                          f"near-identical body copy on {len(where)} URLs "
                          f"→ {', '.join(where[:4])}")

        return self._report(pages_checked, opts)

    # -----------------------------------------------------------------
    @staticmethod
    def _twin_groups(sites):
        """domain → the set of domains it declares as hreflang alternates."""
        # Site.alternates() returns Site rows (self + twins), not dicts. Reading
        # it as a dict raised, and the first version of this swallowed that in a
        # bare except — so every domain looked like it had no twins and the
        # whole suppression silently did nothing. No blanket except here: if the
        # shape changes again, the audit should fail loudly rather than quietly
        # go back to reporting 290 expected duplicates.
        groups = {}
        for site in sites:
            alts = {alt.domain for alt in site.alternates()}
            groups[site.domain] = alts | {site.domain}
        return groups

    @staticmethod
    def _is_twin_set(where, twins):
        """True when every URL in the group is the same path on twinned hosts."""
        paths, domains = set(), set()
        for entry in where:
            domain = entry.split("/", 1)[0]
            paths.add(entry[len(domain):] or "/")
            domains.add(domain)
        if len(paths) != 1 or len(domains) != len(where):
            return False
        # Every domain must list every other as an alternate.
        return all(domains <= twins.get(d, set()) for d in domains)

    def _get(self, site, url):
        try:
            return self.client.get(url, HTTP_HOST=site.domain, secure=True)
        except Exception as e:                       # a 500 is itself a finding
            self._add("ERROR", site.domain, url, f"raised {type(e).__name__}: {e}")
            return None

    def _sitemap_urls(self, site):
        r = self._get(site, "/sitemap.xml")
        if r is None or r.status_code != 200:
            return []
        try:
            root = ET.fromstring(r.content)
        except ET.ParseError as e:
            self._add("ERROR", site.domain, "/sitemap.xml", f"invalid XML: {e}")
            return []
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        out, seen = [], set()
        for loc in root.findall(".//s:url/s:loc", ns):
            path = re.sub(r"^https?://[^/]+", "", (loc.text or "").strip())
            if not path:
                continue
            if path in seen:
                self._add("WARN", site.domain, path, "listed twice in the sitemap")
                continue
            seen.add(path)
            out.append(path)
        # lastmod is the field Google actually leans on for recrawl scheduling.
        if not root.findall(".//s:url/s:lastmod", ns):
            self._add("WARN", site.domain, "/sitemap.xml", "no <lastmod> on any entry")
        return out

    def _check_infra(self, site, urls):
        r = self._get(site, "/robots.txt")
        if r is None or r.status_code != 200:
            self._add("ERROR", site.domain, "/robots.txt", "not served")
        else:
            body = r.content.decode("utf-8", "replace")
            if "sitemap:" not in body.lower():
                self._add("ERROR", site.domain, "/robots.txt", "does not point at a sitemap")
            if re.search(r"^\s*disallow:\s*/\s*$", body, re.I | re.M):
                self._add("ERROR", site.domain, "/robots.txt", "disallows the whole site")
            if site.domain not in body:
                self._add("WARN", site.domain, "/robots.txt",
                          "does not name its own domain — check it is host-aware")
        for path, level in (("/llms.txt", "WARN"), ("/.well-known/security.txt", "WARN")):
            r = self._get(site, path)
            if r is None or r.status_code != 200:
                self._add(level, site.domain, path, "not served")
        # A 404 that returns 200 poisons the index with soft-404s.
        r = self._get(site, "/this-page-should-not-exist-seo-audit/")
        if r is not None and r.status_code == 200:
            self._add("ERROR", site.domain, "/<missing>", "unknown URL returns 200 (soft 404)")

    def _check_live(self, site, urls):
        """Fetch over the real stack. Catches what Django cannot see.

        Django's own rendering is blind to everything in front of it, and every
        outage this network has had lived there: an nginx config with no 443
        block, an alias host serving a duplicate instead of redirecting, and a
        Cloudflare managed robots.txt injected above ours. In-process auditing
        would have called all three of those clean.
        """
        import urllib.error
        import urllib.request

        def fetch(u):
            req = urllib.request.Request(u, headers={
                "User-Agent": "peptidenet-seo-audit/1.0 (+site owner)"})
            try:
                with urllib.request.urlopen(req, timeout=20) as resp:
                    return resp.status, resp.read().decode("utf-8", "replace"), resp.url
            except urllib.error.HTTPError as e:
                return e.code, "", u
            except Exception as e:
                self._add("ERROR", site.domain, u, f"live fetch failed: {e}")
                return None, "", u

        base = f"https://{site.domain}"
        # Sampled rather than exhaustive: one of each page type is enough to
        # catch a stack-level fault, and hammering your own origin through
        # Cloudflare is how an audit ends up in the fail2ban log.
        sample = ["/"] + [u for u in urls if u != "/"][:6]
        for path in sample:
            status, _, final = fetch(base + path)
            if status is None:
                continue
            if status != 200:
                self._add("ERROR", site.domain, path, f"live fetch returned {status}")
            elif final.rstrip("/") != (base + path).rstrip("/"):
                self._add("WARN", site.domain, path, f"live URL redirected to {final}")

        # The edge can serve a different robots.txt than Django does.
        status, body, _ = fetch(base + "/robots.txt")
        if status == 200 and body:
            low = body.lower()
            for bot in ("gptbot", "claudebot", "perplexitybot", "google-extended"):
                block = re.search(rf"user-agent:\s*{bot}\s*\n+disallow:\s*/\s*$",
                                  low, re.I | re.M)
                if block:
                    self._add("ERROR", site.domain, "/robots.txt",
                              f"{bot} is disallowed at the edge — this contradicts "
                              "the llms.txt AI-discovery strategy (check the "
                              "Cloudflare managed robots.txt toggle for this zone)")
        # www must consolidate rather than duplicate.
        status, _, final = fetch(f"https://www.{site.domain}/")
        if status == 200 and site.domain not in final.replace("www.", ""):
            self._add("ERROR", site.domain, "/",
                      f"www host does not consolidate — landed on {final}")

    def _audit_page(self, site, url):
        r = self._get(site, url)
        if r is None:
            return None
        if r.status_code != 200:
            self._add("ERROR", site.domain, url,
                      f"sitemap URL returns {r.status_code}")
            return None
        html = r.content.decode("utf-8", "replace")
        p = PageParser()
        try:
            p.feed(html)
        except Exception as e:
            self._add("WARN", site.domain, url, f"could not parse: {e}")
            return None

        add = lambda lvl, msg: self._add(lvl, site.domain, url, msg)

        # --- title ---------------------------------------------------
        title = " ".join(p.title.split())
        if not title:
            add("ERROR", "no <title>")
        else:
            if len(title) > TITLE_MAX:
                add("WARN", f"title is {len(title)} chars (>{TITLE_MAX}, will be truncated): {title[:70]!r}")
            if len(title) < TITLE_MIN:
                add("WARN", f"title is only {len(title)} chars: {title!r}")

        # --- description ---------------------------------------------
        desc = p.meta.get("description", "").strip()
        if not desc:
            add("ERROR", "no meta description")
        else:
            if len(desc) > DESC_MAX:
                add("WARN", f"meta description is {len(desc)} chars (>{DESC_MAX})")
            elif len(desc) < DESC_MIN:
                add("INFO", f"meta description is only {len(desc)} chars")
            if title and desc.lower().startswith(title.lower()[:30]):
                add("WARN", "meta description just repeats the title")

        # --- headings -------------------------------------------------
        h1s = [t for lvl, t in p.headings if lvl == 1]
        if not h1s:
            add("ERROR", "no <h1>")
        elif len(h1s) > 1:
            add("ERROR", f"{len(h1s)} <h1> elements: {h1s[:3]}")
        prev = 0
        for lvl, text in p.headings:
            if prev and lvl > prev + 1:
                add("WARN", f"heading jumps h{prev} → h{lvl} at {text[:40]!r}")
            prev = lvl
        for lvl, text in p.headings:
            if not text:
                add("WARN", f"empty h{lvl}")

        # --- canonical + hreflang ------------------------------------
        if not p.canonical:
            add("ERROR", "no canonical link")
        else:
            if not p.canonical.startswith("http"):
                add("ERROR", f"canonical is relative: {p.canonical}")
            elif site.domain not in p.canonical:
                add("ERROR", f"canonical points off-site: {p.canonical}")
            elif not p.canonical.rstrip("/").endswith(url.rstrip("/")) and url != "/":
                add("WARN", f"canonical {p.canonical} does not match {url}")
        langs = [l.lower() for l, _ in p.hreflang]
        if langs and "x-default" not in langs:
            add("WARN", "hreflang set has no x-default")
        if len(langs) != len(set(langs)):
            add("ERROR", f"duplicate hreflang values: {langs}")
        self._check_hreflang_targets(site, url, p)

        # --- social / structured data --------------------------------
        for key in ("og:title", "og:description", "og:url", "og:image"):
            if not p.meta.get(key):
                add("WARN", f"missing {key}")
        if p.meta.get("og:image") and not p.meta["og:image"].startswith("http"):
            add("ERROR", "og:image is not an absolute URL")
        if not p.jsonld:
            add("WARN", "no JSON-LD structured data")
        for raw in p.jsonld:
            try:
                json.loads(raw)
            except Exception as e:
                add("ERROR", f"invalid JSON-LD: {e}")

        # --- indexability ---------------------------------------------
        if "noindex" in p.robots:
            add("ERROR", "page is noindex but listed in the sitemap")

        # --- images ----------------------------------------------------
        missing_alt = [s for s, alt in p.images if alt is None]
        if missing_alt:
            add("WARN", f"{len(missing_alt)} <img> without an alt attribute")
        empty_src = [s for s, _ in p.images if not s]
        if empty_src:
            add("ERROR", f"{len(empty_src)} <img> with an empty src")

        # --- content depth ---------------------------------------------
        words = len(re.findall(r"[A-Za-z][A-Za-z'\-]+", p.text))
        if words < THIN_WORDS:
            add("WARN", f"thin content — {words} words")

        return p

    def _check_hreflang_targets(self, site, url, page):
        """Prove every declared localized variant exists and links back.

        A syntactically valid hreflang tag that points to a 404 is worse than
        no tag, and Google ignores one-way clusters. The old audit only checked
        duplicate language labels, so both defects could report clean.
        """
        if not page.hreflang:
            return

        source_set = {
            (lang.lower(), href.rstrip("/"))
            for lang, href in page.hreflang
        }
        source_url = f"https://{site.domain}{url}".rstrip("/")
        checked = set()
        for _, href in page.hreflang:
            parsed = urlsplit(href)
            if parsed.scheme not in ("http", "https") or not parsed.hostname:
                self._add("ERROR", site.domain, url,
                          f"hreflang target is not an absolute HTTP URL: {href}")
                continue
            target_domain = parsed.hostname.lower()
            target_site = self.sites_by_domain.get(target_domain)
            if target_site is None:
                self._add("ERROR", site.domain, url,
                          f"hreflang target is not an active storefront: {href}")
                continue
            target_path = parsed.path or "/"
            key = (target_domain, target_path)
            if key in checked:
                continue
            checked.add(key)

            if target_domain == site.domain and target_path == url:
                target_page = page
            else:
                response = self._get(target_site, target_path)
                if response is None or response.status_code != 200:
                    status = "no response" if response is None else response.status_code
                    self._add("ERROR", site.domain, url,
                              f"hreflang target returns {status}: {href}")
                    continue
                target_page = PageParser()
                try:
                    target_page.feed(response.content.decode("utf-8", "replace"))
                except Exception as exc:
                    self._add("ERROR", site.domain, url,
                              f"could not parse hreflang target {href}: {exc}")
                    continue

            target_set = {
                (lang.lower(), target_href.rstrip("/"))
                for lang, target_href in target_page.hreflang
            }
            if target_set != source_set:
                self._add("ERROR", site.domain, url,
                          f"hreflang set differs on {href}; localized versions "
                          "must publish the same reciprocal set")
            reciprocal = {
                target_href.rstrip("/")
                for lang, target_href in target_page.hreflang
                if lang.lower() == site.hreflang.lower()
            }
            if source_url not in reciprocal:
                self._add("ERROR", site.domain, url,
                          f"hreflang target does not link back: {href}")

    # -----------------------------------------------------------------
    def _add(self, level, domain, url, message):
        self.findings.append({"level": level, "site": domain,
                              "url": url, "message": message})

    def _report(self, pages_checked, opts):
        order = {"ERROR": 0, "WARN": 1, "INFO": 2}
        self.findings.sort(key=lambda f: (order[f["level"]], f["site"], f["url"]))
        counts = defaultdict(int)
        for f in self.findings:
            counts[f["level"]] += 1

        self.stdout.write(self.style.MIGRATE_HEADING("\n=== FINDINGS ==="))
        style = {"ERROR": self.style.ERROR, "WARN": self.style.WARNING,
                 "INFO": self.style.NOTICE}
        for f in self.findings:
            self.stdout.write(style[f["level"]](
                f"  [{f['level']:5}] {f['site']}{f['url']} — {f['message']}"))
        if not self.findings:
            self.stdout.write(self.style.SUCCESS("  nothing to fix."))

        self.stdout.write(self.style.SUCCESS(
            f"\nseo_audit: {pages_checked} pages · "
            f"{counts['ERROR']} errors, {counts['WARN']} warnings, "
            f"{counts['INFO']} notes."))

        if opts["json"]:
            with open(opts["json"], "w", encoding="utf-8") as fh:
                json.dump(self.findings, fh, indent=2)
            self.stdout.write(f"wrote {opts['json']}")

        if counts["ERROR"]:
            raise SystemExit(1)
