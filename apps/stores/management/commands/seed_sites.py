from django.core.management.base import BaseCommand

from apps.stores.models import Site

# The 8 launch domains and the theme each renders.
#
# Three things every row must respect:
#
#  * `country` — .ca serves Canada, .com serves the United States. This drives
#    hreflang, currency, geo schema and which blog keyword set the site uses.
#  * `brand_key` — sites sharing a key are hreflang twins. Without this the
#    three .ca/.com pairs read as duplicate content and Google suppresses one
#    of each pair.
#  * No origin claims. Orders ship direct from the manufacturing partner, so
#    no tagline or meta description may say or imply where goods ship from.
#    `ships_from` is deliberately left empty everywhere.
# ---------------------------------------------------------------------------
# COMPLIANCE REMEDIATION 2026-08-16 - READ BEFORE ADDING A SITE
#
# Six of these eight domains are, on their face, representations of consumer
# intent and cannot be cured by copy:
#
#   smashfat.ca / smash-fat.ca / smash-fat.com / smashfatbiolabs.ca /
#   smashfatbiolabs.com  - the brand is a weight-loss claim. Under 21 CFR
#   201.128 intended use is inferred from the totality of the circumstances,
#   and a domain name is the top-level circumstance: it is what appears in
#   every search result, link, email header and browser tab.
#
#   where-do-i-get-peptides.ca / .com - built to capture individual-consumer
#   search intent, addressed in their own copy to "Canadian buyers".
#
# Taglines and promo codes that stated or implied a body-composition outcome
# ("Smash fat. Research-grade.", BURN10) have been blanked here. That is a
# holding action, not a fix. THE DOMAINS THEMSELVES ARE THE FINDING and the
# remediation is to retire or rename them, and to consolidate eight
# same-catalogue storefronts down to one supplier on one domain.
#
# Promo codes are blanked network-wide: discount urgency on an unapproved
# compound is a retail device, and BURN10 was a fat-loss promise in a coupon.
# ---------------------------------------------------------------------------
SITES = [
    # ---------------- Canada (.ca) ----------------
    {"domain": "smashfatbiolabs.ca", "brand_name": "SmashFat BioLabs", "theme": "biolabs",
     "country": "CA", "currency": "CAD", "brand_key": "smashfatbiolabs",
     "tagline": "We only claim what we can show.", "promo_code": "",
     "meta_description": "Research compounds for Canadian laboratories. Sold uncharacterised — "
                         "we hold no analysis and say so. 10–15 day delivery."},
    {"domain": "smashfat.ca", "brand_name": "SmashFat", "theme": "neon",
     "country": "CA", "currency": "CAD", "brand_key": "smashfat",
     "tagline": "For qualified laboratory research only.", "promo_code": "",
     "meta_description": "Uncharacterised research compounds for qualified Canadian institutions "
                         "and businesses. No analytical documentation is held or claimed."},
    {"domain": "smash-fat.ca", "brand_name": "Smash Fat", "theme": "apothecary",
     "country": "CA", "currency": "CAD", "brand_key": "smash-fat",
     "tagline": "A small formulary, plainly described.", "promo_code": "",
     "meta_description": "A boutique research peptide source for Canada — lyophilised, "
                         "carefully handled, and sold uncharacterised."},
    {"domain": "peptidesalberta.ca", "brand_name": "Peptides Alberta", "theme": "prairie",
     "country": "CA", "currency": "CAD", "brand_key": "peptidesalberta",
     "tagline": "Research peptides for Alberta labs.", "promo_code": "",
     "meta_description": "Research compounds for laboratories in Calgary, Edmonton "
                         "and across Alberta. Sold uncharacterised — we hold no analysis."},
    {"domain": "where-do-i-get-peptides.ca", "brand_name": "Where Do I Get Peptides?", "theme": "guide",
     "country": "CA", "currency": "CAD", "brand_key": "where-do-i-get-peptides",
     "tagline": "A buyer's guide to uncharacterised research compounds.", "promo_code": "",
     "meta_description": "A Canadian laboratory buyer's guide to research-compound documentation, "
                         "supplier questions and handling terms. Materials are sold uncharacterised."},

    # ---------------- United States (.com) ----------------
    {"domain": "smashfatbiolabs.com", "brand_name": "SmashFat BioLabs", "theme": "clinical",
     "country": "US", "currency": "USD", "brand_key": "smashfatbiolabs",
     "tagline": "Plainly described compounds for precision research.", "promo_code": "",
     "meta_description": "Research peptides for US laboratories, sold uncharacterised, "
                         "with no analysis claimed."},
    {"domain": "smash-fat.com", "brand_name": "Smash Fat", "theme": "editorial",
     "country": "US", "currency": "USD", "brand_key": "smash-fat",
     "tagline": "", "promo_code": "",
     "meta_description": "A design-forward reference library of research peptides, "
                         "with published structural data for every compound."},
    {"domain": "where-do-i-get-peptides.com", "brand_name": "Where Do I Get Peptides?", "theme": "directory",
     "country": "US", "currency": "USD", "brand_key": "where-do-i-get-peptides",
     "tagline": "", "promo_code": "",
     "meta_description": "How to vet a research peptide supplier — and an honest "
                         "source that tells you plainly where it falls short."},
]


# Network phone numbers (owned Twilio vanity lines). Applied to every site
# unless a site overrides them above. BIOLABS = 246-5227 on the keypad.
PHONE_DEFAULTS = {
    "phone": "1-325-BIOLABS",
    "phone_tel": "+13252465227",
    "phone_alt": "",
    "phone_alt_tel": "",
}

# Fulfilment defaults applied to every site. `ships_from` is force-blanked here:
# goods ship direct from the manufacturing partner, so any origin claim on the
# storefront would be a false representation.
FULFILMENT_DEFAULTS = {
    "ships_from": "",
    "shipping_min_days": 10,
    "shipping_max_days": 15,
}


class Command(BaseCommand):
    help = "Seed/refresh the 8 launch storefront Site rows."

    def handle(self, *args, **opts):
        created = updated = 0
        for s in SITES:
            # Site-specific values win over the shared defaults.
            s = {**PHONE_DEFAULTS, **FULFILMENT_DEFAULTS, **s}
            _, was_created = Site.objects.update_or_create(domain=s["domain"], defaults=s)
            created += was_created
            updated += not was_created
        self.stdout.write(self.style.SUCCESS(
            f"Sites seeded: {created} created, {updated} updated "
            f"({Site.objects.count()} total)."
        ))
