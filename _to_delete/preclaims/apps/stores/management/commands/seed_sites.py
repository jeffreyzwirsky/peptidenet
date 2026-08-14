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
     "tagline": "Purity you can prove.", "promo_code": "SMASH10",
     "meta_description": "High-purity research compounds for Canadian laboratories, "
                         "independently tested with a COA on every lot."},
    {"domain": "smashfat.ca", "brand_name": "SmashFat", "theme": "neon",
     "country": "CA", "currency": "CAD", "brand_key": "smashfat",
     "tagline": "Smash fat. Research-grade.", "promo_code": "BURN10",
     "meta_description": "High-purity metabolic research compounds for Canadian "
                         "researchers — GLP-1, GIP and mitochondrial targets."},
    {"domain": "smash-fat.ca", "brand_name": "Smash Fat", "theme": "apothecary",
     "country": "CA", "currency": "CAD", "brand_key": "smash-fat",
     "tagline": "Quiet purity, documented to the lot.", "promo_code": "CALM10",
     "meta_description": "A boutique research peptide source for Canada — lyophilised, "
                         "batch-documented, handled with care."},
    {"domain": "peptidesalberta.ca", "brand_name": "Peptides Alberta", "theme": "prairie",
     "country": "CA", "currency": "CAD", "brand_key": "peptidesalberta",
     "tagline": "Research peptides for Alberta labs.", "promo_code": "ALBERTA10",
     "meta_description": "Lab-verified research compounds for researchers in Calgary, "
                         "Edmonton and across Alberta. COA on every lot."},
    {"domain": "where-do-i-get-peptides.ca", "brand_name": "Where Do I Get Peptides?", "theme": "guide",
     "country": "CA", "currency": "CAD", "brand_key": "where-do-i-get-peptides",
     "tagline": "Where do I get peptides? Right here.", "promo_code": "START10",
     "meta_description": "Straight answers for Canadian buyers and lab-grade research "
                         "compounds — purity and COA included."},

    # ---------------- United States (.com) ----------------
    {"domain": "smashfatbiolabs.com", "brand_name": "SmashFat BioLabs", "theme": "clinical",
     "country": "US", "currency": "USD", "brand_key": "smashfatbiolabs",
     "tagline": "Reference-grade compounds for precision research.", "promo_code": "LAB10",
     "meta_description": "Analytically certified research peptides for US laboratories, "
                         "with a COA on every lot."},
    {"domain": "smash-fat.com", "brand_name": "Smash Fat", "theme": "editorial",
     "country": "US", "currency": "USD", "brand_key": "smash-fat",
     "tagline": "Peptides, with a loud signature.", "promo_code": "NOISE10",
     "meta_description": "A design-forward reference library of high-purity research "
                         "peptides, with full molecular data on every compound."},
    {"domain": "where-do-i-get-peptides.com", "brand_name": "Where Do I Get Peptides?", "theme": "directory",
     "country": "US", "currency": "USD", "brand_key": "where-do-i-get-peptides",
     "tagline": "The answer is here.", "promo_code": "GUIDE10",
     "meta_description": "How to vet a research peptide supplier — and a third-party "
                         "tested source that meets the checklist."},
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
