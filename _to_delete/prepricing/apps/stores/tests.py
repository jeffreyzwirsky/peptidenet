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
        # 10% off at 5 packs -> savings > 0 and total < subtotal
        self.assertGreaterEqual(float(data["savings"]), 0.01)
        self.assertLess(float(data["total"]), float(data["subtotal"]))
        self.assertEqual(data["items"][0]["bulk_pct"], 10)

    def test_minimum_order_is_one_pack_not_one_vial(self):
        """A single 'add to cart' must buy a whole pack.

        The tiers count packs, so this also pins the thing that made the
        minimum worth introducing: one pack earns NO bulk discount. When the
        tiers counted vials, this same cart cleared the top tier on its first
        click and handed back 15% of the margin.
        """
        self.client.get("/", HTTP_HOST="smashfat.ca")
        r = self.client.post(
            "/cart/add/", {"product_id": 1},
            content_type="application/json", HTTP_HOST="smashfat.ca",
        )
        data = r.json()
        item = data["items"][0]
        self.assertEqual(item["qty"], 1)
        self.assertEqual(item["pack_size"], 10)
        self.assertEqual(item["vials"], 10)
        self.assertEqual(data["vials"], 10)
        self.assertEqual(item["bulk_pct"], 0)
        self.assertEqual(float(data["savings"]), 0.0)

    def test_pack_price_is_ten_times_the_vial_price(self):
        from apps.catalog.models import Product
        p = Product.objects.get(id=1)
        self.assertEqual(p.pack_price, p.price * 10)
        self.assertEqual(p.pack_list_price, p.list_price * 10)

    def test_supplies_are_not_forced_into_packs(self):
        """Bacteriostatic water is a bottle, not a vial of compound."""
        from apps.catalog.models import Product
        water = Product.objects.filter(category__name__iexact="Supplies").first()
        self.assertIsNotNone(water)
        self.assertEqual(water.vials_per_pack, 1)
        self.assertFalse(water.sells_in_packs)
        self.assertEqual(water.pack_price, water.price)

    def test_sub_pack_quantity_cannot_be_forced_by_a_crafted_request(self):
        """The server does not trust the client to have enforced the minimum."""
        self.client.get("/", HTTP_HOST="smashfat.ca")
        self.client.post("/cart/add/", {"product_id": 1},
                         content_type="application/json", HTTP_HOST="smashfat.ca")
        r = self.client.post(
            "/cart/update/", {"product_id": 1, "qty": 0.4},
            content_type="application/json", HTTP_HOST="smashfat.ca",
        )
        item = r.json()["items"][0]
        self.assertGreaterEqual(item["qty"], 1)
        self.assertGreaterEqual(item["vials"], 10)


class PackOrderMathTests(TestCase):
    """Money and fulfilment arithmetic across the pack boundary.

    Both failures guarded here are silent: the order still completes, the page
    still renders, and the damage only shows up in a margin report or a short
    shipment. They are the reason pack_size is snapshotted on OrderItem.
    """

    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog")
        call_command("seed_sites")

    def _order(self, qty=2):
        from apps.orders.models import Order
        from apps.stores.models import Site
        site = Site.objects.get(domain="smashfat.ca")
        self.client.get("/", HTTP_HOST="smashfat.ca")
        self.client.post("/cart/add/", {"product_id": 1, "qty": qty},
                         content_type="application/json", HTTP_HOST="smashfat.ca")
        from apps.stores.cart import Cart

        class _R:
            session = self.client.session
        cart = Cart(_R())
        items = cart.items()
        return Order.create_from_cart(
            site=site, items=items, total=cart.total(),
            email="lab@example.com", name="Lab",
            payment_method="interac", shipping_address="1 Test St",
        )

    def test_cogs_counts_vials_not_packs(self):
        order = self._order(qty=2)
        item = order.items.first()
        self.assertEqual(item.pack_size, 10)
        self.assertEqual(item.vials, 20)
        # unit_cost is per PACK, so line_cost covers all 20 vials. The bug this
        # replaces multiplied a per-vial cost by a pack count and reported a
        # tenth of the true COGS — i.e. ~95% margins on every order.
        self.assertEqual(item.line_cost, item.unit_cost_per_vial * 20)
        self.assertEqual(order.cost_total, item.line_cost)

    def test_invoice_reconciles(self):
        order = self._order(qty=3)
        item = order.items.first()
        self.assertEqual(item.unit_price * item.qty, item.line_total)

    def test_purchase_order_is_denominated_in_vials(self):
        """The partner picks per vial and has never heard of our pack."""
        from apps.suppliers.models import PurchaseOrder, Supplier
        Supplier.objects.create(
            name="Partner Labs", slug="partner-labs",
            email="orders@example.com", preferred_channel="email",
            is_default=True, is_active=True,
        )
        order = self._order(qty=2)
        order.status = "paid"
        order.save(update_fields=["status"])
        po = PurchaseOrder.build_for(order)
        po_item = po.items.first()
        self.assertEqual(po_item.qty, 20, "PO must order 20 vials, not 2 packs")

        from apps.suppliers import dispatch
        text = dispatch.render_po_text(po)
        self.assertIn("20 vials", text)
        # Customer pricing still never reaches the manufacturing partner.
        self.assertNotIn("$", text)


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
