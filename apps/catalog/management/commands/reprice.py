"""
Recalculate retail prices from supplier cost.

    python manage.py reprice --dry-run     # always look first
    python manage.py reprice
    python manage.py reprice --force       # apply moves past the big-move guard

The arithmetic is one line: hold `target_margin_pct` on the landed cost of a
vial. Everything else in this file is a guard, because a job that edits live
prices unattended is only safe to the extent it refuses to.

  * No FX rate, or a rate older than FxRate.STALE_AFTER_HOURS → nothing runs.
    A stale rate is the failure this whole design is most exposed to.
  * Moves smaller than --threshold are skipped. Without this the daily
    exchange-rate wobble would nudge public prices every night, which looks
    erratic to a customer and makes the struck-through comparison price
    impossible to defend.
  * Moves larger than --max-move are reported and NOT applied. A mistyped cost
    is far more likely than a genuine 40% swing.
  * `list_price` is never touched. It is the price we actually used to charge —
    a historical fact, not a number to derive. Recomputing it would manufacture
    a "was" price that was never charged, which is exactly the misrepresentation
    the Competition Act's ordinary-selling-price rule exists to catch.
  * Every applied move writes a PriceChange row.
"""
from decimal import Decimal, ROUND_UP

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.catalog.models import Product
from apps.suppliers.models import FxRate, PriceChange

STEP = Decimal("0.50")   # retail prices land on a 50-cent step, per vial


def _round_up(value, step=STEP):
    """Round up to the next step. Up, not nearest: rounding down would quietly
    give away margin the target was chosen to hold."""
    return (value / step).quantize(Decimal("1"), rounding=ROUND_UP) * step


