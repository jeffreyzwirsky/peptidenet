from django.core.management.base import BaseCommand, CommandError

from apps.stores.models import Site

AVAILABLE_THEMES = [
    "biolabs", "clinical", "neon", "apothecary",
    "editorial", "prairie", "guide", "directory",
]


class Command(BaseCommand):
    help = "Add a new storefront in one line. Then run emit_nginx + emit_hosts."

    def add_arguments(self, parser):
        parser.add_argument("domain")
        parser.add_argument("--brand", required=True)
        parser.add_argument("--theme", default="biolabs")
        parser.add_argument("--tagline", default="")
        parser.add_argument("--promo", default="")
        parser.add_argument("--email", default="")
        parser.add_argument("--ships-from", default="Canada")
        parser.add_argument("--alias", action="append", default=[],
                            help="Extra host that resolves here (repeatable).")

    def handle(self, *args, **o):
        if o["theme"] not in AVAILABLE_THEMES:
            raise CommandError(
                f"Unknown theme '{o['theme']}'. Available: {', '.join(AVAILABLE_THEMES)}"
            )
        site, created = Site.objects.update_or_create(
            domain=o["domain"],
            defaults=dict(
                brand_name=o["brand"], theme=o["theme"], tagline=o["tagline"],
                promo_code=o["promo"], contact_email=o["email"],
                ships_from=o["ships_from"], aliases=o["alias"],
            ),
        )
        verb = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"{verb} {site.domain} → theme '{site.theme}'."))
        self.stdout.write("Next: manage.py emit_nginx > deploy/nginx.conf  &&  "
                          "manage.py emit_hosts  (then reload nginx + gunicorn).")
