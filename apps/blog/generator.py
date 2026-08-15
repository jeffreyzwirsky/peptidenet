"""AI blog-post generator with compliance baked into the prompt AND enforced by
the guardrail scanner afterward. Produces a DRAFT (needs_review) — never publishes."""
import re
import zlib

from django.conf import settings
from django.utils.text import slugify

from apps.ai import images, llm
from apps.catalog.models import Product

from . import guardrails, keywords
from .models import BLOG_HERO_POOL, BlogPost


def _unique_slug(site, base):
    """Per-site unique slug. Appends -2, -3, … so regenerating a keyword/title
    never trips the (site, slug) unique constraint (which used to 500 the creator)."""
    base = (base or "post")[:200]
    slug = base
    i = 2
    while BlogPost.objects.filter(site=site, slug=slug).exists():
        suffix = f"-{i}"
        slug = f"{base[:200 - len(suffix)]}{suffix}"
        i += 1
    return slug


# Google renders roughly 155–160 characters of a meta description on desktop and
# less on mobile. The old code stored the first 300 characters of the body —
# which, because the body opens with its own H1, meant every description on the
# network began by repeating the title and then cut off mid-sentence.
META_DESCRIPTION_CHARS = 158


def summarise(body, title="", limit=158):
    """A clean description drawn from the post's opening prose.

    Skips the H1, any other heading, the hero/disclaimer rules and list markers,
    strips inline markdown, and trims on a word boundary with an ellipsis rather
    than mid-word.
    """
    text_parts = []
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith(("#", "---", ">", "|", "*", "-", "_")):
            continue
        if title and s.lower().startswith(title.lower()[:40]):
            continue
        if "research use only" in s.lower():
            continue
        text_parts.append(s)
        if sum(len(p) for p in text_parts) > limit * 2:
            break
    text = " ".join(text_parts)
    text = re.sub(r"[*_`]+", "", text)                      # inline emphasis
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)     # links → their text
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:.—–-")
    return f"{cut}…"


def build_system(site):
    """Compliance prompt, built per site.

    This used to be a module-level constant that opened "You write SEO blog
    posts for a Canadian research-compound store" and asked for "Canadian
    availability/shipping" — regardless of which of the eight domains was
    calling. The four .com storefronts were therefore having Canada-targeted
    posts written for a United States audience, which quietly undid the market
    split in keywords.py.

    Rule 6 is the one worth reading twice. The network makes no statement about
    where goods ship from, in either direction, and a model writing for a
    national audience will volunteer one unless told not to.
    """
    market = site.country_name or "Canada"
    window = f"{site.shipping_min_days}–{site.shipping_max_days}"
    return (
        f"You write SEO blog posts for a RESEARCH-COMPOUND (peptide) supplier "
        f"serving laboratories in {market}.\n"
        "STRICT COMPLIANCE RULES — follow exactly:\n"
        "1. Everything is for laboratory research use only. Never imply human or veterinary use.\n"
        "2. Make NO medical, therapeutic, diagnostic, or health claims (no cure/treat/prevent/heal).\n"
        "3. NO dosing, administration, or 'how to take' guidance. NO weight-loss or "
        "body-composition promises.\n"
        "4. NO efficacy guarantees, 'clinically proven', 'FDA approved', or testimonials. "
        "Do not invent customer quotes, review counts, ratings, or case studies.\n"
        "5. Do not claim certifications the business has not stated: no GMP, ISO, USP, "
        "'pharmaceutical grade', or regulatory registration of any kind.\n"
        "5b. CRITICAL — we hold NO analytical documentation. Never state or imply that "
        "products are third-party tested, HPLC or mass-spec verified, purity-tested, or "
        "that a certificate of analysis exists, is issued per batch, or is available on "
        "request. Never state a purity figure or threshold (no '≥99%', no 'high purity', "
        "no 'release purity'). You may explain what a COA or an HPLC test IS as general "
        "education, but never claim we provide one. Where documentation would naturally "
        "be mentioned, say plainly that we hold none and the material should be treated "
        "as uncharacterised.\n"
        "6. NEVER state or imply a country or region that products ship from, are stocked "
        "in, or are manufactured in — not Canada, not anywhere else. Do not write 'ships "
        "from', 'domestic stock', 'made in', or any equivalent. Say only that orders ship "
        "directly from our manufacturing partner. Writing about a market is fine; writing "
        "about an origin is not.\n"
        f"7. The delivery window is {window} days. Never state any other window, and never "
        "promise same-day, next-day, overnight, or free express shipping.\n"
        "8. No superlatives or price claims — no 'cheapest', 'best', 'purest', 'number one'.\n"
        "9. Research-news reporting is encouraged: summarize published, peer-reviewed "
        "research about a compound, but ATTRIBUTE every finding to its source ('a 2023 "
        "rodent study reported…', 'researchers observed…', 'a review of the literature "
        "found…') and HEDGE it (preliminary, in animal models, not established in "
        "humans). Report findings as-is; never restate them as this store's own claim, "
        "never extrapolate them into advice, and never invent a citation, journal, or "
        "result. Where a finding is exciting, say plainly that human relevance is "
        "unknown.\n"
        "9b. Every research summary must carry a short reader note: this is not medical "
        "advice — do your own research and consult the primary literature.\n"
        "10. Naturally include the target keyword. End with a research-use-only disclaimer.\n"
        "Return Markdown: an H1 title, a 2–3 sentence intro, then 4–6 substantive sections "
        "with H2 headings, and a closing disclaimer. Aim for 900–1300 words of genuine "
        "information — depth a researcher would actually find useful, not padding."
    )