class Command(BaseCommand):
    help = "Recalculate retail prices from supplier costs and the current FX rate."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--force", action="store_true",
                            help="Apply moves that exceed --max-move.")
        parser.add_argument("--threshold", type=float, default=3.0,
                            help="Ignore moves smaller than this %% (default 3).")
        parser.add_argument("--max-move", type=float, default=25.0,
                            help="Refuse moves larger than this %% (default 25).")
        parser.add_argument("--currency", default="CAD")
        parser.add_argument("--slug", default="", help="Limit to one product.")
        parser.add_argument("--calibrate", action="store_true",
                            help="Set each product's target margin to the margin it "
                                 "currently earns, instead of repricing. Run this once "
                                 "when switching a live catalogue onto auto-pricing.")

    def handle(self, *args, **o):
        currency = o["currency"].upper()
        fx = FxRate.latest("USD", currency)
        if fx is None:
            self.stderr.write(self.style.ERROR(
                f"No USD/{currency} rate stored. Run `manage.py fetch_fx` first. "
                f"Nothing repriced."))
            return
        if fx.is_stale:
            self.stderr.write(self.style.ERROR(
                f"USD/{currency} rate is STALE — {fx.age_hours:.0f}h old (limit "
                f"{FxRate.STALE_AFTER_HOURS}h). The feed is probably down. "
                f"Nothing repriced — fix the feed, or set a rate by hand with "
                f"`manage.py fetch_fx --set <rate>`."))
            return

        qs = Product.objects.filter(auto_price=True).exclude(supplier_cat_no="")
        if o["slug"]:
            qs = qs.filter(slug=o["slug"])

        if o["calibrate"]:
            return self._calibrate(qs, currency, o["dry_run"])

        applied = skipped = blocked = unlinked = 0
        rows = []
        for p in qs.select_related("category"):
            cost = p.cost_from_supplier(currency)
            target = p.target_price(currency)
            if cost is None or target is None:
                unlinked += 1
                self.stderr.write(self.style.WARNING(
                    f"  ? {p.name}: no supplier row for '{p.supplier_cat_no}' — skipped."))
                continue

            target = _round_up(target)
            old = p.price
            move = ((target - old) / old * 100) if old else Decimal("100")

            if abs(move) < Decimal(str(o["threshold"])):
                skipped += 1
                # Cost still gets refreshed even when the price holds — margin
                # reporting should not drift just because the price didn't move.
                if p.unit_cost != cost and not o["dry_run"]:
                    p.unit_cost = cost
                    p.save(update_fields=["unit_cost"])
                continue

            if abs(move) > Decimal(str(o["max_move"])) and not o["force"]:
                blocked += 1
                rows.append(("BLOCKED", p, old, target, cost, move))
                continue

            rows.append(("apply", p, old, target, cost, move))
            if not o["dry_run"]:
                PriceChange.objects.create(
                    product=p, old_price=old, new_price=target, unit_cost=cost,
                    fx_rate=fx.rate,
                    reason=f"cost {cost} {currency} @ {p.target_margin_pct}% target",
                    applied_by="reprice",
                )
                p.price = target
                p.unit_cost = cost
                p.price_updated_at = timezone.now()
                p.save(update_fields=["price", "unit_cost", "price_updated_at"])
            applied += 1

        if rows:
            self.stdout.write(f"\n{'':2}{'product':<24}{'old':>9}{'new':>9}"
                              f"{'cost':>9}{'margin':>8}{'move':>8}")
            for kind, p, old, new, cost, move in sorted(rows, key=lambda r: -abs(r[5])):
                margin = (new - cost) / new * 100 if new else 0
                mark = self.style.ERROR("✗") if kind == "BLOCKED" else " "
                line = (f"{mark} {p.name[:23]:<24}{old:>9}{new:>9}{cost:>9}"
                        f"{margin:>7.0f}%{move:>7.0f}%")
                self.stdout.write(line)
                if kind == "BLOCKED":
                    self.stdout.write(self.style.ERROR(
                        f"    move exceeds {o['max_move']}% — check the supplier cost "
                        f"is right, then re-run with --force to apply."))
                elif p.list_price and new >= p.list_price:
                    self.stdout.write(self.style.WARNING(
                        f"    new price meets the {p.list_price} comparison price — "
                        f"the 'was' price and discount badge will stop showing on "
                        f"this product, which is correct but worth knowing."))

        verb = "would apply" if o["dry_run"] else "applied"
        self.stdout.write(self.style.SUCCESS(
            f"\n{verb} {applied}; {skipped} within threshold; {blocked} blocked; "
            f"{unlinked} unlinked.  USD/{currency} {fx.rate} "
            f"({fx.age_hours:.0f}h old, {fx.source})"))
        if o["dry_run"] and applied:
            self.stdout.write("Dry run — nothing written. Re-run without --dry-run to apply.")

    def _calibrate(self, qs, currency, dry_run):
        """Adopt each product's current margin as its target.

        Switching a live catalogue onto cost-plus pricing with one blanket
        margin would reprice everything at once — in testing, a flat 75% target
        moved existing products by as much as -40% and +48% on the first run.
        That is a catalogue-wide price shock dressed up as automation, and it
        would also push some prices above their comparison price and silently
        retire the discount badge.

        Calibrating first makes the switch a no-op: today's prices are declared
        correct, and auto-pricing from then on only responds to what actually
        changes — a new supplier sheet or a move in the exchange rate.
        """
        changed = 0
        self.stdout.write(f"\n{'product':<26}{'price':>9}{'cost':>9}{'margin now':>12}"
                          f"{'was target':>12}")
        for p in qs.order_by("name"):
            cost = p.cost_from_supplier(currency)
            if cost is None or not p.price:
                continue
            margin = ((p.price - cost) / p.price * Decimal(100)).quantize(Decimal("0.01"))
            if margin <= 0:
                self.stderr.write(self.style.ERROR(
                    f"  ! {p.name}: sells at or below cost ({p.price} vs {cost}) — "
                    f"left alone, this needs a decision not a calculation."))
                continue
            old_target = p.target_margin_pct
            self.stdout.write(f"{p.name[:25]:<26}{p.price:>9}{cost:>9}"
                              f"{margin:>11.1f}%{old_target:>11.1f}%")
            if not dry_run:
                p.target_margin_pct = margin
                p.save(update_fields=["target_margin_pct"])
            changed += 1
        verb = "would set" if dry_run else "set"
        self.stdout.write(self.style.SUCCESS(
            f"\n{verb} the target margin on {changed} product(s) to what they already "
            f"earn. Repricing is now a no-op until a cost or the FX rate moves."))
