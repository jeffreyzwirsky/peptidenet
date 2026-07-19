from django.conf import settings
from django.db import models
from django.utils.crypto import get_random_string


class Order(models.Model):
    STATUS = [
        ("pending_payment", "Pending payment"),  # payment processor not wired
        ("paid", "Paid"),
        ("fulfilled", "Fulfilled"),
        ("cancelled", "Cancelled"),
    ]

    number = models.CharField(max_length=20, unique=True, editable=False)
    site = models.ForeignKey(
        "stores.Site", on_delete=models.PROTECT, related_name="orders"
    )
    email = models.EmailField(blank=True)
    name = models.CharField(max_length=120, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cost_total = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="COGS snapshot — sum of unit costs at time of sale.",
    )
    status = models.CharField(max_length=20, choices=STATUS, default="pending_payment")
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def profit(self):
        return self.total - self.cost_total

    @property
    def margin_pct(self):
        return round(self.profit / self.total * 100, 1) if self.total else 0

    class Meta:
        ordering = ["-created_at"]

    @classmethod
    def create_from_cart(cls, site, items, total, email="", name=""):
        from decimal import Decimal

        from django.db.models import F

        from apps.catalog.models import Product

        number = "SFB-" + get_random_string(8, "0123456789")
        # Snapshot each product's unit cost so COGS/profit stay accurate even if
        # costs change later.
        costs = dict(Product.objects.filter(
            id__in=[i["id"] for i in items if i.get("id")]
        ).values_list("id", "unit_cost"))
        cost_total = sum(
            (costs.get(i.get("id"), Decimal("0")) * i["qty"] for i in items),
            Decimal("0"),
        )
        order = cls.objects.create(
            number=number, site=site, email=email, name=name, total=total,
            cost_total=cost_total,
            status="paid" if settings.PAYMENTS_LIVE else "pending_payment",
        )
        OrderItem.objects.bulk_create([
            OrderItem(
                order=order, product_id=i.get("id"), product_name=i["name"],
                unit_price=i["price"], unit_cost=costs.get(i.get("id"), Decimal("0")),
                qty=i["qty"], line_total=i["line_total"],
            )
            for i in items
        ])
        # Decrement the shared inventory pool (one stock across every site).
        for i in items:
            if i.get("id"):
                Product.objects.filter(id=i["id"], track_inventory=True).update(
                    stock_qty=F("stock_qty") - i["qty"]
                )
        return order

    @property
    def confirmation_message(self):
        if settings.PAYMENTS_LIVE:
            return f"Order {self.number} confirmed."
        return (
            f"Order {self.number} received. Payment isn't live yet — connect a "
            "processor to charge and fulfil automatically."
        )

    def __str__(self):
        return self.number


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "catalog.Product", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="order_items",
    )
    product_name = models.CharField(max_length=140)
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    qty = models.PositiveIntegerField(default=1)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def line_cost(self):
        return self.unit_cost * self.qty

    @property
    def line_profit(self):
        return self.line_total - self.line_cost

    def __str__(self):
        return f"{self.qty}× {self.product_name}"
