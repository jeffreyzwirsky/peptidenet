"""Where a product's photography lives, defined once.

Two commands answer this question and they used to answer it differently.
``seed_catalog`` resolved artwork through the size family (``family or slug``);
``assign_product_images`` looked only for ``<slug>.png``. A sibling strength
therefore got a picture from one command and nothing at all from the other —
which is why 49 active products were sitting on the SVG fallback on
2026-08-16 while the seeder believed it had illustrated them.

The rule now, in one place:

    1. ``<slug>.png``   — this product's own render. Preferred, because the
       label prints the net fill and the cake height is drawn from the
       milligram mass, so the 5 mg sibling's own render is the only one that
       is true of the 5 mg vial.
    2. ``<family>.png`` — the family default's render. A fallback only, for a
       sibling added to catalogue.json before the renderer has been run. It
       shows the right compound with the WRONG net fill, so it is strictly
       better than a grey placeholder and strictly worse than doing the render.
    3. ``None``         — no file on disk; the caller leaves the product alone
       and the template keeps its SVG fallback.
"""
from pathlib import Path

from django.conf import settings

STATIC_URL_DIR = "/static/products"


def products_dir() -> Path:
    """Source static dir (not STATIC_ROOT) — renders are committed, not collected."""
    dirs = list(getattr(settings, "STATICFILES_DIRS", []) or [])
    root = Path(dirs[0]) if dirs else Path(settings.BASE_DIR) / "static"
    return root / "products"


def art_slug(slug, family="", directory=None):
    """Which render illustrates this product, or None. See module docstring."""
    directory = Path(directory) if directory else products_dir()
    for candidate in (slug, family):
        if candidate and (directory / f"{candidate}.png").exists():
            return candidate
    return None


def art_urls(slug, family="", directory=None):
    """(primary_url, label_url) for a product, either of which may be None."""
    art = art_slug(slug, family, directory)
    if not art:
        return None, None
    directory = Path(directory) if directory else products_dir()
    label = (directory / f"{art}-label.png").exists()
    return (f"{STATIC_URL_DIR}/{art}.png",
            f"{STATIC_URL_DIR}/{art}-label.png" if label else None)


def is_family_fallback(slug, family="", directory=None):
    """True when this product is borrowing a sibling's picture.

    Worth surfacing in command output: it means the printed net fill does not
    match the product, and the fix is `generate_product_images --missing-only`.
    """
    art = art_slug(slug, family, directory)
    return bool(art) and art != slug
