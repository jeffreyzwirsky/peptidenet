import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.catalog.models import Category, Product

# Category accent colours (used to tint vials/badges across all themes).
CATEGORY_COLORS = {
    "Metabolic": "#4f8ff7",
    "Mitochondrial": "#ff6b6b",
    "Repair & Recovery": "#37e0a6",
    "Growth Factors": "#9b8cff",
    "Neuropeptides": "#ffb454",
    "Melanocortin": "#e08a4f",
    "Supplies": "#8fa0bd",
}
CATEGORY_ORDER = list(CATEGORY_COLORS.keys())


class Command(BaseCommand):
    help = "Load/refresh the shared product catalogue from data/catalogue.json"

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=str(Path(settings.BASE_DIR) / "data" / "catalogue.json"),
        )

    def handle(self, *args, **opts):
        data = json.loads(Path(opts["path"]).read_text(encoding="utf-8"))
        products = data["products"]

        # Categories first.
        for name in CATEGORY_ORDER:
            Category.objects.update_or_create(
                name=name,
                defaults={
                    "slug": slugify(name),
                    "color": CATEGORY_COLORS[name],
                    "order": CATEGORY_ORDER.index(name),
                },
            )

        created = updated = 0
        for i, p in enumerate(products):
            cat, _ = Category.objects.get_or_create(
                name=p["cat"],
                defaults={"slug": slugify(p["cat"]),
                          "color": CATEGORY_COLORS.get(p["cat"], "#8fa0bd")},
            )
            # Give tracked inventory sensible starting quantities so the
            # low/in/out states match the original design flags.
            seed_qty = {"low": 4, "out": 0}.get(p.get("stock", "in"), 30)
            # Placeholder landed cost ~35% of sell price (typical research-peptide
            # markup). Edit real costs in the control panel / admin.
            seed_cost = round(p["price"] * 0.35, 2)
            defaults = {
                "name": p["n"],
                "category": cat,
                "price": p["price"],
                "purity": p.get("pur", "≥99%"),
                "sizes": p.get("sizes", []),
                "stock": p.get("stock", "in"),
                "is_new": p.get("new", False),
                "description": p.get("d", ""),
                "order": i,
                "track_inventory": True,
                "low_stock_threshold": 5,
            }
            existing = Product.objects.filter(slug=slugify(p["n"])).first()
            if existing is None:
                # only set qty + cost on first seed; don't clobber later edits
                defaults["stock_qty"] = seed_qty
                defaults["unit_cost"] = seed_cost
            _, was_created = Product.objects.update_or_create(
                slug=slugify(p["n"]), defaults=defaults,
            )
            created += was_created
            updated += not was_created

        self.stdout.write(
            self.style.SUCCESS(
                f"Catalogue seeded: {created} created, {updated} updated, "
                f"{Category.objects.count()} categories."
            )
        )
