"""
Load the supplier price sheet into the staff-only price list.

Run this whenever they send a new sheet. It is idempotent — matching on the
supplier's own catalogue code — so re-importing an updated sheet moves prices
rather than creating duplicates, and prints what moved.

    python manage.py import_supplier_prices
    python manage.py import_supplier_prices --file data/supplier_prices.json
    python manage.py import_supplier_prices --dry-run

Nothing here touches retail prices. `reprice` does that, separately and on
purpose, so a bad import can be inspected before it reaches a storefront.
"""
import json
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.suppliers.models import SupplierPrice

DEFAULT_FILE = "data/supplier_prices.json"


class Command(BaseCommand):
    help = "Import or update the supplier price list (staff-only cost data)."

    def add_arguments(self, parser):
        parser.add_argument("--file", default=DEFAULT_FILE)
        parser.add_argument("--dry-run", action="store_true",
                            help="Report what would change without writing.")
        parser.add_argument("--deactivate-missing", action="store_true",
                            help="Mark codes absent from this sheet as inactive.")

    def handle(self, *args, **o):
        path = Path(o["file"])
        if not path.is_absolute():
            path = Path(settings.BASE_DIR) / path
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise CommandError(f"No price sheet at {path}")
        except json.JSONDecodeError as e:
            raise CommandError(f"{path} is not valid JSON: {e}")

        rows = payload.get("prices") or []
        if not rows:
            raise CommandError("Price sheet contains no rows.")
        currency = payload.get("currency", "USD")

        created = updated = unchanged = 0
        moves = []
        seen = set()
        for r in rows:
            cat = (r.get("cat") or "").strip()
            if not cat:
                self.stderr.write(f"  skipped a row with no catalogue code: {r}")
                continue
            seen.add(cat)
            new_price = Decimal(str(r["pack_price_usd"]))
            defaults = {
                "name": r.get("name", cat),
                "size": r.get("size", ""),
                "pack_size": int(r.get("pack_size", 10)),
                "pack_price": new_price,
                "currency": r.get("currency", currency),
                "risk": r.get("risk", "standard"),
                "is_active": True,
            }
            existing = SupplierPrice.objects.filter(cat_no=cat).first()
            if existing is None:
                SupplierPrice.objects.create(cat_no=cat, **defaults)
                created += 1
                continue
            old_price = existing.pack_price
            for k, v in defaults.items():
                setattr(existing, k, v)
            existing.save()
            if old_price != new_price:
                updated += 1
                pct = ((new_price - old_price) / old_price * 100) if old_price else 0
                moves.append((cat, existing.name, old_price, new_price, pct))
            else:
                unchanged += 1

        stale = SupplierPrice.objects.exclude(cat_no__in=seen).filter(is_active=True)
        if o["deactivate_missing"] and not o["dry_run"]:
            n = stale.update(is_active=False)
            self.stdout.write(f"Deactivated {n} code(s) absent from this sheet.")
        elif stale.exists():
            self.stdout.write(self.style.WARNING(
                f"{stale.count()} active code(s) are not in this sheet "
                f"(kept — pass --deactivate-missing to retire them)."))

        if moves:
            self.stdout.write("\nCost changes:")
            for cat, name, old, new, pct in sorted(moves, key=lambda m: -abs(m[4])):
                arrow = self.style.ERROR("↑") if new > old else self.style.SUCCESS("↓")
                self.stdout.write(f"  {arrow} {cat:<8} {name[:34]:<34} "
                                  f"{old} → {new} ({pct:+.0f}%)")

        self.stdout.write(self.style.SUCCESS(
            f"\n{created} created, {updated} repriced, {unchanged} unchanged."))

        flagged = SupplierPrice.objects.filter(risk__in=("patented", "hormone"),
                                               is_active=True).count()
        if flagged:
            self.stdout.write(self.style.WARNING(
                f"{flagged} SKU(s) are flagged as patent-enforced GLP-1s or regulated "
                f"hormones. They are in the cost list but must not be listed for sale "
                f"without a deliberate decision — see /manage/pricing/."))
        if o["dry_run"]:
            raise CommandError("--dry-run: rolled back, nothing written.")

        self.stdout.write(
            "Retail prices are unchanged. Run `manage.py reprice --dry-run` to see "
            "what these costs would do to prices before applying anything.")
