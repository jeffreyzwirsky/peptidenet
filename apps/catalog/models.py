from decimal import Decimal

from django.db import models
from django.utils.text import slugify

# Network-wide "buy more, save more" tiers: (minimum vials, % off per vial).
# Applied in the cart and shown on every product page.
BULK_DISCOUNT_TIERS = [(3, 5), (5, 10), (10, 15)]


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

    # --- scientific reference data (shown on the product detail page) ---
    cas_number = models.CharField(max_length=40, blank=True)
    molecular_formula = models.CharField(max_length=120, blank=True)
    molecular_weight = models.CharField(
        max_length=40, blank=True, help_text="g/mol, as a display string e.g. 1419.5"
    )
    sequence = models.TextField(blank=True, help_text="Amino-acid sequence / structure note.")
    synonyms = models.JSONField(default=list, blank=True)
    half_life = models.CharField(max_length=60, blank=True)
    storage = models.CharField(max_length=200, blank=True)
    solubility = models.CharField(max_length=200, blank=True)
    appearance = models.CharField(max_length=120, blank=True)
    research_area = models.TextField(
        blank=True, help_text="One compliant sentence — laboratory research framing only."
    )
    lab_name = models.CharField(
        max_length=80, blank=True, default="Janoshik Analytical",
        help_text="Independent lab that issued the batch COA.",
    )
    lot_number = models.CharField(max_length=40, blank=True)
    faqs = models.JSONField(
        default=list, blank=True,
        help_text='List of {"q":..., "a":...} shown on the product page + as FAQ schema.',
    )

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

    @property
    def has_specs(self):
        """True when there's enough reference data to render a spec table."""
        return any([self.cas_number, self.molecular_formula,
                    self.molecular_weight, self.sequence])

    @property
    def is_blend(self):
        return "+" in self.name or not self.molecular_formula

    # --- reviews / ratings (drives AggregateRating schema) ---
    @property
    def review_qs(self):
        return self.reviews.filter(is_published=True)

    @property
    def rating_count(self):
        return self.review_qs.count()

    @property
    def rating_avg(self):
        from django.db.models import Avg
        v = self.review_qs.aggregate(a=Avg("rating"))["a"]
        return round(v, 1) if v else None

    # --- bulk / tiered pricing ---
    def bulk_tiers(self):
        """List of {min_qty, pct, unit_price} rows for the buy-more-save table."""
        rows = []
        for min_qty, pct in BULK_DISCOUNT_TIERS:
            unit = (self.price * (Decimal(100 - pct) / Decimal(100))).quantize(Decimal("0.01"))
            rows.append({"min_qty": min_qty, "pct": pct, "unit_price": unit})
        return rows

    def auto_faqs(self):
        """Factual, compliance-safe FAQs used for both the on-page accordion and
        FAQPage JSON-LD. Any curated self.faqs come first, then generated ones."""
        out = list(self.faqs or [])
        have = {f.get("q", "").lower() for f in out}

        def add(q, a):
            if a and q.lower() not in have:
                out.append({"q": q, "a": a})

        if self.research_area:
            add(f"What is {self.name} studied for?", self.research_area)
        if self.molecular_formula or self.molecular_weight:
            bits = []
            if self.molecular_formula:
                bits.append(f"molecular formula {self.molecular_formula}")
            if self.molecular_weight:
                bits.append(f"a molecular weight of ~{self.molecular_weight} g/mol")
            if self.cas_number:
                bits.append(f"CAS number {self.cas_number}")
            add(
                f"What is the molecular formula of {self.name}?",
                f"{self.name} has {', and '.join(bits)}.",
            )
        if self.storage or self.solubility:
            parts = [p for p in [self.solubility, self.storage] if p]
            add(f"How is {self.name} stored and reconstituted?", " ".join(parts))
        add(
            f"Is {self.name} for human use?",
            f"No. {self.name} is supplied strictly as a laboratory reference "
            f"material for research use only — not for human or veterinary use.",
        )
        return out[:5]

    def __str__(self):
        return self.name


class Review(models.Model):
    """Researcher reviews — power on-page social proof + AggregateRating schema.
    A review with product=None is a site-wide/general review."""

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="reviews",
        null=True, blank=True,
    )
    author = models.CharField(max_length=80)
    location = models.CharField(max_length=80, blank=True)
    rating = models.PositiveSmallIntegerField(default=5)
    body = models.TextField()
    is_verified = models.BooleanField(default=True)
    is_published = models.BooleanField(default=True)
    created_at = models.DateField(help_text="Display date.")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.author} · {self.rating}★"
