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


class PolicyPageTests(TestCase):
    """Policy pages were entirely missing. They're a buyer-trust gap on a 10-15
    day delivery and a blocker on any payment-processor application."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog")
        call_command("seed_sites")

    def test_all_four_policies_render_on_every_site(self):
        for host in ("smashfatbiolabs.ca", "smashfatbiolabs.com", "smashfat.ca",
                     "smash-fat.ca", "smash-fat.com", "peptidesalberta.ca",
                     "where-do-i-get-peptides.ca", "where-do-i-get-peptides.com"):
            for slug in ("shipping", "returns", "privacy", "terms"):
                r = self.client.get(f"/{slug}/", HTTP_HOST=host)
                self.assertEqual(r.status_code, 200, f"{host}/{slug}")

    def test_policies_state_the_delivery_window_not_an_origin(self):
        html = self.client.get("/shipping/", HTTP_HOST="smashfatbiolabs.ca").content.decode()
        self.assertIn("10–15 days", html)
        for phrase in ("Ships from Canada", "ships from Canada", "same-day",
                       "Same-day", "1–2 business"):
            self.assertNotIn(phrase, html)

    def test_privacy_is_market_aware(self):
        ca = self.client.get("/privacy/", HTTP_HOST="smashfatbiolabs.ca").content.decode()
        us = self.client.get("/privacy/", HTTP_HOST="smashfatbiolabs.com").content.decode()
        self.assertIn("PIPEDA", ca)
        self.assertNotIn("PIPEDA", us)
        self.assertIn("California", us)

    def test_terms_carry_the_research_use_only_gate(self):
        html = self.client.get("/terms/", HTTP_HOST="smashfat.ca").content.decode()
        self.assertIn("research use only", html.lower())
        self.assertIn("21", html)

    def test_policies_linked_in_footer_and_sitemap(self):
        home = self.client.get("/", HTTP_HOST="smashfat.ca").content.decode()
        for slug in ("shipping", "returns", "privacy", "terms"):
            self.assertIn(f'href="/{slug}/"', home)
        sm = self.client.get("/sitemap.xml", HTTP_HOST="smashfat.ca").content.decode()
        for slug in ("shipping", "returns", "privacy", "terms"):
            self.assertIn(f"/{slug}/", sm)


class RegionPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog")
        call_command("seed_sites")

    def test_ca_region_serves_on_ca_site_only(self):
        self.assertEqual(
            self.client.get("/research-peptides/alberta/",
                            HTTP_HOST="peptidesalberta.ca").status_code, 200)
        # A .com serving Canadian provinces would be the doorway pattern these
        # pages are written to avoid.
        self.assertEqual(
            self.client.get("/research-peptides/alberta/",
                            HTTP_HOST="smash-fat.com").status_code, 404)

    def test_us_region_serves_on_us_site_only(self):
        self.assertEqual(
            self.client.get("/research-peptides/california/",
                            HTTP_HOST="smash-fat.com").status_code, 200)
        self.assertEqual(
            self.client.get("/research-peptides/california/",
                            HTTP_HOST="smashfat.ca").status_code, 404)

    def test_every_region_renders_on_a_site_in_its_market(self):
        from apps.stores import regions
        hosts = {"CA": "smashfatbiolabs.ca", "US": "smashfatbiolabs.com"}
        for r in regions.REGIONS:
            resp = self.client.get(f"/research-peptides/{r['slug']}/",
                                   HTTP_HOST=hosts[r["market"]])
            self.assertEqual(resp.status_code, 200, r["slug"])

    def test_region_copy_makes_no_banned_claim(self):
        """These pages are the biggest surface of new copy in the project. If a
        claim slips in anywhere, it slips in here."""
        from apps.stores import regions
        hosts = {"CA": "smashfatbiolabs.ca", "US": "smashfatbiolabs.com"}
        banned = ["Ships from", "ships from", "same-day", "Same-day",
                  "1–2 business", "dosage", "weight loss"]
        for r in regions.REGIONS:
            html = self.client.get(f"/research-peptides/{r['slug']}/",
                                   HTTP_HOST=hosts[r["market"]]).content.decode()
            for phrase in banned:
                self.assertNotIn(phrase, html, f"{phrase!r} on {r['slug']}")
            self.assertIn("Research Use Only", html)

    def test_sitemap_lists_only_this_markets_regions(self):
        ca = self.client.get("/sitemap.xml", HTTP_HOST="smashfatbiolabs.ca").content.decode()
        us = self.client.get("/sitemap.xml", HTTP_HOST="smashfatbiolabs.com").content.decode()
        self.assertIn("/research-peptides/alberta/", ca)
        self.assertNotIn("/research-peptides/alberta/", us)
        self.assertIn("/research-peptides/california/", us)
        self.assertNotIn("/research-peptides/california/", ca)


class SupplierCommandTests(TestCase):
    def test_add_supplier_requires_a_reachable_channel(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            call_command("add_supplier", "Partner")

    def test_add_supplier_rejects_non_e164_whatsapp(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            call_command("add_supplier", "Partner", "--whatsapp", "8613800000000",
                         "--channel", "whatsapp")

    def test_add_supplier_creates_and_sets_default(self):
        from apps.suppliers.models import Supplier
        call_command("add_supplier", "Partner Labs", "--email", "o@x.com", "--default")
        s = Supplier.objects.get(slug="partner-labs")
        self.assertTrue(s.is_default)
        self.assertEqual(Supplier.get_default(), s)
        # Re-running updates rather than duplicating.
        call_command("add_supplier", "Partner Labs", "--email", "new@x.com")
        self.assertEqual(Supplier.objects.count(), 1)
        s.refresh_from_db()
        self.assertEqual(s.email, "new@x.com")
