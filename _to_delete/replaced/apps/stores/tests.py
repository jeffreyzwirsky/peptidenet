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
            "/checkout/",
            {"name": "Lab", "email": "a@b.ca", "shipping_address": "1 Bench Rd",
             "payment_method": "interac", "ruo_ack": "1"},
            content_type="application/json", HTTP_HOST="smashfat.ca",
        )
        body = out.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["status"], "pending_payment")

    def test_checkout_requires_ruo_acknowledgement(self):
        """The research-use-only tick is the record that the buyer was told what
        they were buying. Without it the order must not be created."""
        self.client.get("/", HTTP_HOST="smashfat.ca")
        self.client.post("/cart/add/", {"product_id": 1, "qty": 1},
                         content_type="application/json", HTTP_HOST="smashfat.ca")
        out = self.client.post(
            "/checkout/",
            {"name": "Lab", "email": "a@b.ca", "shipping_address": "1 Bench Rd"},
            content_type="application/json", HTTP_HOST="smashfat.ca",
        )
        self.assertEqual(out.status_code, 400)
        self.assertFalse(out.json()["ok"])

    def test_checkout_requires_shipping_address(self):
        """The manufacturing partner ships direct, so there is no order without
        somewhere to send it."""
        self.client.get("/", HTTP_HOST="smashfat.ca")
        self.client.post("/cart/add/", {"product_id": 1, "qty": 1},
                         content_type="application/json", HTTP_HOST="smashfat.ca")
        out = self.client.post(
            "/checkout/", {"name": "Lab", "email": "a@b.ca", "ruo_ack": "1"},
            content_type="application/json", HTTP_HOST="smashfat.ca",
        )
        self.assertEqual(out.status_code, 400)

    def test_no_shipping_origin_claim_anywhere(self):
        """Goods ship direct from the manufacturing partner. Claiming a
        ships-from country would be a false representation under the Competition
        Act / FTC Act, so no storefront may state or imply one."""
        banned = ["Ships from Canada", "ships from Canada", "Dispatched from",
                  "Same-day", "same-day dispatch", "1–2 business days",
                  "Canadian-owned", "Free express"]
        for host in ("smashfatbiolabs.ca", "smashfatbiolabs.com", "smashfat.ca",
                     "smash-fat.ca", "smash-fat.com", "peptidesalberta.ca",
                     "where-do-i-get-peptides.ca", "where-do-i-get-peptides.com"):
            html = self.client.get("/", HTTP_HOST=host).content.decode()
            for phrase in banned:
                self.assertNotIn(phrase, html, f"{phrase!r} still on {host}")

    def test_shipping_window_is_disclosed_on_every_site(self):
        for host in ("smashfatbiolabs.ca", "smashfatbiolabs.com",
                     "peptidesalberta.ca", "where-do-i-get-peptides.com"):
            html = self.client.get("/", HTTP_HOST=host).content.decode()
            self.assertIn("10–15 days", html, host)

    def test_twin_domains_declare_hreflang(self):
        """The three .ca/.com brand pairs serve one catalogue. Without hreflang
        Google reads them as duplicates and suppresses one of each pair."""
        r = self.client.get("/", HTTP_HOST="smashfatbiolabs.ca")
        html = r.content.decode()
        self.assertIn('hreflang="en-ca"', html)
        self.assertIn('hreflang="en-us"', html)
        self.assertIn("smashfatbiolabs.com", html)
        self.assertIn('hreflang="x-default"', html)

    def test_standalone_site_emits_no_hreflang(self):
        """smashfat.ca has no .com twin — hreflang pointing at nothing is worse
        than none."""
        html = self.client.get("/", HTTP_HOST="smashfat.ca").content.decode()
        self.assertNotIn("hreflang", html)

    def test_us_sites_use_usd(self):
        html = self.client.get("/product/bpc-157/",
                               HTTP_HOST="smashfatbiolabs.com").content.decode()
        self.assertIn('"priceCurrency": "USD"', html)

    def test_no_fabricated_reviews(self):
        """The reviews block used to ship four invented testimonials. Made-up
        endorsements breach Competition Act s.74.01 and the FTC endorsement
        rules."""
        html = self.client.get("/", HTTP_HOST="smashfatbiolabs.ca").content.decode()
        for invented in ("M. Larson", "R. Okafor", "S. Beaumont", "T. Nguyen",
                         "arrived in two days"):
            self.assertNotIn(invented, html)

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


class AgeGateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog")
        call_command("seed_sites")

    def test_gate_shows_without_cookie(self):
        r = self.client.get("/", HTTP_HOST="smashfatbiolabs.ca", secure=True)
        self.assertContains(r, "data-age-gate")

    def test_gate_hidden_with_cookie(self):
        self.client.cookies["age_ok"] = "1"
        for path in ("/", "/product/bpc-157/", "/calculator/"):
            r = self.client.get(path, HTTP_HOST="smashfatbiolabs.ca", secure=True)
            self.assertNotContains(r, "data-age-gate", msg_prefix=path)
