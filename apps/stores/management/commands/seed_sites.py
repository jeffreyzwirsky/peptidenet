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
SITES = [
    # ---------------- Canada (.ca) ----------------
    {"domain": "smashfatbiolabs.ca", "brand_name": "SmashFat BioLabs", "theme": "biolabs",
     "country": "CA", "currency": "CAD", "brand_key": "smashfatbiolabs",
     "tagline": "We only claim what we can show.", "promo_code": "SMASH10",
     "meta_description": "Research compounds for Canadian laboratories. Sold uncharacterised — "
                         "we hold no analysis and say so. 10–15 day delivery."},
    {"domain": "smashfat.ca", "brand_name": "SmashFat", "theme": "neon",
     "country": "CA", "currency": "CAD", "brand_key": "smashfat",
     "tagline": "Smash fat. Research-grade.", "promo_code": "BURN10",
     "meta_description": "Metabolic research compounds for Canadian "
                         "researchers — GLP-1, GIP and mitochondrial targets."},
    {"domain": "smash-fat.ca", "brand_name": "Smash Fat", "theme": "apothecary",
     "country": "CA", "currency": "CAD", "brand_key": "smash-fat",
     "tagline": "A small formulary, plainly described.", "promo_code": "CALM10",
     "meta_description": "A boutique research peptide source for Canada — lyophilised, "
                         "carefully handled, and sold uncharacterised."},
    {"domain": "peptidesalberta.ca", "brand_name": "Peptides Alberta", "theme": "prairie",
     "country": "CA", "currency": "CAD", "brand_key": "peptidesalberta",
     "tagline": "Research peptides for Alberta labs.", "promo_code": "ALBERTA10",
     "meta_description": "Research compounds for laboratories in Calgary, Edmonton "
                         "and across Alberta. Sold uncharacterised — we hold no analysis."},
    {"domain": "where-do-i-get-peptides.ca", "brand_name": "Where Do I Get Peptides?", "theme": "guide",
     "country": "CA", "currency": "CAD", "brand_key": "where-do-i-get-peptides",
     "tagline": "Where do I get peptides? Right here.", "promo_code": "START10",
     "meta_description": "Straight answers for Canadian buyers, a working catalogue, "
                         "and an honest account of what we don't hold."},

    # ---------------- United States (.com) ----------------
    {"domain": "smashfatbiolabs.com", "brand_name": "SmashFat BioLabs", "theme": "clinical",
     "country": "US", "currency": "USD", "brand_key": "smashfatbiolabs",
     "tagline": "Plainly described compounds for precision research.", "promo_code": "LAB10",
     "meta_description": "Research peptides for US laboratories, sold uncharacterised, "
                         "with no analysis claimed."},
    {"domain": "smash-fat.com", "brand_name": "Smash Fat", "theme": "editorial",
     "country": "US", "currency": "USD", "brand_key": "smash-fat",
     "tagline": "Peptides, with a loud signature.", "promo_code": "NOISE10",
     "meta_description": "A design-forward reference library of research peptides, "
                         "with published structural data for every compound."},
    {"domain": "where-do-i-get-peptides.com", "brand_name": "Where Do I Get Peptides?", "theme": "directory",
     "country": "US", "currency": "USD", "brand_key": "where-do-i-get-peptides",
     "tagline": "The answer is here.", "promo_code": "GUIDE10",
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
