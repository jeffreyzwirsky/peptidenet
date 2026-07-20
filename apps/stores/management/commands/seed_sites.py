from django.core.management.base import BaseCommand

from apps.stores.models import Site

# The 8 launch domains and the theme each renders. Twins (.com/.ca/hyphen) are
# their own Site rows because you asked for a distinct site per name; point one
# at another with `aliases` instead if you'd rather they share.
SITES = [
    {"domain": "smashfatbiolabs.ca", "brand_name": "SmashFat BioLabs", "theme": "biolabs",
     "tagline": "Purity you can prove.", "promo_code": "SMASH10",
     "meta_description": "High-purity research compounds, independently tested, shipped from Canada."},
    {"domain": "smashfatbiolabs.com", "brand_name": "SmashFat BioLabs", "theme": "clinical",
     "tagline": "Reference-grade compounds for precision research.", "promo_code": "LAB10",
     "meta_description": "Analytically certified research peptides with a COA on every lot."},
    {"domain": "smashfat.ca", "brand_name": "SmashFat", "theme": "neon",
     "tagline": "Smash fat. Research-grade.", "promo_code": "BURN10",
     "meta_description": "High-purity metabolic and weight-management research compounds."},
    {"domain": "smash-fat.ca", "brand_name": "Smash Fat", "theme": "apothecary",
     "tagline": "Quiet purity, documented to the lot.", "promo_code": "CALM10",
     "meta_description": "A boutique, compounding-pharmacy-inspired research peptide source."},
    {"domain": "smash-fat.com", "brand_name": "Smash Fat", "theme": "editorial",
     "tagline": "Peptides, with a loud signature.", "promo_code": "NOISE10",
     "meta_description": "A design-forward reference library of high-purity research peptides."},
    {"domain": "peptidesalberta.ca", "brand_name": "Peptides Alberta", "theme": "prairie",
     "tagline": "Research peptides, dispatched from Alberta.", "promo_code": "ALBERTA10",
     "ships_from": "Alberta",
     "meta_description": "Alberta-owned, lab-verified research compounds. Fast provincial dispatch."},
    {"domain": "where-do-i-get-peptides.ca", "brand_name": "Where Do I Get Peptides?", "theme": "guide",
     "tagline": "Where do I get peptides? Right here.", "promo_code": "START10",
     "meta_description": "Straight answers and lab-grade research compounds — purity and COA included."},
    {"domain": "where-do-i-get-peptides.com", "brand_name": "Where Do I Get Peptides?", "theme": "directory",
     "tagline": "The answer is here.", "promo_code": "GUIDE10",
     "meta_description": "The definitive, third-party-tested source for research peptides."},
]


# Network phone numbers (owned Twilio vanity lines). Applied to every site
# unless a site overrides them above. BIOLABS = 246-5227 on the keypad.
PHONE_DEFAULTS = {
    "phone": "1-839-BIOLABS",
    "phone_tel": "+18392465227",
    "phone_alt": "1-325-BIOLABS",
    "phone_alt_tel": "+13252465227",
}


class Command(BaseCommand):
    help = "Seed/refresh the 8 launch storefront Site rows."

    def handle(self, *args, **opts):
        created = updated = 0
        for s in SITES:
            s = {**PHONE_DEFAULTS, **s}  # site-specific values win over phone defaults
            _, was_created = Site.objects.update_or_create(domain=s["domain"], defaults=s)
            created += was_created
            updated += not was_created
        self.stdout.write(self.style.SUCCESS(
            f"Sites seeded: {created} created, {updated} updated "
            f"({Site.objects.count()} total)."
        ))
