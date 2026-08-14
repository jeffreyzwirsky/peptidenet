from decimal import Decimal

from django.db import models
from django.utils.text import slugify

# Compounds are sold in fixed packs, never as loose vials — the manufacturing
# partner prices and picks per vial but will not break a pack. `Product.pack_size`
# holds the vials per sellable unit (10 for compounds, 1 for supplies).
DEFAULT_PACK_SIZE = 10

# Network-wide "buy more, save more" tiers: (minimum PACKS, % off).
#
# These count packs, not vials. That matters: when the minimum order became one
# 10-vial pack, tiers keyed to vials meant every order cleared the top tier on
# its first item — a permanent extra 15% off dressed up as a volume reward, and
# 15% straight off the margin of the smallest possible order. Counting packs
# restores the intent: the minimum order pays full freight, and a real volume
# commitment (3 packs = 30 vials) is what earns the discount.
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
    list_price = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text="Pre-discount reference price. When set and higher than the sell "
                  "price, the storefront shows it struck through. Leave blank for "
                  "no comparison price.",
    )
    unit_cost = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        help_text="Your landed cost per vial (CAD) — used for margin, COGS and inventory value.",
    )
    # --- cost-plus pricing ---------------------------------------------------
    # `unit_cost` above stays a stored field, not a derived one, because order
    # lines snapshot it at checkout and must not move afterwards. `reprice`
    # writes it from the linked supplier price; these three fields say where it
    # comes from and what to do with it.
    supplier_cat_no = models.CharField(
        max_length=20, blank=True,
        help_text="Supplier catalogue code this product is bought as, e.g. BC10. "
                  "Links cost and retail price to the supplier price list.",
    )
    target_margin_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("75.00"),
        help_text="Gross margin to hold when prices are recalculated from cost.",
    )
    auto_price = models.BooleanField(
        default=False,
        help_text="Recalculate the retail price from cost automatically. "
                  "Off means the price is whatever a human last set.",
    )
    price_updated_at = models.DateTimeField(null=True, blank=True, editable=False)

    pack_size = models.PositiveIntegerField(
        default=DEFAULT_PACK_SIZE,
        help_text="Vials per sellable unit. Compounds ship in packs of 10 and "
                  "cannot be split. Set 1 for supplies (bacteriostatic water, "
                  "syringes) so they can still be bought singly.",
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

    # --- product photography -------------------------------------------------
    # Static paths (same pattern as BlogPost.hero_image), not uploads — the
    # renders are generated by `generate_product_images` and committed to
    # static/products/ so they go through the normal collectstatic + long-cache
    # pipeline. Falls back to the inline SVG vial when empty.
    image = models.CharField(
        max_length=300, blank=True,
        help_text="Primary product image, e.g. /static/products/bpc-157.png",
    )
    image_alt = models.CharField(
        max_length=200, blank=True,
        help_text="Alt text. Auto-generated from the product name when blank.",
    )
    gallery = models.JSONField(
        default=list, blank=True,
        help_text='Extra images: [{"src": "/static/...", "alt": "...", "label": "Label detail"}]',
    )

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

    # --- pack pricing -------------------------------------------------------
    # `price` and `unit_cost` stay per-vial in the database so margin, COGS and
    # the supplier's per-vial invoicing all keep working untouched. Everything
    # the customer sees and buys is a pack, and these derive it.
    @property
    def sells_in_packs(self):
        return (self.pack_size or 1) > 1

    @property
    def vials_per_pack(self):
        return self.pack_size or 1

    @property
    def pack_price(self):
        """What one sellable unit costs the customer."""
        return (self.price * self.vials_per_pack).quantize(Decimal("0.01"))

    @property
    def pack_list_price(self):
        """Struck-through comparison price for a pack, or None."""
        if not self.is_discounted:
            return None
        return (self.list_price * self.vials_per_pack).quantize(Decimal("0.01"))

    @property
    def pack_savings(self):
        if not self.is_discounted:
            return Decimal("0")
        return (self.savings * self.vials_per_pack).quantize(Decimal("0.01"))

    @property
    def pack_cost(self):
        return (self.unit_cost * self.vials_per_pack).quantize(Decimal("0.01"))

    @property
    def pack_label(self):
        """Human unit, e.g. '10-vial pack'. Supplies read 'each'."""
        return f"{self.vials_per_pack}-vial pack" if self.sells_in_packs else "each"

    @property
    def pack_noun(self):
        return "pack" if self.sells_in_packs else "unit"

    @property
    def minimum_order_note(self):
        if not self.sells_in_packs:
            return ""
        return (f"Sold in packs of {self.vials_per_pack} vials — "
                f"{self.vials_per_pack} vials is the minimum order for this compound.")

    # --- discount display ---
    @property
    def is_discounted(self):
        return bool(self.list_price and self.list_price > self.price)

    @property
    def savings(self):
        return (self.list_price - self.price) if self.is_discounted else Decimal("0")

    @property
    def discount_pct(self):
        if not self.is_discounted:
            return 0
        return int(round(self.savings / self.list_price * 100))

    # --- cost-plus derivation ------------------------------------------------
    @property
    def supplier_price(self):
        """The supplier price row this product is bought as, or None."""
        if not self.supplier_cat_no:
            return None
        from apps.suppliers.models import SupplierPrice
        return SupplierPrice.objects.filter(cat_no=self.supplier_cat_no).first()

    def cost_from_supplier(self, currency="CAD"):
        """Landed cost per vial in `currency`, from the supplier price list.

        Returns None rather than a guess when the supplier row is missing or no
        FX rate is available — a silently wrong cost would propagate into the
        retail price, which is the whole risk of automatic repricing.
        """
        sp = self.supplier_price
        if sp is None:
            return None
        return sp.unit_price_in(currency)

    def target_price(self, currency="CAD"):
        """Retail price per vial that holds `target_margin_pct` on cost."""
        cost = self.cost_from_supplier(currency)
        if cost is None:
            return None
        margin = Decimal(self.target_margin_pct or 0)
        if margin >= 100:
            return None
        return (cost / ((Decimal(100) - margin) / Decimal(100))).quantize(Decimal("0.01"))

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

    # --- imagery -------------------------------------------------------------
    @property
    def alt_text(self):
        return self.image_alt or (
            f"{self.name} — lyophilised research compound vial, "
            f"{self.purity} purity, for laboratory research use only"
        )

    @property
    def images(self):
        """Full gallery: primary image first, then extras. Empty when the
        product has no photography yet, so templates fall back to the SVG."""
        out = []
        if self.image:
            out.append({"src": self.image, "alt": self.alt_text, "label": "Vial"})
        for g in (self.gallery or []):
            src = g.get("src")
            if src:
                out.append({
                    "src": src,
                    "alt": g.get("alt") or self.alt_text,
                    "label": g.get("label") or "",
                })
        return out

    @property
    def has_gallery(self):
        return len(self.images) > 1

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
        """Rows for the buy-more-save table.

        `min_qty` counts PACKS. `vials` spells that out for the customer, because
        "3+" next to a per-vial price is the kind of ambiguity that turns into a
        chargeback. Every price here is per pack.
        """
        rows = []
        for min_qty, pct in BULK_DISCOUNT_TIERS:
            unit = (self.pack_price * (Decimal(100 - pct) / Decimal(100))).quantize(Decimal("0.01"))
            rows.append({
                "min_qty": min_qty,
                "pct": pct,
                "unit_price": unit,
                "vials": min_qty * self.vials_per_pack,
                "per_vial": (unit / self.vials_per_pack).quantize(Decimal("0.01")),
            })
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
