from decimal import Decimal

from apps.catalog.models import Product

CART_SESSION_KEY = "cart"


class Cart:
    """Session-backed cart shared by every site on the server."""

    def __init__(self, request):
        self.session = request.session
        self.cart = self.session.setdefault(CART_SESSION_KEY, {})

    def save(self):
        self.session[CART_SESSION_KEY] = self.cart
        self.session.modified = True

    def add(self, product_id, qty=1, replace=False):
        pid = str(product_id)
        current = self.cart.get(pid, 0)
        self.cart[pid] = int(qty) if replace else current + int(qty)
        if self.cart[pid] <= 0:
            self.cart.pop(pid, None)
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
        ids = [int(k) for k in self.cart.keys()]
        return {p.id: p for p in Product.objects.filter(id__in=ids)}

    def items(self):
        products = self._products()
        out = []
        for pid, qty in self.cart.items():
            p = products.get(int(pid))
            if not p:
                continue
            out.append({
                "id": p.id,
                "name": p.name,
                "slug": p.slug,
                "price": p.price,
                "qty": qty,
                "line_total": p.price * qty,
                "category": p.category.name,
                "color": p.category.color,
            })
        return out

    def count(self):
        return sum(self.cart.values())

    def total(self):
        return sum((i["line_total"] for i in self.items()), Decimal("0"))
