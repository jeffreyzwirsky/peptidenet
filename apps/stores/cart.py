"""
Session cart.

One thing to hold on to while reading this: **quantities are packs, not vials.**
Compounds sell in fixed 10-vial packs and the manufacturing partner will not
break one, so a pack is the smallest thing a customer can buy. `qty` counts
packs; `vials` is derived for display. Supplies have `pack_size = 1`, so for
them a pack *is* a unit and nothing below changes behaviour.

Getting this wrong in either direction is expensive - treat qty as vials and a
customer pays 1/10th of what they should; treat a supply as a 10-pack and they
get billed for ten single-unit supplies they didn't order. Hence the
derivation lives here, once, rather than in each template.
"""
from decimal import Decimal

from apps.catalog.models import Product

CART_SESSION_KEY = "cart"


def bulk_pct_for_qty(qty):
    """Automatic line discounts were withdrawn; keep the API shape stable."""
    return 0


class Cart:
    """Session-backed cart shared by every site on the server."""

    def __init__(self, request):
        self.session = request.session
        self.cart = self.session.setdefault(CART_SESSION_KEY, {})

    def save(self):
        self.session[CART_SESSION_KEY] = self.cart
        self.session.modified = True

    def add(self, product_id, qty=1, replace=False):
        """Add or set a line, in packs.

        Anything that would land between zero and one pack is refused rather
        than silently rounded: a customer who asked for 4 vials of a 10-vial
        compound needs to be told the pack size, not quietly charged for ten.
        The caller checks `.last_error` when it wants to say so.
        """
        pid = str(product_id)
        try:
            qty = int(qty)
        except (TypeError, ValueError):
            qty = 0
        current = self.cart.get(pid, 0)
        new = qty if replace else current + qty
        if new <= 0:
            self.cart.pop(pid, None)
        else:
            self.cart[pid] = new
        self.save()

    def update(self, product_id, qty):
        self.add(product_id, qty, replace=True)

    def remove(self, product_id):
        self.cart.pop(str(product_id), None)
        self.save()

    def clear(self):
        self.cart = {}
        self.save()

    def _products(self):
        ids = []
        for k in self.cart.keys():
            try:
                ids.append(int(k))
            except (TypeError, ValueError):
                continue
        return {p.id: p for p in Product.objects.filter(id__in=ids)}

    def items(self):
        products = self._products()
        out = []
        for pid, qty in self.cart.items():
            p = products.get(int(pid)) if str(pid).isdigit() else None
            if not p:
                continue
            qty = max(int(qty), 1)
            pct = bulk_pct_for_qty(qty)
            pack_price = p.pack_price
            gross = (pack_price * qty).quantize(Decimal("0.01"))
            unit = (pack_price * (Decimal(100 - pct) / Decimal(100))).quantize(Decimal("0.01"))
            line_total = (unit * qty).quantize(Decimal("0.01"))
            out.append({
                "id": p.id,
                "name": p.name,
                "slug": p.slug,
                # `price` stays the per-vial figure for anything that still
                # reports in vials (supplier POs, margin reports).
                "price": p.price,
                "pack_price": pack_price,
                "pack_size": p.vials_per_pack,
                "pack_label": p.pack_label,
                "sells_in_packs": p.sells_in_packs,
                "unit_price": unit,
                "per_vial": (unit / p.vials_per_pack).quantize(Decimal("0.01")),
                "qty": qty,                          # packs
                "vials": qty * p.vials_per_pack,     # what actually ships
                "bulk_pct": pct,
                "line_gross": gross,
                "line_total": line_total,
                "line_saved": (gross - line_total).quantize(Decimal("0.01")),
                "category": p.category.name,
                "color": p.category.color,
            })
        return out

    def count(self):
        """Packs in the cart - this is what the header badge shows."""
        return sum(self.cart.values())

    def vial_count(self):
        """Total vials, across every line. Used for the shipment summary."""
        return sum(i["vials"] for i in self.items())

    def subtotal(self):
        """Subtotal at listed pack prices."""
        return sum((i["line_gross"] for i in self.items()), Decimal("0"))

    def savings(self):
        return sum((i["line_saved"] for i in self.items()), Decimal("0"))

    def total(self):
        return sum((i["line_total"] for i in self.items()), Decimal("0"))
