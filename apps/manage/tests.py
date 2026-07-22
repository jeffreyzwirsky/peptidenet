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

    def test_admin_requires_login(self):
        r = self.client.get("/manage/")
        self.assertEqual(r.status_code, 302)  # redirected to the console login
        self.assertIn("/manage/login", r.url)

    def test_portal_requires_login(self):
        r = self.client.get("/portal/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/portal/login", r.url)

    def test_dashboard_loads_for_owner(self):
        self.client.force_login(self.staff)  # 'boss' is a superuser
        r = self.client.get("/manage/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Overview")

    def test_owner_can_see_both_sides(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get("/manage/").status_code, 200)
        self.assertEqual(self.client.get("/portal/").status_code, 200)

    def test_walled_staff_can_use_portal_not_admin(self):
        from django.contrib.auth.models import Group

        from apps.manage.access import PORTAL_GROUP
        g, _ = Group.objects.get_or_create(name=PORTAL_GROUP)
        clerk = get_user_model().objects.create_user(
            "clerk", password="x", is_staff=False, is_superuser=False
        )
        clerk.groups.add(g)
        self.client.force_login(clerk)
        # Portal: allowed.
        self.assertEqual(self.client.get("/portal/").status_code, 200)
        self.assertContains(self.client.get("/portal/messages/"), "")
        # Admin side: walled out (redirected to the admin login).
        r = self.client.get("/manage/")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/manage/login", r.url)

    def test_team_page_is_owner_only(self):
        from django.contrib.auth.models import Group

        from apps.manage.access import PORTAL_GROUP
        g, _ = Group.objects.get_or_create(name=PORTAL_GROUP)
        clerk = get_user_model().objects.create_user("clerk2", password="x", is_staff=False)
        clerk.groups.add(g)
        # Owner sees Team.
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get("/manage/team/").status_code, 200)
        # Walled staff can't (redirected off it).
        self.client.force_login(clerk)
        self.assertEqual(self.client.get("/portal/team/").status_code, 302)

    def test_owner_can_invite_walled_staff(self):
        self.client.force_login(self.staff)
        self.client.post("/manage/team/", {
            "action": "invite", "username": "newclerk", "email": "n@ex.com",
        })
        u = get_user_model().objects.get(username="newclerk")
        self.assertFalse(u.is_staff)
        self.assertFalse(u.is_superuser)
        self.assertFalse(u.has_usable_password())
        from apps.manage.access import PORTAL_GROUP
        self.assertTrue(u.groups.filter(name=PORTAL_GROUP).exists())

    def test_compliance_page_loads(self):
        self.client.force_login(self.staff)
        r = self.client.get("/manage/compliance/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Consent audit")

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

    def test_numbers_page_loads_and_saves_settings(self):
        from apps.comms.models import PhoneNumber
        self.client.force_login(self.staff)
        n = PhoneNumber.objects.create(e164="+13252465227", label="net", sms_enabled=True)
        r = self.client.get("/manage/numbers/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "AI intake")
        self.client.post("/manage/numbers/", {
            "number_id": n.pk, "label": "Network line", "greeting": "New greeting.",
            "ai_intake": "1", "voice_enabled": "1", "is_active": "1",  # sms unchecked
        })
        n.refresh_from_db()
        self.assertTrue(n.ai_intake)
        self.assertFalse(n.sms_enabled)          # unchecked box -> turned off
        self.assertEqual(n.greeting, "New greeting.")
