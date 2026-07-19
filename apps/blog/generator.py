"""AI blog-post generator with compliance baked into the prompt AND enforced by
the guardrail scanner afterward. Produces a DRAFT (needs_review) — never publishes."""
from django.utils.text import slugify

from apps.ai import llm
from apps.catalog.models import Product

from . import guardrails
from .models import BlogPost

SYSTEM = (
    "You write SEO blog posts for a Canadian RESEARCH-COMPOUND (peptide) store. "
    "STRICT COMPLIANCE RULES — follow exactly:\n"
    "1. Everything is for laboratory research use only. Never imply human or veterinary use.\n"
    "2. Make NO medical, therapeutic, diagnostic, or health claims (no cure/treat/prevent/heal).\n"
    "3. NO dosing, administration, or 'how to take' guidance. NO weight-loss or body-composition promises.\n"
    "4. NO efficacy guarantees, 'clinically proven', 'FDA approved', or testimonials.\n"
    "5. Write factually and neutrally about the compound's research context, purity, testing, COAs, "
    "and Canadian availability/shipping. Educational, not promotional hype.\n"
    "6. Naturally include the target keyword for SEO. End with a research-use-only disclaimer.\n"
    "Return Markdown: an H1 title, a 2-3 sentence intro, 2-3 short sections, and a closing disclaimer."
)


def _stub_post(site, keyword):
    """Compliant fallback post (used when no AI key). Written to pass guardrails."""
    brand = site.brand_name
    ships = site.ships_from
    names = ", ".join(p.name for p in Product.objects.filter(is_active=True)[:6])
    title = f"{keyword.title()}: What to Look For in a Research Supplier"
    body = f"""# {title}

Researchers searching for **{keyword}** should evaluate a supplier on documentation and
transparency, not marketing language. This overview explains what {brand} publishes for
every batch and how ordering works for laboratories in Canada.

## Purity and third-party testing
Every compound is released above a documented ≥99% purity threshold and independently
analyzed by HPLC and mass spectrometry. A batch-specific Certificate of Analysis (COA) is
available on request so a lab can match the vial to its analysis.

## Selection and availability
The catalogue spans research categories such as {names}. Listings show the research category,
size, and purity so a purchasing decision can be made on documented specifications.

## Ordering in Canada
Orders ship from {ships} in plain, tracked packaging, typically arriving within 1-4 days.
Compounds are supplied strictly as laboratory reference materials.

For research use only. Not for human or veterinary use. This article is informational and
describes laboratory research materials; it makes no medical, therapeutic, or health claims.
"""
    return title, body


def generate(site, keyword):
    stub_title, stub_body = _stub_post(site, keyword)
    body = llm.complete(
        system=SYSTEM,
        user=(f"Write an SEO blog post for {site.brand_name} targeting the keyword "
              f"\"{keyword}\" for the Canadian research market. Follow all compliance rules."),
        purpose="blog_post", site=site, stub=stub_body,
    )
    # derive a title from the first H1 if present, else the stub title
    title = stub_title
    for line in body.splitlines():
        if line.strip().startswith("# "):
            title = line.strip()[2:].strip()
            break

    review = guardrails.review(body)     # enforce disclaimer + scan for claims
    excerpt = " ".join(review["text"].replace("#", "").split())[:300]

    post = BlogPost.objects.create(
        site=site, title=title[:200], slug=slugify(title)[:200] or slugify(keyword)[:200],
        keyword=keyword, excerpt=excerpt, body=review["text"],
        meta_description=excerpt[:300], seo_title=title[:200],
        hero_svg=banner_svg(site, title),
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
<text x="70" y="150" fill="{accent}" font-family="Inter,Arial" font-size="20" font-weight="700" letter-spacing="3">RESEARCH NOTES</text>
<text x="70" y="250" fill="#eaf0fb" font-family="Inter,Arial" font-size="52" font-weight="800">{head[:34]}</text>
<text x="70" y="410" fill="#93a2bd" font-family="Inter,Arial" font-size="18">{site.brand_name} · For research use only</text>
</svg>"""
