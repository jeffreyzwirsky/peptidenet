from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils.crypto import get_random_string


class Order(models.Model):
    """
    A customer order in the dropship flow.

    Money and goods move like this:
      1. Customer pays (Interac e-Transfer, crypto, Alipay or Western Union —
         all manually confirmed, so an order sits in `payment_review` until a
         human marks it received).
      2. Once paid, a PurchaseOrder is raised against the manufacturing partner
         and sent by email or WhatsApp (`po_sent`).
      3. The partner ships direct to the customer (`supplier_shipped`), we
         record the tracking number, and the order runs to `delivered`.

    We never hold the stock, so nothing is decremented from an owned pool.
    """

    STATUS = [
        ("pending_payment", "Pending payment"),   # awaiting customer payment
        ("payment_review", "Payment in review"),  # customer says sent, not yet confirmed
        ("paid", "Paid"),                         # funds confirmed
        ("po_sent", "Ordered from supplier"),     # PO raised + sent
        ("supplier_shipped", "Shipped by supplier"),
        ("in_transit", "In transit"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
        ("refunded", "Refunded"),
    ]

    # Statuses that mean the money has landed — used for revenue reporting.
    PAID_STATUSES = ("paid", "po_sent", "supplier_shipped", "in_transit", "delivered")
    OPEN_STATUSES = ("pending_payment", "payment_review")

    PAYMENT_METHODS = [
        ("interac", "Interac e-Transfer"),
        ("crypto", "Cryptocurrency"),
        ("alipay", "Alipay"),
        ("western_union", "Western Union"),
        ("other", "Other"),
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

    # --- payment ------------------------------------------------------------
    payment_method = models.CharField(
        max_length=20, choices=PAYMENT_METHODS, blank=True,
        help_text="How the customer chose to pay. All methods are confirmed by hand.",
    )
    payment_reference = models.CharField(
        max_length=140, blank=True,
        help_text="Interac reference, transaction hash, Alipay/WU receipt number.",
    )
    paid_at = models.DateTimeField(null=True, blank=True)

    # --- fulfilment ---------------------------------------------------------
    shipping_address = models.TextField(
        blank=True, help_text="Where the manufacturing partner ships to.",
    )
    tracking_number = models.CharField(max_length=120, blank=True)
    tracking_carrier = models.CharField(max_length=80, blank=True)
    tracking_url = models.URLField(blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    # Snapshot of the promise made at checkout, so a later policy change never
    # rewrites what this customer was actually told.
    promised_min_days = models.PositiveSmallIntegerField(default=10)
    promised_max_days = models.PositiveSmallIntegerField(default=15)

    @property
    def profit(self):
        return self.total - self.cost_total

    @property
    def margin_pct(self):
        return round(self.profit / self.total * 100, 1) if self.total else 0

    @property
    def is_paid(self):
        return self.status in self.PAID_STATUSES

    @property
    def promised_window(self):
        return f"{self.promised_min_days}–{self.promised_max_days} days"

    @property
    def expected_delivery_range(self):
        """(earliest, latest) dates the customer was promised, measured from
        payment if we have it, else from when the order was placed."""
        import datetime
        start = (self.paid_at or self.created_at)
        if not start:
            return None
        start = start.date()
        return (
            start + datetime.timedelta(days=self.promised_min_days),
            start + datetime.timedelta(days=self.promised_max_days),
        )

    def mark_paid(self, method="", reference="", when=None):
        """Confirm funds received. Kept as an explicit call — payment is
        manually verified, never inferred."""
        from django.utils import timezone
        self.status = "paid"
        self.paid_at = when or timezone.now()
        if method:
            self.payment_method = method
        if reference:
            self.payment_reference = reference
        self.save(update_fields=["status", "paid_at", "payment_method",
                                 "payment_reference"])
        return self

    def mark_shipped(self, tracking_number="", carrier="", url="", when=None):
        from django.utils import timezone
        self.status = "supplier_shipped"
        self.shipped_at = when or timezone.now()
        self.tracking_number = tracking_number or self.tracking_number
        self.tracking_carrier = carrier or self.tracking_carrier
        self.tracking_url = url or self.tracking_url
        self.save(update_fields=["status", "shipped_at", "tracking_number",
                                 "tracking_carrier", "tracking_url"])
        return self

    class Meta:
        ordering = ["-created_at"]

    @classmethod
    def create_from_cart(cls, site, items, total, email="", name="",
                         payment_method="", shipping_address=""):
        from decimal import Decimal

        from django.db.models import F

        from apps.catalog.models import Product

        number = "SFB-" + get_random_string(8, "0123456789")
        # Snapshot each product's unit cost so COGS/profit stay accurate even if
        # costs change later.
        #
        # `unit_cost` on Product is PER VIAL, but a cart line's qty counts PACKS.
        # Multiplying the two directly understates cost of goods by the pack size
        # — a factor of ten on every compound — which would have shown ~95% margins
        # on orders that actually earn ~50%. Scale to the pack before doing any
        # arithmetic with qty.
        costs = dict(Product.objects.filter(
            id__in=[i["id"] for i in items if i.get("id")]
        ).values_list("id", "unit_cost"))
        pack_cost = {
            i["id"]: (costs.get(i["id"], Decimal("0")) * (i.get("pack_size") or 1))
            for i in items if i.get("id")
        }
        cost_total = sum(
            (pack_cost.get(i.get("id"), Decimal("0")) * i["qty"] for i in items),
            Decimal("0"),
        )
        order = cls.objects.create(
            number=number, site=site, email=email, name=name, total=total,
            cost_total=cost_total,
            payment_method=payment_method,
            shipping_address=shipping_address,
            promised_min_days=getattr(site, "shipping_min_days", 10),
            promised_max_days=getattr(site, "shipping_max_days", 15),
            # Every accepted payment method is confirmed by a human, so a new
            # order waits in review rather than jumping straight to paid.
            status="payment_review" if settings.PAYMENTS_LIVE else "pending_payment",
        )
        OrderItem.objects.bulk_create([
            OrderItem(
                order=order, product_id=i.get("id"), product_name=i["name"],
                # The price actually charged per pack, after any bulk tier — so
                # unit_price × qty == line_total and the invoice reconciles.
                unit_price=i.get("unit_price") or i["price"],
                unit_cost=pack_cost.get(i.get("id"), Decimal("0")),
                qty=i["qty"],
                pack_size=i.get("pack_size") or 1,
                line_total=i["line_total"],
            )
            for i in items
        ])
        # Under dropship we hold no stock — the manufacturing partner ships
        # direct, so there is no owned pool to decrement. `stock_qty` becomes a
        # supplier-availability signal that a human maintains. Set
        # PEPTIDENET_DROPSHIP=0 to restore the old owned-inventory behaviour.
        if not settings.DROPSHIP:
            for i in items:
                if i.get("id"):
                    # stock_qty is counted in vials, qty in packs.
                    Product.objects.filter(id=i["id"], track_inventory=True).update(
                        stock_qty=F("stock_qty") - (i["qty"] * (i.get("pack_size") or 1))
                    )
        return order

    @property
    def confirmation_message(self):
        window = self.promised_window
        if settings.PAYMENTS_LIVE:
            return (
                f"Order {self.number} received. We'll confirm your payment, then "
                f"your order ships directly from our manufacturing partner — "
                f"allow {window} for delivery."
            )
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
    # Both of these are PER SELLABLE UNIT — i.e. per pack, not per vial — so
    # that unit_price × qty reconciles to line_total on the face of an invoice.
    # Per-vial figures are derived below; `pack_size` is snapshotted so a later
    # change to how a compound is packed can't retroactively rewrite an old
    # order's arithmetic.
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    qty = models.PositiveIntegerField(default=1, help_text="Packs ordered.")
    pack_size = models.PositiveIntegerField(default=1, help_text="Vials per pack at time of order.")
    line_total = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def vials(self):
        """What the manufacturing partner actually picks and ships."""
        return self.qty * (self.pack_size or 1)

    @property
    def unit_price_per_vial(self):
        return (self.unit_price / (self.pack_size or 1)).quantize(Decimal("0.01"))

    @property
    def unit_cost_per_vial(self):
        return (self.unit_cost / (self.pack_size or 1)).quantize(Decimal("0.01"))

    @property
    def line_cost(self):
        return self.unit_cost * self.qty

    @property
    def line_profit(self):
        return self.line_total - self.line_cost

    @property
    def qty_label(self):
        if (self.pack_size or 1) > 1:
            return f"{self.qty} × {self.pack_size}-vial pack ({self.vials} vials)"
        return f"{self.qty} ×"

    def __str__(self):
        return f"{self.qty_label} {self.product_name}"