def _stub_post(site, keyword):
    """Compliant fallback post (used when no AI key). Written to pass guardrails."""
    brand = site.brand_name
    market = site.country_name
    window = f"{site.shipping_min_days}-{site.shipping_max_days}"
    names = ", ".join(p.name for p in Product.objects.filter(is_active=True)[:6])
    title = f"{keyword.title()}: What to Look For in a Research Supplier"
    body = f"""# {title}

Researchers searching for **{keyword}** should evaluate a supplier on documentation and
transparency, not marketing language. This overview explains what {brand} does and does not
hold, and how ordering works for laboratories in {market}.

## What documentation exists
{brand} holds no certificate of analysis, purity result or identity confirmation for the
compounds it lists, and does not claim any. Material should be treated as uncharacterised.
A researcher whose work depends on confirmed identity or purity should budget for their own
analysis before use.

## Selection and availability
The catalogue spans research categories such as {names}. Listings show the research category
and size. No purity figure is published, because no measurement stands behind one.

## Ordering
Orders ship directly from our manufacturing partner in plain, tracked packaging. Allow
{window} days for delivery; shipments may be subject to customs clearance. Compounds are
supplied strictly as laboratory reference materials.

For research use only. Not for human or veterinary use. This article is informational and
describes laboratory research materials; it makes no medical, therapeutic, or health claims.
"""
    return title, body


# How many times the model is handed its own violations and asked to fix them
# before the deterministic scrub takes over. Three is where the returns stop:
# pass 1 clears the great majority, pass 2 catches the phrase the rewrite
# reintroduced somewhere else, pass 3 is insurance. Override with
# PEPTIDENET_BLOG_REPAIR_PASSES.
MAX_REPAIR_PASSES = getattr(settings, "BLOG_REPAIR_PASSES", 3)

# Below this, a scrubbed post is too thin to be worth publishing and is held
# for a human instead. Google's problem with a 300-word page is not that it is
# short, it is that it answers nothing.
MIN_PUBLISH_WORDS = getattr(settings, "BLOG_MIN_WORDS", 600)


def _repair_prompt(site, body, hard, keyword):
    """The rewrite instruction: the offending draft plus a per-rule brief."""
    window = f"{site.shipping_min_days}–{site.shipping_max_days}"
    return (
        "The draft below FAILED the compliance scanner. Rewrite it in full so it "
        "passes, and change nothing else.\n\n"
        "=== WHAT FAILED ===\n"
        f"{guardrails.remediation_brief(hard)}\n\n"
        "=== HOW TO REWRITE ===\n"
        "- Keep the same topic, structure, headings, register and length. This is "
        "a repair, not a new post.\n"
        "- Fix the idea, not just the words. Deleting a banned phrase while the "
        "surrounding sentence still asserts the claim does not pass.\n"
        "- Do not replace a removed claim with a synonym for it, and do not "
        "replace it with a denial that names a country.\n"
        "- Losing a paragraph is acceptable; replace it with something factual "
        "and useful so the post stays substantive.\n"
        f"- The only delivery window you may state is {window} days.\n"
        f"- Keep the keyword \"{keyword}\" reading naturally in the text.\n"
        "- Return the complete rewritten post as Markdown, starting with its H1. "
        "Return nothing else — no preamble, no notes about what you changed.\n\n"
        "=== DRAFT ===\n"
        f"{body}"
    )


