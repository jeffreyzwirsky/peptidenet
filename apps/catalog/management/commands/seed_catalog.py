import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.catalog import images
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

        created = updated = borrowed = 0
        for i, p in enumerate(products):
            cat, _ = Category.objects.get_or_create(
                name=p["cat"],
                defaults={"slug": slugify(p["cat"]),
                          "color": CATEGORY_COLORS.get(p["cat"], "#8fa0bd")},
            )
            # Give tracked inventory sensible starting quantities so the
            # low/in/out states match the original design flags.
            seed_qty = {"low": 4, "out": 0}.get(p.get("stock", "in"), 30)
            # Landed cost comes from the catalogue's explicit "cost" key, which is
            # pegged to the PRE-discount price — cutting our retail price doesn't
            # make the vial cheaper to buy. Falls back to 35% of the reference
            # price for older catalogue files. These are still PLACEHOLDERS until
            # the real per-vial supplier cost is entered.
            reference = p.get("was", p["price"])
            seed_cost = p.get("cost", round(reference * 0.35, 2))
            defaults = {
                "name": p["n"],
                "category": cat,
                "price": p["price"],
                # Only show a struck-through comparison price when it's genuinely
                # higher — a fake "was" price is a Competition Act problem.
                "list_price": (p["was"] if p.get("was", 0) > p["price"] else None),
                # No catalogue entry has ever carried a "pur" key, so this
                # fallback was the sole author of the "≥99%" chip that rendered
                # on every product card and product page across all eight
                # storefronts — a measured-result claim with no analysis behind
                # it. The model default is already "" for exactly that reason
                # (Competition Act s.74.01(1)(b): adequate and proper testing
                # BEFORE the claim, burden on the advertiser); the seeder was
                # quietly overriding it on every run. Set "pur" on a compound
                # only once its analysis is actually in hand.
                "purity": p.get("pur", ""),
                "sizes": p.get("sizes", []),
                "stock": p.get("stock", "in"),
                "is_new": p.get("new", False),
                "description": p.get("d", ""),
                "order": i,
                "track_inventory": True,
                "low_stock_threshold": 5,
                # Compounds sell in 10-vial packs; Supplies are single units.
                # Driven off the catalogue's own "pack" key where present so a
                # future exception doesn't need a code change.
                "pack_size": p.get("pack", 1 if p["cat"] == "Supplies" else 10),
                # Cost-plus wiring. `sup` is the supplier's catalogue code; when
                # present the product opts into automatic repricing, so a new
                # supplier price sheet flows through to cost, margin and retail
                # without anyone retyping figures.
                "supplier_cat_no": p.get("sup", ""),
                "target_margin_pct": p.get("margin", 75),
                "auto_price": bool(p.get("sup")) and p["cat"] != "Supplies",
            }
            if p.get("area"):
                defaults["research_area"] = p["area"]
            # Size-family grouping. A sibling strength carries an explicit
            # slug so the original product keeps the URL that is already
            # indexed and linked — appending a strength to an existing slug
            # would silently 404 every link to it.
            defaults["family"] = p.get("family", "")
            defaults["size_label"] = p.get("size_label", "")
            defaults["family_order"] = p.get("family_order", 0)
            defaults["is_family_default"] = p.get("is_family_default", False)

            # Point at the generated product renders when they exist on disk, so
            # a fresh deploy gets real photography without a second command.
            # This prefers the product's OWN render and only falls back to the
            # family's — siblings do NOT simply share artwork, because the label
            # prints the net fill and the cake is drawn from the mass, so the
            # family picture states the wrong milligrams on every sibling.
            # apps/catalog/images.art_urls is the single definition; this and
            # assign_product_images disagreed until 2026-08-16 and 49 products
            # fell down the gap.
            slug = p.get("slug") or slugify(p["n"])
            primary, label = images.art_urls(slug, p.get("family", ""))
            if primary:
                defaults["image"] = primary
                if label:
                    defaults["gallery"] = [{
                        "src": label,
                        "alt": f"{p['n']} vial label detail — research use only",
                        "label": "Label detail",
                    }]
                if images.is_family_fallback(slug, p.get("family", "")):
                    borrowed += 1

            existing = Product.objects.filter(slug=slug).first()
            if existing is None:
                # only set qty + cost on first seed; don't clobber later edits
                defaults["stock_qty"] = seed_qty
                defaults["unit_cost"] = seed_cost
            _, was_created = Product.objects.update_or_create(
                slug=slug, defaults=defaults,
            )
            created += was_created
            updated += not was_created

        if borrowed:
            # Not fatal, but it means those pages show a label printing a net
            # fill that is not theirs. Say so rather than let it pass as green.
            self.stdout.write(self.style.WARNING(
                f"  {borrowed} product(s) are borrowing a sibling's photograph, "
                "so the printed net fill on those images is wrong. Fix: "
                "manage.py generate_product_images --missing-only"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Catalogue seeded: {created} created, {updated} updated, "
                f"{Category.objects.count()} categories."
            )
        )
