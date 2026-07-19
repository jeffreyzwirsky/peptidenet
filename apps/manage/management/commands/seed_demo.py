"""Optional: create sample orders + leads so the control panel has data to show.
Safe to run in dev only. `python manage.py seed_demo`"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.catalog.models import Product
from apps.leads.models import Lead
from apps.orders.models import Order
from apps.stores.models import Site

ORDERS = [
    ("smashfatbiolabs.ca", "m.larson@lab.ca", [("bpc-157", 2), ("tb-500", 1)], "paid"),
    ("smashfat.ca", "r.okafor@research.ca", [("retatrutide", 3)], "fulfilled"),
    ("peptidesalberta.ca", "s.beaumont@ualberta.ca", [("ghk-cu", 2), ("nad", 1)], "pending_payment"),
    ("smashfatbiolabs.com", "t.nguyen@clinic.com", [("tesamorelin", 1), ("ipamorelin", 2)], "paid"),
    ("where-do-i-get-peptides.ca", "j.whitfield@lab.ca", [("semax", 1), ("selank", 1)], "pending_payment"),
    ("smash-fat.com", "c.tremblay@inst.ca", [("mots-c", 2)], "paid"),
    ("smash-fat.ca", "a.hassan@bio.ca", [("epithalon", 1), ("kpv", 2)], "fulfilled"),
    ("smashfat.ca", "l.oconnor@lab.ca", [("melanotan-2", 1)], "cancelled"),
    ("peptidesalberta.ca", "d.chastain@clinic.ca", [("ss-31", 1), ("bacteriostatic-water", 2)], "paid"),
]
LEADS = [
    ("smashfatbiolabs.ca", "feedback", "P. Sandhu", "priya@lab.ca", 5, "COA on every batch — exactly what I needed."),
    ("where-do-i-get-peptides.com", "request", "K. Berg", "kberg@bio.ca", None, "Do you carry AOD-9604? Would order if so."),
    ("smashfat.ca", "contact", "N. Reid", "nreid@research.ca", None, "Reconstitution guidance for the metabolic line?"),
]


class Command(BaseCommand):
    help = "Seed sample orders + leads for the control-panel demo."

    def handle(self, *args, **opts):
        made = 0
        for domain, email, lines, status in ORDERS:
            site = Site.objects.filter(domain=domain).first()
            if not site:
                continue
            items, total = [], Decimal("0")
            for slug, qty in lines:
                p = Product.objects.filter(slug=slug).first()
                if not p:
                    continue
                lt = p.price * qty
                total += lt
                items.append({"id": p.id, "name": p.name, "price": p.price,
                              "qty": qty, "line_total": lt})
            if not items:
                continue
            order = Order.create_from_cart(site, items, total, email=email)
            order.status = status
            order.save(update_fields=["status"])
            made += 1
        for domain, kind, name, email, rating, msg in LEADS:
            site = Site.objects.filter(domain=domain).first()
            if site:
                Lead.objects.create(site=site, kind=kind, name=name, email=email,
                                    rating=rating, message=msg)
        self.stdout.write(self.style.SUCCESS(f"Demo data: {made} orders, {len(LEADS)} leads."))
