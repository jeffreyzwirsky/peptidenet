from django.core.management import call_command
from django.test import TestCase


class StorefrontTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog")
        call_command("seed_sites")

    def test_host_routing_selects_theme(self):
        cases = {
            "smashfatbiolabs.ca": "biolabs",
            "smashfatbiolabs.com": "clinical",
            "smashfat.ca": "neon",
            "peptidesalberta.ca": "prairie",
            "where-do-i-get-peptides.com": "directory",
        }
        for host, theme in cases.items():
            r = self.client.get("/", HTTP_HOST=host)
            self.assertEqual(r.status_code, 200, host)
            self.assertContains(r, f"themes/{theme}/theme.css")

    def test_www_alias_resolves(self):
        r = self.client.get("/", HTTP_HOST="www.smashfat.ca")
        self.assertEqual(r.status_code, 200)

    def test_shared_catalogue_on_every_site(self):
        for host in ("smashfatbiolabs.ca", "smash-fat.com"):
            r = self.client.get("/", HTTP_HOST=host)
            self.assertEqual(r.content.decode().count('class="pcard"'), 18, host)

    def test_cart_and_checkout_flow(self):
        self.client.get("/", HTTP_HOST="smashfat.ca")  # set csrf cookie
        add = self.client.post(
            "/cart/add/", {"product_id": 1, "qty": 2},
            content_type="application/json", HTTP_HOST="smashfat.ca",
        )
        self.assertEqual(add.json()["count"], 2)
        out = self.client.post(
            "/checkout/", {"name": "Lab", "email": "a@b.ca"},
            content_type="application/json", HTTP_HOST="smashfat.ca",
        )
        body = out.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["status"], "pending_payment")

    def test_unknown_host_404s_in_prod_mode(self):
        with self.settings(DEBUG=False):
            r = self.client.get("/", HTTP_HOST="not-a-store.example")
            self.assertEqual(r.status_code, 404)


class ProductPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog")
        call_command("seed_sites")
        call_command("apply_specs")

    def test_product_page_renders_with_specs_and_schema(self):
        r = self.client.get("/product/bpc-157/", HTTP_HOST="smashfatbiolabs.ca", secure=True)
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        self.assertIn("Molecular formula", body)
        self.assertIn("C62H98N16O22", body)
        self.assertIn('"@type": "Product"', body)
        self.assertIn("FAQPage", body)
        self.assertIn("BreadcrumbList", body)

    def test_product_page_all_themes(self):
        from apps.stores.models import Site
        for s in Site.objects.all():
            r = self.client.get("/product/retatrutide/", HTTP_HOST=s.domain, secure=True)
            self.assertEqual(r.status_code, 200, s.theme)

    def test_calculator_and_rewards_pages(self):
        for path, needle in (("/calculator/", "data-calc"), ("/rewards/", "SMASH10")):
            r = self.client.get(path, HTTP_HOST="smashfat.ca", secure=True)
            self.assertEqual(r.status_code, 200, path)
            self.assertIn(needle, r.content.decode())


class BulkPricingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog")
        call_command("seed_sites")

    def test_bulk_tiers(self):
        from apps.stores.cart import bulk_pct_for_qty
        self.assertEqual(bulk_pct_for_qty(1), 0)
        self.assertEqual(bulk_pct_for_qty(2), 0)
        self.assertEqual(bulk_pct_for_qty(3), 5)
        self.assertEqual(bulk_pct_for_qty(5), 10)
        self.assertEqual(bulk_pct_for_qty(10), 15)
        self.assertEqual(bulk_pct_for_qty(25), 15)

    def test_bulk_discount_applied_in_cart(self):
        self.client.get("/", HTTP_HOST="smashfat.ca")
        r = self.client.post(
            "/cart/add/", {"product_id": 1, "qty": 5},
            content_type="application/json", HTTP_HOST="smashfat.ca",
        )
        data = r.json()
        # 10% off at qty 5 -> savings > 0 and total < subtotal
        self.assertGreaterEqual(float(data["savings"]), 0.01)
        self.assertLess(float(data["total"]), float(data["subtotal"]))
        self.assertEqual(data["items"][0]["bulk_pct"], 10)