def compose(site, keyword):
    """Write a post and repair it until the guardrails pass.

    Returns (review, provenance). The old behaviour was a single call whose
    output was scanned once and then, if flagged, abandoned — which is how 65 of
    66 drafts ended up stranded in needs_review with six of eight blogs never
    publishing anything. The scanner's verdict is now fed back to the writer,
    which is the difference between a gate and a dead end.
    """
    _, stub_body = _stub_post(site, keyword)
    market = site.country_name or "Canada"
    # The angle keeps eight sites off one another's toes. All eight share a
    # single catalogue, so without a distinct lane per domain the network reads
    # as one site duplicated eight times — which is the failure mode that gets
    # a network filtered rather than ranked.
    angle = keywords.angle_for(site)
    lane = f"\nEditorial angle for this site: {angle}" if angle else ""
    system = build_system(site)
    body = llm.complete(
        system=system,
        user=(f"Write an SEO blog post for {site.brand_name} targeting the keyword "
              f"\"{keyword}\" for the {market} research market.{lane}\n"
              "Write it so it stands on its own — a reader who found this page from "
              "search should leave better informed about how to evaluate a supplier. "
              "Follow all compliance rules."),
        purpose="blog_post", site=site, stub=stub_body,
        max_tokens=2600,
    )
    return _repair_loop(site, body, keyword, provenance=["first draft"])


def compose_repair(site, body, keyword):
    """Run an EXISTING body through the repair loop. Same contract as compose().

    This is what rescues the backlog: a draft written before the loop existed
    never got a second look, and the scanner's own verdict is the brief that
    fixes it.
    """
    return _repair_loop(site, body, keyword, provenance=["existing draft"])


def _repair_loop(site, body, keyword, provenance):
    """Hand the model its own violations until they are gone, then scrub.

    Returns (review, provenance).
    """
    system = build_system(site)
    review = guardrails.review(body)

    for attempt in range(1, MAX_REPAIR_PASSES + 1):
        if review["status"] == "pass":
            break
        hard, _ = guardrails.scan(review["text"])
        if not hard:                                   # nothing actionable left
            break
        rewritten = llm.complete(
            system=system,
            user=_repair_prompt(site, review["text"], hard, keyword),
            purpose="blog_repair", site=site, stub="",
            max_tokens=2800,
        )
        if not rewritten.strip():
            # No key, or the call failed. Another identical attempt will fail
            # the same way, so stop paying for it and let the scrub decide.
            provenance.append(f"repair pass {attempt}: no response")
            break
        candidate = guardrails.review(rewritten)
        provenance.append(
            f"repair pass {attempt}: {review['hard_count']} → {candidate['hard_count']} issues")
        # Only keep a rewrite that actually helped. A model asked to fix four
        # violations sometimes returns prose that is cleaner in three places and
        # worse in a fourth; keeping the better of the two means the loop can
        # never walk a draft backwards.
        if candidate["hard_count"] <= review["hard_count"]:
            review = candidate
        if review["status"] == "pass":
            break

    if review["status"] != "pass":
        # The model has had its chances. Cut the sentences that still carry a
        # violation and re-scan — a post that loses two sentences and publishes
        # clean beats a post that keeps them and never publishes at all.
        before = review["hard_count"]
        scrubbed = guardrails.review(guardrails.scrub(review["text"]))
        words = guardrails.word_count(scrubbed["text"])
        if scrubbed["status"] == "pass" and words >= MIN_PUBLISH_WORDS:
            review = scrubbed
            provenance.append(f"scrubbed {before} → 0 issues ({words} words)")
        elif scrubbed["status"] == "pass":
            provenance.append(
                f"scrub left only {words} words (min {MIN_PUBLISH_WORDS}) "
                "— held for a human")
        else:
            provenance.append("scrub could not clear it — held for a human")

    return review, provenance


