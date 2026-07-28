"""Point every Product at its generated vial photography.

Run after `generate_product_images` (which writes the PNG/WebP pairs into
static/products/):

  python manage.py assign_product_images            # only products missing an image
  python manage.py assign_product_images --all      # re-point every product
  python manage.py assign_product_images --dry-run  # show what would change

Sets, per product:
  image      /static/products/<slug>.png
  image_alt  a compliant, descriptive alt string (research framing only)
  gallery    [{"src": "/static/products/<slug>-label.png", ..., "label": "Label detail"}]

Product.images serves the primary first (label "Vial"), then the gallery, so the
detail template gets a two-shot gallery and the card gets the hero. Products with
no rendered file on disk are left alone, so templates keep their SVG fallback.
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.catalog.models import Product

STATIC_URL_DIR = "/static/products"


def alt_for(p) -> str:
    """Descriptive, research-framed alt text. No claims, no uses, no routes."""
    size = (p.sizes or [""])[0] if isinstance(p.sizes, list) else ""
    bits = [p.name]
    if size:
        bits.append(f"{size} vial")
    else:
        bits.append("vial")
    return (
        f"{' '.join(bits)} — clear glass research-compound vial with an aluminium "
        f"crimp cap, {p.purity} purity, labelled for laboratory research use only"
    )


def label_alt_for(p) -> str:
    return (
        f"Close-up of the {p.name} vial label showing the compound name, net fill, "
        f"{p.purity} purity, lot field and the research-use-only statement"
    )


class Command(BaseCommand):
    help = "Set Product.image / image_alt / gallery from the generated renders."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true",
                            help="Re-point products that already have an image.")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        products_dir = Path(settings.STATICFILES_DIRS[0]) / "products"
        updated = skipped = missing = 0

        for p in Product.objects.all().order_by("order", "name"):
            slug = p.slug or slugify(p.name)
            primary = products_dir / f"{slug}.png"
            label = products_dir / f"{slug}-label.png"

            if not primary.exists():
                missing += 1
                self.stdout.write(self.style.WARNING(
                    f"  no render for {p.name} ({slug}.png) — left on the SVG fallback"))
                continue
            if p.image and not opts["all"]:
                skipped += 1
                continue

            p.image = f"{STATIC_URL_DIR}/{slug}.png"
            p.image_alt = alt_for(p)
            p.gallery = [{
                "src": f"{STATIC_URL_DIR}/{slug}-label.png",
                "alt": label_alt_for(p),
                "label": "Label detail",
            }] if label.exists() else []

            if not opts["dry_run"]:
                p.save(update_fields=["image", "image_alt", "gallery"])
            updated += 1
            self.stdout.write(f"  {p.name} -> {p.image}"
                              + (" + label detail" if p.gallery else ""))

        verb = "would update" if opts["dry_run"] else "updated"
        self.stdout.write(self.style.SUCCESS(
            f"Product imagery: {verb} {updated}, {skipped} already had an image, "
            f"{missing} with no render on disk."))
