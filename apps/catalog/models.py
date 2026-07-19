from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    """A research category shared across every site (Metabolic, Mitochondrial…)."""

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True, blank=True)
    # Accent colour used to tint the vial cap / badges per category.
    color = models.CharField(max_length=9, default="#4f8ff7")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Product(models.Model):
    """
    One shared catalogue for the whole network. Edit a product once here and it
    updates on every site that renders it. Sizes/purity are display metadata.
    """

    STOCK_CHOICES = [("in", "In stock"), ("low", "Low stock"), ("out", "Out of stock")]

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="products"
    )
    price = models.DecimalField(max_digits=8, decimal_places=2, help_text="CAD sell price per vial")
    unit_cost = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        help_text="Your landed cost per vial (CAD) — used for margin, COGS and inventory value.",
    )
    purity = models.CharField(max_length=20, default="≥99%")
    sizes = models.JSONField(default=list, help_text='e.g. ["10mg", "50mg"]')
    stock = models.CharField(
        max_length=3, choices=STOCK_CHOICES, default="in",
        help_text="Manual status, used only when inventory tracking is off.",
    )
    track_inventory = models.BooleanField(default=True)
    stock_qty = models.IntegerField(default=0, help_text="Vials on hand (shared across all sites).")
    low_stock_threshold = models.PositiveIntegerField(default=5)
    is_new = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    coa_url = models.URLField(blank=True, help_text="Link to the batch COA PDF, if any")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def stock_state(self):
        """in / low / out — from real quantity when tracked, else the manual field."""
        if not self.track_inventory:
            return self.stock
        if self.stock_qty <= 0:
            return "out"
        if self.stock_qty <= self.low_stock_threshold:
            return "low"
        return "in"

    @property
    def stock_state_label(self):
        return dict(self.STOCK_CHOICES).get(self.stock_state, "In stock")

    @property
    def stock_label(self):  # kept for template back-compat
        return self.stock_state_label

    # --- cost / margin economics ---
    @property
    def margin(self):
        """Profit per vial (sell price − unit cost)."""
        return self.price - self.unit_cost

    @property
    def margin_pct(self):
        if not self.price:
            return 0
        return round(self.margin / self.price * 100, 1)

    @property
    def stock_value_cost(self):
        """Value of on-hand inventory at cost."""
        return self.unit_cost * max(self.stock_qty, 0)

    @property
    def stock_value_retail(self):
        return self.price * max(self.stock_qty, 0)

    @property
    def has_coa(self):
        return bool(self.coa_url)

    def __str__(self):
        return self.name
