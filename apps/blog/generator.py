"""AI blog-post generator with compliance baked into the prompt AND enforced by
the guardrail scanner afterward. Produces a DRAFT (needs_review) — never publishes."""
import zlib

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
        "9. Write factually and neutrally about the compound's research context and the "
        "published literature. Educational, not promotional hype.\n"
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


def generate(site, keyword):
    stub_title, stub_body = _stub_post(site, keyword)
    market = site.country_name or "Canada"
    # The angle keeps eight sites off one another's toes. All eight share a
    # single catalogue, so without a distinct lane per domain the network reads
    # as one site duplicated eight times — which is the failure mode that gets
    # a network filtered rather than ranked.
    angle = keywords.angle_for(site)
    lane = f"\nEditorial angle for this site: {angle}" if angle else ""
    body = llm.complete(
        system=build_system(site),
        user=(f"Write an SEO blog post for {site.brand_name} targeting the keyword "
              f"\"{keyword}\" for the {market} research market.{lane}\n"
              "Write it so it stands on its own — a reader who found this page from "
              "search should leave better informed about how to evaluate a supplier. "
              "Follow all compliance rules."),
        purpose="blog_post", site=site, stub=stub_body,
        max_tokens=2600,
    )
    # derive a title from the first H1 if present, else the stub title
    title = stub_title
    for line in body.splitlines():
        if line.strip().startswith("# "):
            title = line.strip()[2:].strip()
            break

    review = guardrails.review(body)     # enforce disclaimer + scan for claims
    excerpt = " ".join(review["text"].replace("#", "").split())[:300]

    slug = _unique_slug(site, slugify(title) or slugify(keyword))
    accent = (site.palette or {}).get("accent", "#4f8ff7")
    # OpenAI-generated hero (research-safe prompt); falls back to the stock pool
    # when AI is offline/stubbed so drafts always have an image.
    hero_image = images.generate_blog_image(keyword, site=site, accent=accent, slug=slug) \
        or BLOG_HERO_POOL[zlib.crc32(keyword.encode()) % len(BLOG_HERO_POOL)]

    post = BlogPost.objects.create(
        site=site, title=title[:200], slug=slug,
        keyword=keyword, excerpt=excerpt, body=review["text"],
        meta_description=excerpt[:300], seo_title=title[:200],
        hero_svg=banner_svg(site, title),
        hero_image=hero_image,
        status="needs_review",                         # NEVER auto-published
        compliance_status=review["status"],
        compliance_notes=review["notes"],
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
