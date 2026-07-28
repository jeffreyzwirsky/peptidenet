"""
Dropship supply chain.

The customer buys from us; we buy from a manufacturing partner who ships direct
to the customer. This app models that second leg — who the partner is, how we
reach them, and one PurchaseOrder per customer order.

Nothing here contacts anyone on its own. A PurchaseOrder is *built* by the
system and *sent* by a human from the control panel, because the channels are
email and WhatsApp and both need a person in the loop.
"""
from decimal import Decimal

from django.db import models
from django.utils.crypto import get_random_string


class Supplier(models.Model):
    """A manufacturing partner we place dropship orders with."""

    CHANNELS = [
        ("email", "Email"),
        ("whatsapp", "WhatsApp"),
    ]

    name = models.CharField(max_length=140)
    slug = models.SlugField(max_length=160, unique=True)
    contact_name = models.CharField(max_length=140, blank=True)
    email = models.EmailField(blank=True)
    whatsapp = models.CharField(
        max_length=40, blank=True,
        help_text="E.164, e.g. +8613800000000. Used to build the wa.me link.",
    )
    preferred_channel = models.CharField(
        max_length=20, choices=CHANNELS, default="email",
        help_text="Where purchase orders go by default.",
    )

    # --- commercial terms ---------------------------------------------------
    currency = models.CharField(
        max_length=3, default="USD",
        help_text="Currency the supplier invoices us in.",
    )
    lead_time_min_days = models.PositiveSmallIntegerField(
        default=10, help_text="Order placed -> delivered to our customer.",
    )
    lead_time_max_days = models.PositiveSmallIntegerField(default=15)
    minimum_order_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="MOQ in the supplier's currency. 0 = none.",
    )
    payment_terms = models.CharField(
        max_length=200, blank=True,
        help_text="How we pay them, e.g. 'Alipay on order, 50/50'.",
    )
    notes = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(
        default=False,
        help_text="Used when a product has no supplier of its own.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    @classmethod
    def get_default(cls):
        return (
            cls.objects.filter(is_active=True, is_default=True).first()
            or cls.objects.filter(is_active=True).first()
        )

    @property
    def whatsapp_link(self):
        """wa.me link for the control panel's 'Send on WhatsApp' button."""
        if not self.whatsapp:
            return ""
        return "https://wa.me/" + "".join(c for c in self.whatsapp if c.isdigit())

    @property
    def lead_time_window(self):
        return f"{self.lead_time_min_days}–{self.lead_time_max_days} days"

    def __str__(self):
        return self.name


class PurchaseOrder(models.Model):
    """
    What we ask the manufacturing partner to ship, for one customer order.

    Raised only after the customer's payment is confirmed — we never commit to
    a supplier on an unpaid order.
    """

    STATUS = [
        ("draft", "Draft"),            # built, not yet sent
        ("sent", "Sent to supplier"),
        ("confirmed", "Confirmed by supplier"),
        ("shipped", "Shipped"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
        ("problem", "Problem"),        # seized, lost, refused, out of stock
    ]

    number = models.CharField(max_length=24, unique=True, editable=False)
    order = models.OneToOneField(
        "orders.Order", on_delete=models.PROTECT, related_name="purchase_order",
    )
    supplier = models.ForeignKey(
        Supplier, on_delete=models.PROTECT, related_name="purchase_orders",
    )
    status = models.CharField(max_length=20, choices=STATUS, default="draft")

    # Where the supplier ships. Copied from the order at build time so an edit
    # to the customer record can't silently redirect a PO already in flight.
    ship_to = models.TextField(blank=True)

    cost_total = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="What we owe the supplier, in their currency.",
    )
    channel = models.CharField(
        max_length=20, choices=Supplier.CHANNELS, blank=True,
        help_text="How this PO was actually sent.",
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    sent_by = models.CharField(max_length=140, blank=True)
    supplier_reference = models.CharField(
        max_length=140, blank=True, help_text="Their order number, if they give one.",
    )
    tracking_number = models.CharField(max_length=120, blank=True)
    tracking_carrier = models.CharField(max_length=80, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @classmethod
    def build_for(cls, order, supplier=None):
        """
        Create a draft PO from a paid customer order. Idempotent — calling it
        twice returns the existing PO rather than double-ordering.
        """
        existing = cls.objects.filter(order=order).first()
        if existing:
            return existing

        supplier = supplier or Supplier.get_default()
        if supplier is None:
            raise ValueError(
                "No active supplier configured — add one in the control panel "
                "before raising purchase orders."
            )

        po = cls.objects.create(
            number="PO-" + get_random_string(8, "0123456789"),
            order=order,
            supplier=supplier,
            ship_to=order.shipping_address,
            cost_total=order.cost_total or Decimal("0"),
        )
        PurchaseOrderItem.objects.bulk_create([
            PurchaseOrderItem(
                purchase_order=po,
                product=item.product,
                product_name=item.product_name,
                qty=item.qty,
                unit_cost=item.unit_cost,
                line_cost=item.unit_cost * item.qty,
            )
            for item in order.items.all()
        ])
        return po

    def mark_sent(self, channel="", by="", when=None):
        from django.utils import timezone
        self.status = "sent"
        self.channel = channel or self.supplier.preferred_channel
        self.sent_at = when or timezone.now()
        self.sent_by = by or self.sent_by
        self.save(update_fields=["status", "channel", "sent_at", "sent_by"])
        if self.order.status in ("paid",):
            self.order.status = "po_sent"
            self.order.save(update_fields=["status"])
        return self

    def mark_shipped(self, tracking_number="", carrier=""):
        """Record the supplier's tracking and push it onto the customer order so
        the buyer can see it on their status page."""
        self.status = "shipped"
        self.tracking_number = tracking_number or self.tracking_number
        self.tracking_carrier = carrier or self.tracking_carrier
        self.save(update_fields=["status", "tracking_number", "tracking_carrier"])
        self.order.mark_shipped(
            tracking_number=self.tracking_number, carrier=self.tracking_carrier
        )
        return self

    @property
    def is_overdue(self):
        """True when the supplier's own lead time has run out and nothing has
        shipped. Drives the 'needs chasing' list in the control panel."""
        import datetime

        from django.utils import timezone
        if self.status in ("shipped", "delivered", "cancelled"):
            return False
        if not self.sent_at:
            return False
        due = self.sent_at + datetime.timedelta(days=self.supplier.lead_time_max_days)
        return timezone.now() > due

    def __str__(self):
        return f"{self.number} → {self.supplier.name}"


class PurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE, related_name="items",
    )
    product = models.ForeignKey(
        "catalog.Product", null=True, blank=True, on_delete=models.SET_NULL,
    )
    product_name = models.CharField(max_length=140)
    qty = models.PositiveIntegerField(default=1)
    unit_cost = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    line_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.qty}× {self.product_name}"
