from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.catalog.models import Product
from apps.orders.models import Order


class ControlPanelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog")
        call_command("seed_sites")
        cls.staff = get_user_model().objects.create_user(
            "boss", password="x", is_staff=True, is_superuser=True
        )

    def test_requires_staff(self):
        r = self.client.get("/manage/")
        self.assertEqual(r.status_code, 302)  # redirected to admin login
        self.assertIn("/admin/login", r.url)

    def test_dashboard_loads_for_staff(self):
        self.client.force_login(self.staff)
        r = self.client.get("/manage/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Overview")

    def test_checkout_decrements_shared_inventory(self):
        p = Product.objects.get(slug="bpc-157")
        start = p.stock_qty
        self.client.get("/", HTTP_HOST="smashfat.ca")
        self.client.post("/cart/add/", {"product_id": p.id, "qty": 3},
                         content_type="application/json", HTTP_HOST="smashfat.ca")
        self.client.post("/checkout/", {"name": "L", "email": "a@b.ca"},
                         content_type="application/json", HTTP_HOST="smashfat.ca")
        p.refresh_from_db()
        self.assertEqual(p.stock_qty, start - 3)

    def test_inventory_edit_updates_pool(self):
        self.client.force_login(self.staff)
        p = Product.objects.get(slug="glow")
        self.client.post("/manage/inventory/", {
            "product_id": p.id, "action": "save", "price": "130",
            "stock_qty": "7", "low_stock_threshold": "5", "is_active": "on",
        })
        p.refresh_from_db()
        self.assertEqual(p.stock_qty, 7)
        self.assertEqual(str(p.price), "130.00")

    def test_restock_adds_units(self):
        self.client.force_login(self.staff)
        p = Product.objects.get(slug="klow")
        start = p.stock_qty
        self.client.post("/manage/inventory/", {
            "product_id": p.id, "action": "restock", "amount": "50",
        })
        p.refresh_from_db()
        self.assertEqual(p.stock_qty, start + 50)

    def test_order_captures_cost_and_profit(self):
        p = Product.objects.get(slug="tesamorelin")  # price 90, cost ~31.50
        self.client.get("/", HTTP_HOST="smashfat.ca")
        self.client.post("/cart/add/", {"product_id": p.id, "qty": 2},
                         content_type="application/json", HTTP_HOST="smashfat.ca")
        self.client.post("/checkout/", {"name": "L", "email": "a@b.ca"},
                         content_type="application/json", HTTP_HOST="smashfat.ca")
        o = Order.objects.latest("created_at")
        self.assertEqual(o.cost_total, p.unit_cost * 2)
        self.assertEqual(o.profit, o.total - o.cost_total)
        self.assertGreater(o.profit, 0)

    def test_inventory_edit_saves_unit_cost(self):
        self.client.force_login(self.staff)
        p = Product.objects.get(slug="glow")
        self.client.post("/manage/inventory/", {
            "product_id": p.id, "action": "save", "price": "120",
            "unit_cost": "44.00", "stock_qty": "10", "low_stock_threshold": "5",
            "is_active": "on",
        })
        p.refresh_from_db()
        self.assertEqual(str(p.unit_cost), "44.00")
        self.assertEqual(str(p.margin), "76.00")

    def test_order_status_update(self):
        self.client.force_login(self.staff)
        site = __import__("apps.stores.models", fromlist=["Site"]).Site.objects.first()
        o = Order.objects.create(number="SFB-1", site=site, total=10)
        self.client.post(f"/manage/orders/{o.pk}/", {"status": "fulfilled"})
        o.refresh_from_db()
        self.assertEqual(o.status, "fulfilled")
