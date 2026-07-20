import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.catalog.models import Product

# The seed catalogue uses a couple of names that differ from the science file
# (e.g. "TB-500 (Thymosin…)" vs "TB-500"). Map spec-file name -> catalogue name.
ALIASES = {
    "TB-500": "TB-500",
    "Epithalon": "Epithalon",
    "SS-31": "SS-31",
}

SPEC_FIELDS = [
    "cas_number", "molecular_formula", "molecular_weight", "sequence",
    "synonyms", "half_life", "storage", "solubility", "appearance",
    "research_area",
]


class Command(BaseCommand):
    help = "Apply scientific reference data (CAS, formula, MW, sequence…) to products."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=str(Path(settings.BASE_DIR) / "data" / "compound_specs.json"),
        )

    def handle(self, *args, **opts):
        data = json.loads(Path(opts["path"]).read_text(encoding="utf-8"))
        updated = missing = 0
        for c in data["compounds"]:
            name = ALIASES.get(c["name"], c["name"])
            p = (
                Product.objects.filter(slug=slugify(name)).first()
                or Product.objects.filter(name=name).first()
                or Product.objects.filter(slug=slugify(c["name"])).first()
            )
            if not p:
                self.stderr.write(f"  ! no product for {c['name']}")
                missing += 1
                continue
            p.cas_number = c.get("cas", "") or ""
            p.molecular_formula = c.get("formula", "") or ""
            mw = c.get("mw")
            p.molecular_weight = ("" if mw is None else str(mw))
            p.sequence = c.get("sequence", "") or ""
            p.synonyms = c.get("synonyms", []) or []
            p.half_life = c.get("half_life", "") or ""
            p.storage = c.get("storage", "") or ""
            p.solubility = c.get("solubility", "") or ""
            p.appearance = c.get("appearance", "") or ""
            p.research_area = c.get("research_area", "") or ""
            if not p.lab_name:
                p.lab_name = "Janoshik Analytical"
            p.save()
            updated += 1
        self.stdout.write(
            self.style.SUCCESS(f"Specs applied: {updated} updated, {missing} missing.")
        )