def repair_title(site, body, current_title, keyword=""):
    """A compliant title for a repaired post, or '' if none could be produced.

    The repair loop only ever scanned `body`, and a title is a separate column.
    So a post could come out of it marked `pass` while its `<title>` still read
    "High Purity Peptides Canada" or "Mass-Spec Verified Peptides" — 17 of the
    backlog did exactly that. That is the most damaging place a claim can sit:
    the title is what Google renders in the result and what a reader sees before
    they see anything else, and the body scrub had removed the very sentences
    that made the claim, so the post asserted in its headline something its text
    no longer said.

    Tries the cheapest thing first (the scrubbed body's own H1, which is already
    known clean), then asks the model, then gives up — and giving up means the
    post stays flagged rather than publishing a headline nobody checked.
    """
    current_title = (current_title or "").strip()
    if current_title and not guardrails.scan(current_title)[0]:
        return current_title

    for line in body.splitlines():
        s = line.strip()
        if s.startswith("# "):
            candidate = s[2:].strip()
            if candidate and not guardrails.scan(candidate)[0]:
                return candidate[:200]
            break

    hard, _ = guardrails.scan(current_title)
    brief = guardrails.remediation_brief(hard) if hard else ""
    for _ in range(2):
        out = llm.complete(
            system=build_system(site),
            user=("Write a replacement headline for the article below. The "
                  "current headline fails compliance:\n\n"
                  f"CURRENT: {current_title}\n\n"
                  f"{brief}\n\n"
                  "Rules: under 70 characters, no claim the article does not "
                  "support, no purity figure, no testing/COA/certification "
                  f"claim, no country of origin. Keep it about \"{keyword}\" if "
                  "that reads naturally. Return the headline alone — no quotes, "
                  "no preamble, no alternatives.\n\n"
                  f"ARTICLE:\n{body[:2500]}"),
            purpose="blog_title", site=site, stub="", max_tokens=120,
        )
        candidate = (out or "").strip().strip('"“”').splitlines()[0].strip()[:200] \
            if (out or "").strip() else ""
        if candidate and not guardrails.scan(candidate)[0]:
            return candidate
    return ""


def generate(site, keyword):
    stub_title, _ = _stub_post(site, keyword)
    review, provenance = compose(site, keyword)
    body = review["text"]

    # derive a title from the first H1 if present, else the stub title
    title = stub_title
    for line in body.splitlines():
        if line.strip().startswith("# "):
            title = line.strip()[2:].strip()
            break
    # The H1 survives the scrub only if it was clean, but a title lifted from a
    # draft the model wrote can still carry a claim the body no longer makes.
    # A headline is the most visible place a claim can sit; scan it like prose.
    if guardrails.scan(title)[0]:
        title = repair_title(site, body, title, keyword) or stub_title

    excerpt = summarise(body, title, limit=300)

    slug = _unique_slug(site, slugify(title) or slugify(keyword))
    accent = (site.palette or {}).get("accent", "#4f8ff7")
    # OpenAI-generated hero (research-safe prompt); falls back to the stock pool
    # when AI is offline/stubbed so drafts always have an image.
    hero_image = images.generate_blog_image(keyword, site=site, accent=accent, slug=slug) \
        or BLOG_HERO_POOL[zlib.crc32(keyword.encode()) % len(BLOG_HERO_POOL)]

    post = BlogPost.objects.create(
        site=site, title=title[:200], slug=slug,
        keyword=keyword, excerpt=excerpt, body=review["text"],
        seo_title=title[:200],
        hero_svg=banner_svg(site, title),
        hero_image=hero_image,
        meta_description=summarise(body, title, limit=META_DESCRIPTION_CHARS),
        status="needs_review",                         # NEVER auto-published
        compliance_status=review["status"],
        compliance_notes="\n".join(
            [review["notes"]] + [f"· {p}" for p in provenance]).strip(),
        ai_generated=True,
    )
    return post


def banner_svg(site, title):
    """Self-contained SVG blog hero — themed molecular banner with the title."""
    accent = (site.palette or {}).get("accent", "#4f8ff7")
    words = (title or "Research").split()
    head = " ".join(words[:6])
    return f"""<svg viewBox="0 0 1200 480" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{head}">
<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="#0a0f1c"/><stop offset="1" stop-color="#111a2b"/></linearGradient></defs>
<rect width="1200" height="480" fill="url(#bg)"/>
<g fill="none" stroke="{accent}" stroke-width="2" opacity="0.28">
<polygon points="980,90 1040,124 1040,192 980,226 920,192 920,124"/>
<circle cx="980" cy="90" r="7" fill="{accent}"/><circle cx="1040" cy="192" r="7" fill="{accent}"/>
<path d="M980 226 L975 300 L1050 340"/><circle cx="1050" cy="340" r="7" fill="{accent}"/>
<polygon points="150,300 205,332 205,396 150,428 95,396 95,332"/></g>
<text x="70" y="150" fill="{accent}" font-family="IBM Plex Sans,Segoe UI,Arial,sans-serif" font-size="20" font-weight="700" letter-spacing="3">RESEARCH NOTES</text>
<text x="70" y="250" fill="#eaf0fb" font-family="IBM Plex Sans,Segoe UI,Arial,sans-serif" font-size="52" font-weight="800">{head[:34]}</text>
<text x="70" y="410" fill="#93a2bd" font-family="IBM Plex Sans,Segoe UI,Arial,sans-serif" font-size="18">{site.brand_name} · For research use only</text>
</svg>"""
