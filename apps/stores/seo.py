"""Page titles and meta descriptions, built to the lengths search engines use.

Three things were wrong before this module existed, and all three came from the
same cause — the head of every page was assembled inline in a template, so
nothing could measure it.

1. `<meta name="description">` was pinned to `site.meta_description` in
   `themes/base.html` for every page type except products, which set their own
   in each of the eight theme files. One description for a whole storefront.
2. Product titles and descriptions ignored `size_label`, so the eight Retatrutide
   strengths — eight separate URLs at eight different prices — shipped one
   identical title between them. Twenty-eight families do this.
3. Nothing was measured. 344 descriptions ran past 160 characters and 33 titles
   past 60, which means Google truncated them mid-word and the part that
   distinguished the page was often the part that got cut.

The budgets below are where Google truncates, not arbitrary style rules, and
`fit()` drops whole optional segments before it ever cuts a word in half.
"""
import re

# Google renders a title to about 580px, which is roughly 60 characters, and a
# description to about 155–160. Short is fine; truncated mid-word is not.
TITLE_BUDGET = 60
DESC_BUDGET = 158


def _clean(text):
    return " ".join(str(text or "").split())


def fit(head, tail_options=(), budget=TITLE_BUDGET, sep=" — ", required=""):
    """`head`, a `required` segment that is never dropped, then whatever fits.

    Segments are dropped whole rather than truncated, because the useful part
    of "Retatrutide 30mg — Peptides Alberta · Research Compound" is the front,
    and losing a suffix entirely reads better than keeping half of it.

    `required` exists because dropping the brand is how eight domains end up
    sharing one title. "Repair & Recovery Research Compounds — Canada" fits in
    60 characters only if the brand goes, and three unrelated .ca domains then
    ship the identical result — which is precisely the duplicate-network signal
    the whole eight-site structure has to avoid. The brand is what makes the
    title this site's; it is the last thing that should go, not the first.
    """
    head = _clean(head)
    required = _clean(required)
    if required:
        room = budget - len(required) - len(sep)
        if len(head) > room:
            head = _clean(head[:max(room - 1, 1)].rsplit(" ", 1)[0]) + "…"
        out = f"{head}{sep}{required}"
        sep = " · "
        for tail in tail_options:
            tail = _clean(tail)
            if tail and len(f"{out}{sep}{tail}") <= budget:
                out = f"{out}{sep}{tail}"
        return out
    out = head
    for tail in tail_options:
        tail = _clean(tail)
        if not tail:
            continue
        candidate = f"{out}{sep}{tail}"
        if len(candidate) <= budget:
            out = candidate
        sep = " · "                       # first join is an em dash, rest are dots
    if len(out) <= budget:
        return out
    # Even the head alone is too long — trim on a word boundary.
    return _clean(out[:budget - 1].rsplit(" ", 1)[0]) + "…"


def clamp(text, budget=DESC_BUDGET):
    """Trim to the budget on a word boundary, without a dangling ellipsis when
    the text already ends cleanly."""
    text = _clean(text)
    if len(text) <= budget:
        return text
    cut = text[:budget].rsplit(" ", 1)[0].rstrip(" ,;:—–-")
    return f"{cut}…"


def sentences(*parts, budget=DESC_BUDGET):
    """Join whole sentences, keeping as many as fit the budget.

    A description made of two complete sentences reads better in a SERP than
    three sentences with the last one severed, so this drops the overflow
    instead of clamping it.
    """
    out = ""
    for part in parts:
        part = _clean(part)
        if not part:
            continue
        candidate = f"{out} {part}".strip()
        if len(candidate) > budget:
            break
        out = candidate
    return out or clamp(" ".join(_clean(p) for p in parts if p), budget)


# ---------------------------------------------------------------------------
# Per page type
# ---------------------------------------------------------------------------

def home(site):
    return {
        "title": fit(site.brand_name, [site.tagline or "Research Compounds"]),
        "description": clamp(site.meta_description),
    }


