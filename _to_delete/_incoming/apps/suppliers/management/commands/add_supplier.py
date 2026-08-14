"""
Register the manufacturing partner in one command.

`/manage/purchasing/` cannot raise a purchase order until a Supplier row exists,
so this is the single thing standing between the dropship flow and working.
Everything except the name is optional — register what you know now and fill the
rest in later from Django admin.
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from apps.suppliers.models import Supplier


class Command(BaseCommand):
    help = (
        "Add or update the manufacturing partner purchase orders are sent to. "
        "Example: manage.py add_supplier \"Partner Labs\" --email orders@x.com "
        "--whatsapp +8613800000000 --channel whatsapp --default"
    )

    def add_arguments(self, parser):
        parser.add_argument("name", help="Supplier name, e.g. \"Partner Labs\"")
        parser.add_argument("--slug", default="", help="Defaults to a slug of the name.")
        parser.add_argument("--contact", default="", help="Contact person.")
        parser.add_argument("--email", default="", help="Where purchase orders are emailed.")
        parser.add_argument("--whatsapp", default="",
                            help="E.164, e.g. +8613800000000. Builds the wa.me link.")
        parser.add_argument("--channel", default="email", choices=["email", "whatsapp"],
                            help="Default channel for purchase orders.")
        parser.add_argument("--currency", default="USD", help="Currency they invoice in.")
        parser.add_argument("--lead-min", type=int, default=10,
                            help="Days from order placed to delivered to our customer.")
        parser.add_argument("--lead-max", type=int, default=15)
        parser.add_argument("--moq", default="0",
                            help="Minimum order value in their currency. 0 = none.")
        parser.add_argument("--terms", default="", help="Payment terms, free text.")
        parser.add_argument("--notes", default="")
        parser.add_argument("--default", action="store_true",
                            help="Use for products with no supplier of their own.")

    def handle(self, *args, **o):
        if not o["email"] and not o["whatsapp"]:
            raise CommandError(
                "Give at least one of --email or --whatsapp — a purchase order "
                "has to reach them somehow."
            )
        if o["channel"] == "email" and not o["email"]:
            raise CommandError("--channel email needs --email.")
        if o["channel"] == "whatsapp" and not o["whatsapp"]:
            raise CommandError("--channel whatsapp needs --whatsapp.")
        if o["whatsapp"] and not o["whatsapp"].startswith("+"):
            raise CommandError(
                "--whatsapp must be E.164 and start with '+', e.g. +8613800000000."
            )
        if o["lead_min"] > o["lead_max"]:
            raise CommandError("--lead-min cannot be greater than --lead-max.")

        slug = o["slug"] or slugify(o["name"])
        supplier, created = Supplier.objects.update_or_create(
            slug=slug,
            defaults={
                "name": o["name"],
                "contact_name": o["contact"],
                "email": o["email"],
                "whatsapp": o["whatsapp"],
                "preferred_channel": o["channel"],
                "currency": o["currency"],
                "lead_time_min_days": o["lead_min"],
                "lead_time_max_days": o["lead_max"],
                "minimum_order_value": o["moq"],
                "payment_terms": o["terms"],
                "notes": o["notes"],
                "is_active": True,
            },
        )
        if o["default"]:
            Supplier.objects.exclude(pk=supplier.pk).update(is_default=False)
            supplier.is_default = True
            supplier.save(update_fields=["is_default"])

        verb = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(
            f"{verb} supplier {supplier.name} ({supplier.slug}) — "
            f"{supplier.get_preferred_channel_display()}, "
            f"lead time {supplier.lead_time_window}"
            f"{', default' if supplier.is_default else ''}."
        ))
        self.stdout.write(
            "Purchase orders can now be raised at /manage/purchasing/.\n"
            "Reminder: per-vial costs are still placeholders. Enter the real "
            "supplier cost per product in the control panel before trusting any "
            "margin figure."
        )
