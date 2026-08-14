from django.db import models


class Site(models.Model):
    """
    One row per storefront/domain. This registry is the whole 'add a site'
    surface: create a Site (admin or `add_site`), assign a theme, and the same
    shared catalogue is served under that domain. `emit_nginx` / `emit_hosts`
    turn these rows into the nginx server_name blocks + ALLOWED_HOSTS list.
    """

    COUNTRIES = [("CA", "Canada"), ("US", "United States")]
    CURRENCIES = [("CAD", "Canadian dollar"), ("USD", "US dollar")]

    domain = models.CharField(
        max_length=190, unique=True, help_text="Canonical host, e.g. smashfatbiolabs.ca"
    )
    aliases = models.JSONField(
        default=list, blank=True,
        help_text='Extra hosts that resolve to this site, e.g. ["www.smashfatbiolabs.ca"]',
    )
    brand_name = models.CharField(max_length=120)
    theme = models.SlugField(
        max_length=60, help_text="Theme folder under templates/themes/ + static/themes/"
    )
    tagline = models.CharField(max_length=200, blank=True)
    promo_code = models.CharField(max_length=30, blank=True)
    contact_email = models.EmailField(blank=True)
    phone = models.CharField(
        max_length=40, blank=True,
        help_text='Display phone shown in header/hero/footer, e.g. "1-325-BIOLABS" (owned vanity line).',
    )
    phone_tel = models.CharField(
        max_length=40, blank=True,
        help_text='Dialable form for tel: links, e.g. "+13252465227".',
    )
    phone_alt = models.CharField(max_length=40, blank=True, help_text="Secondary display phone.")
    phone_alt_tel = models.CharField(max_length=40, blank=True)
    ships_from = models.CharField(
        max_length=80, blank=True, default="",
        help_text="DEPRECATED — internal note only. Never rendered on the storefront. "
                  "Orders ship direct from the manufacturing partner, so an origin "
                  "claim here would be a false representation.",
    )

    # --- market / geo targeting -------------------------------------------
    # `country` drives hreflang, currency, geo JSON-LD and which keyword set the
    # blog generator uses. `brand_key` groups the .ca/.com twins of one brand so
    # hreflang can pair them and Google stops treating them as duplicates.
    country = models.CharField(
        max_length=2, choices=COUNTRIES, default="CA",
        help_text="Primary market this domain targets. .ca -> CA, .com -> US.",
    )
    currency = models.CharField(
        max_length=3, choices=CURRENCIES, default="CAD",
        help_text="Display + schema currency for this storefront.",
    )
    brand_key = models.SlugField(
        max_length=80, blank=True,
        help_text="Sites sharing a brand_key are hreflang twins (e.g. the .ca and "
                  ".com of one brand). Leave blank for a standalone site.",
    )

    # --- fulfilment ---------------------------------------------------------
    # Orders are dropshipped: the manufacturing partner ships direct to the
    # customer. These drive the shipping disclosure shown on the product page,
    # in the cart, at checkout and in the confirmation email.
    shipping_min_days = models.PositiveSmallIntegerField(default=10)
    shipping_max_days = models.PositiveSmallIntegerField(default=15)

    meta_description = models.CharField(max_length=300, blank=True)
    # Optional per-site theme variable overrides (e.g. {"accent": "#c6ff00"}).
    palette = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["domain"]

    def all_hostnames(self):
        hosts = [self.domain] + list(self.aliases or [])
        # Always accept the www. variant of the canonical domain.
        if not self.domain.startswith("www."):
            hosts.append("www." + self.domain)
        return sorted(set(hosts))

    @property
    def contact_email_or_default(self):
        return self.contact_email or f"info@{self.domain}"

    @property
    def is_smash_brand(self):
        """True for the SMASH-branded storefronts (gets the SMASH logo + favicon).
        The Peptides Alberta / Where-Do-I-Get sites keep their own identity."""
        return "smash" in (self.brand_name or "").lower()

    @property
    def phone_tel_or_derived(self):
        """Dialable number: explicit phone_tel, else digits stripped from `phone`."""
        if self.phone_tel:
            return self.phone_tel
        if self.phone:
            digits = "".join(c for c in self.phone if c.isdigit())
            return ("+" + digits) if digits else ""
        return ""

    @property
    def phone_alt_tel_or_derived(self):
        if self.phone_alt_tel:
            return self.phone_alt_tel
        if self.phone_alt:
            digits = "".join(c for c in self.phone_alt if c.isdigit())
            return ("+" + digits) if digits else ""
        return ""

    # --- geo / SEO helpers --------------------------------------------------
    @property
    def hreflang(self):
        """BCP-47 tag for this storefront, e.g. 'en-ca'."""
        return f"en-{self.country.lower()}"

    @property
    def country_name(self):
        return dict(self.COUNTRIES).get(self.country, "Canada")

    @property
    def currency_symbol(self):
        return "$"

    def twins(self):
        """Sibling storefronts of the same brand in other markets. Drives the
        hreflang alternates. Returns [] for a standalone site — emitting
        hreflang with no real alternate is worse than emitting none."""
        if not self.brand_key:
            return []
        return list(
            Site.objects.filter(brand_key=self.brand_key, is_active=True)
            .exclude(pk=self.pk)
        )

    def alternates(self):
        """Self + twins, for building the full hreflang block. Only returns
        rows when a genuine alternate exists."""
        sibs = self.twins()
        return ([self] + sibs) if sibs else []

    # --- fulfilment helpers -------------------------------------------------
    @property
    def shipping_window(self):
        """e.g. '10–15 days' — the single source of truth for the delivery
        promise shown on the product page, cart, checkout and email."""
        return f"{self.shipping_min_days}–{self.shipping_max_days} days"

    @property
    def shipping_notice(self):
        """One plain sentence stating the delivery window. Deliberately makes no
        claim about where goods ship from."""
        return (
            f"Orders ship directly from our manufacturing partner. "
            f"Allow {self.shipping_window} for delivery."
        )

    @property
    def customs_notice(self):
        """Shipments may cross a border, so the buyer is told customs can apply.
        States no country of origin."""
        return "Shipments may be subject to customs clearance, which can affect delivery time."

    def __str__(self):
        return f"{self.brand_name} ({self.domain})"