def category(site, cat, product_count=0):
    """A category page has to say something the homepage does not.

    Both halves matter: the name distinguishes it from the other six categories
    on this domain, and the market distinguishes it from the same category on
    the seven sibling domains.
    """
    from apps.catalog import copy

    name = _clean(getattr(cat, "name", "")) or "Research compounds"
    market = site.country_name or ""
    title = fit(name, ["Research Compounds", market], required=site.brand_name)
    lede = copy.for_category(cat)["lede"]
    # The brand and the count are what stop the same category description
    # appearing verbatim on eight domains.
    tail = (f"{product_count} listed at {site.brand_name}."
            if product_count else f"At {site.brand_name}.")
    # The lede is the same seven strings on all eight domains, and some of them
    # fill the whole budget on their own — so reserve the brand's room first and
    # clamp the lede into what is left, rather than letting `sentences()` drop
    # the only part that differs between the sites.
    lede = clamp(lede, DESC_BUDGET - len(tail) - 1)
    return {
        "title": title,
        "description": f"{lede} {tail}".strip(),
    }


def product(site, prod):
    """Size is the whole point here.

    A compound sold in eight strengths is eight URLs at eight prices, and until
    the strength appeared in the title they were eight identical results
    competing with one another for the same query.
    """
    name = _clean(prod.name)
    size = _clean(getattr(prod, "size_label", ""))
    label = f"{name} {size}".strip()
    title = fit(label, ["Research Compound"], required=site.brand_name)

    area = _clean(getattr(prod, "research_area", ""))
    if area and not area.endswith("."):
        area += "."
    price = ""
    try:
        price = f"{site.currency or 'CAD'} ${prod.price:.2f} per vial."
    except Exception:
        pass
    window = _clean(getattr(site, "shipping_window", ""))
    delivery = f"{window} delivery." if window else ""
    return {
        "title": title,
        # Front-loaded: the strength and the research area are what tell a
        # searcher this is the right one of eight near-identical results.
        # The brand goes in the opening sentence, not the last one. The same
        # compound at the same price on three .com domains produced three
        # identical descriptions when the brand was left to the overflow.
        "description": sentences(
            f"{label} from {site.brand_name} — laboratory reference material, "
            "research use only.",
            area, price, delivery),
    }


def blog_post(site, post):
    """A post's own headline, never truncated to make room for the brand.

    Everywhere else, squeezing a title into 60 characters is the right trade.
    Here it is not: blog headlines run long and often share an opening, so
    truncating the head and appending the brand collapsed ten pairs of genuinely
    different posts into one identical `<title>` — "Where to Buy Research
    Peptides… — Where Do I Get Peptides?" twice on the same site. A title that
    Google shortens in the SERP still indexes in full and still tells the two
    pages apart; a title that arrives identical does neither.

    So the brand is appended only when the whole thing fits.
    """
    title = _clean(post.seo_title or post.title)
    with_brand = f"{title} — {_clean(site.brand_name)}"
    return {
        "title": with_brand if len(with_brand) <= TITLE_BUDGET else title,
        "description": clamp(post.meta_description or post.excerpt),
    }


def generic(site, heading, blurb=""):
    """Policy, order status, and other pages with a plain heading.

    The brand is appended rather than assumed: these blurbs are written once and
    rendered on all eight domains, so without it every storefront ships an
    identical description for each policy and operational page.
    """
    blurb = _clean(blurb) or _clean(site.meta_description)
    brand = _clean(site.brand_name)
    if brand:
        # Reserve the brand's room and clamp the blurb into what is left. The
        # earlier version appended the brand only when it happened to fit, so
        # the three longest policy summaries — shipping, returns and terms —
        # dropped it and shipped one identical description across all eight
        # domains, which is exactly the case it was added for.
        tail = f"{brand}."
        blurb = f"{clamp(blurb, DESC_BUDGET - len(tail) - 1)} {tail}".strip()
    return {
        "title": fit(heading, required=brand),
        "description": clamp(blurb),
    }


def region(site, reg):
    name = _clean(reg.get("name", ""))
    return {
        "title": fit(f"Research Peptides in {name}", required=site.brand_name),
        "description": clamp(reg.get("meta_description", "")),
    }


# ---------------------------------------------------------------------------

_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]+")


def word_count(text):
    return len(_WORD.findall(text or ""))
