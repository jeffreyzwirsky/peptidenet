from django.db import models


class Site(models.Model):
    """
    One row per storefront/domain. This registry is the whole 'add a site'
    surface: create a Site (admin or `add_site`), assign a theme, and the same
    shared catalogue is served under that domain. `emit_nginx` / `emit_hosts`
    turn these rows into the nginx server_name blocks + ALLOWED_HOSTS list.
    """

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
        help_text='Display phone shown in header/hero/footer, e.g. "1-839-BIOLABS".',
    )
    phone_tel = models.CharField(
        max_length=40, blank=True,
        help_text='Dialable form for tel: links, e.g. "+18392465227".',
    )
    phone_alt = models.CharField(max_length=40, blank=True, help_text="Secondary display phone.")
    phone_alt_tel = models.CharField(max_length=40, blank=True)
    ships_from = models.CharField(max_length=80, default="Canada")
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

    def __str__(self):
        return f"{self.brand_name} ({self.domain})"
