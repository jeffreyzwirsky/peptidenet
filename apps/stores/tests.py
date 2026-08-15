import re

from django.core.management import call_command
from django.db import models
from django.test import TestCase

from apps.catalog.models import Product
from apps.stores import seo
from apps.stores.models import Site


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
        # Changed 2026-08-12: aliases now 301 to the canonical domain instead
        # of serving a duplicate of the whole site under a second hostname.
        r = self.client.get("/", HTTP_HOST="www.smashfat.ca")
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r["Location"], "http://smashfat.ca/")

    def test_shared_catalogue_on_every_site(self):
        """One catalogue, rendered identically everywhere.

        Counted against the database rather than a literal, so adding products
        doesn't fail this test for the wrong reason — what's being asserted is
        that no site shows a different set, not that there are exactly N.
        """
        # Cards, not SKUs — sibling strengths collapse into one listing.
        expected = Product.objects.filter(is_active=True).filter(
            models.Q(family="") | models.Q(is_family_default=True)).count()
        self.assertGreater(expected, 0)
        for host in ("smashfatbiolabs.ca", "smash-fat.com"):
            r = self.client.get("/", HTTP_HOST=host)
            self.assertEqual(r.content.decode().count('class="pcard"'), expected, host)

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
        # California is owned by smashfatbiolabs.com; a sibling .com must not
        # serve it either, or the page exists at two US domains.
        self.assertEqual(
            self.client.get("/research-peptides/california/",
                            HTTP_HOST="smashfatbiolabs.com").status_code, 200)
        self.assertEqual(
            self.client.get("/research-peptides/california/",
                            HTTP_HOST="smash-fat.com").status_code, 404)
        self.assertEqual(
            self.client.get("/research-peptides/california/",
                            HTTP_HOST="smashfat.ca").status_code, 404)

    def test_every_region_renders_on_its_owner(self):
        from apps.stores import regions
        for r in regions.REGIONS:
            resp = self.client.get(f"/research-peptides/{r['slug']}/",
                                   HTTP_HOST=r["owner"])
            self.assertEqual(resp.status_code, 200, r["slug"])

    def test_each_region_lives_on_exactly_one_domain(self):
        """The point of the whole ownership layer. Before it, every .ca site
        served all 13 Canadian pages — the same Alberta page at five domains,
        which is cross-domain duplicate content no amount of distinct writing
        fixes."""
        from apps.stores import regions
        from apps.stores.models import Site
        domains = list(Site.objects.values_list("domain", flat=True))
        for r in regions.REGIONS:
            serving = [d for d in domains
                       if self.client.get(f"/research-peptides/{r['slug']}/",
                                          HTTP_HOST=d).status_code == 200]
            self.assertEqual(serving, [r["owner"]],
                             f"{r['slug']} served by {serving}, expected only {r['owner']}")

    def test_region_ownership_is_evenly_spread(self):
        from collections import Counter

        from apps.stores import regions
        ca = Counter(r["owner"] for r in regions.REGIONS if r["market"] == "CA"
                     and not r.get("parent"))
        us = Counter(r["owner"] for r in regions.REGIONS if r["market"] == "US")
        # Alberta's owner holds one province; the other four .ca sites hold three each.
        self.assertEqual(sorted(ca.values()), [1, 3, 3, 3, 3])
        self.assertEqual(sorted(us.values()), [4, 4, 4])

    def test_sibling_links_never_point_at_a_404(self):
        """Siblings used to list the whole market, so every region page linked
        to twelve pages that 404 on that domain."""
        from apps.stores import regions
        r = regions.get("alberta")
        html = self.client.get("/research-peptides/alberta/",
                               HTTP_HOST=r["owner"]).content.decode()
        import re as _re
        for slug in set(_re.findall(r'/research-peptides/([a-z\-]+)/', html)):
            self.assertEqual(
                self.client.get(f"/research-peptides/{slug}/",
                                HTTP_HOST=r["owner"]).status_code, 200,
                f"alberta page links to /research-peptides/{slug}/ which 404s on {r['owner']}")

    def test_region_copy_makes_no_banned_claim(self):
        """These pages are the biggest surface of new copy in the project. If a
        claim slips in anywhere, it slips in here."""
        from apps.stores import regions
        banned = ["Ships from", "ships from", "same-day", "Same-day",
                  "1–2 business", "dosage", "weight loss"]
        for r in regions.REGIONS:
            html = self.client.get(f"/research-peptides/{r['slug']}/",
                                   HTTP_HOST=r["owner"]).content.decode()
            for phrase in banned:
                self.assertNotIn(phrase, html, f"{phrase!r} on {r['slug']}")
            self.assertIn("Research Use Only", html)

    def test_sitemap_lists_only_the_regions_this_site_owns(self):
        ab = self.client.get("/sitemap.xml", HTTP_HOST="peptidesalberta.ca").content.decode()
        bio = self.client.get("/sitemap.xml", HTTP_HOST="smashfatbiolabs.ca").content.decode()
        us = self.client.get("/sitemap.xml", HTTP_HOST="smashfatbiolabs.com").content.decode()
        self.assertIn("/research-peptides/alberta/", ab)
        # Another .ca site must not advertise a page it does not serve.
        self.assertNotIn("/research-peptides/alberta/", bio)
        self.assertIn("/research-peptides/british-columbia/", bio)
        self.assertNotIn("/research-peptides/alberta/", us)
        self.assertIn("/research-peptides/california/", us)


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


class SizeFamilyTests(TestCase):
    """One compound, several strengths, one card.

    A size stays its own Product — the cart, order line, purchase order and
    repricer all key on Product, and all four handle money. Grouping is a
    presentation concern layered on top, and these tests pin the seam.
    """

    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog")
        call_command("seed_sites")

    def test_existing_urls_did_not_move(self):
        """The original strength keeps the slug that is already indexed.

        Renaming it to bpc-157-10mg would 404 every existing link and lose the
        page's ranking — the one thing a catalogue restructure must not do.
        """
        for slug in ("bpc-157", "tb-500", "ghk-cu", "mots-c", "retatrutide",
                     "tesamorelin", "epithalon", "nad", "selank", "semax"):
            r = self.client.get(f"/product/{slug}/", HTTP_HOST="smashfatbiolabs.ca")
            self.assertEqual(r.status_code, 200, slug)

    def test_sibling_strengths_are_their_own_pages(self):
        r = self.client.get("/product/bpc-157-5mg/", HTTP_HOST="smashfatbiolabs.ca")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "BPC-157")

    def test_grid_shows_one_card_per_compound(self):
        """87 SKUs, 48 cards. The grid should read as deep, not padded."""
        skus = Product.objects.filter(is_active=True).count()
        cards = Product.objects.filter(is_active=True).filter(
            models.Q(family="") | models.Q(is_family_default=True)).count()
        self.assertGreater(skus, cards)
        html = self.client.get("/", HTTP_HOST="smashfatbiolabs.ca").content.decode()
        self.assertEqual(html.count('class="pcard"'), cards)

    def test_every_family_has_exactly_one_default(self):
        """Two defaults would double-list a compound; none would hide it."""
        from django.db.models import Count
        fams = (Product.objects.filter(is_active=True).exclude(family="")
                .values("family")
                .annotate(defaults=Count("id", filter=models.Q(is_family_default=True))))
        self.assertTrue(fams)
        for f in fams:
            self.assertEqual(f["defaults"], 1, f["family"])

    def test_each_strength_carries_its_own_price_and_supplier_code(self):
        small = Product.objects.get(slug="bpc-157-5mg")
        big = Product.objects.get(slug="bpc-157")
        self.assertNotEqual(small.price, big.price)
        self.assertNotEqual(small.supplier_cat_no, big.supplier_cat_no)
        self.assertLess(small.price, big.price)

    def test_size_selector_lists_every_strength_as_a_real_link(self):
        """No-JS and crawlers both need somewhere real to go."""
        html = self.client.get("/product/bpc-157/",
                               HTTP_HOST="smashfatbiolabs.ca").content.decode()
        self.assertIn('data-size-picker', html)
        self.assertIn('href="/product/bpc-157-5mg/"', html)
        self.assertIn('aria-current="true"', html)

    def test_multi_size_card_does_not_add_to_cart(self):
        """Adding from a card showing three sizes would silently pick one."""
        html = self.client.get("/", HTTP_HOST="smashfatbiolabs.ca").content.decode()
        self.assertIn("Choose size", html)

    def test_a_standalone_product_is_unaffected(self):
        klow = Product.objects.get(slug="klow")
        self.assertEqual(klow.family, "")
        self.assertFalse(klow.has_sizes)
        self.assertEqual(klow.siblings, [])

    def test_buying_a_sibling_strength_charges_that_strength(self):
        """The seam that matters: the cart must price what was selected."""
        small = Product.objects.get(slug="bpc-157-5mg")
        self.client.get("/", HTTP_HOST="smashfat.ca")
        r = self.client.post("/cart/add/", {"product_id": small.id},
                             content_type="application/json", HTTP_HOST="smashfat.ca")
        item = r.json()["items"][0]
        self.assertEqual(item["id"], small.id)
        self.assertEqual(item["pack_price"], str(small.pack_price))


class NoUnevidencedClaimsTests(TestCase):
    """No storefront may claim testing, a COA, or a purity figure.

    We hold no analytical documentation for anything in the catalogue. Under
    Competition Act s.74.01(1)(b) — and the FTC Act on the .com sites — a
    performance claim must rest on adequate and proper testing made BEFORE the
    claim, and the burden of proving it sits with the advertiser. These claims
    were live on all eight storefronts, in the hero, the trust badges, the
    ticker, the FAQ, the policy pages, the JSON feeds and the AI assistant.
    """

    HOSTS = ("smashfatbiolabs.ca", "smashfatbiolabs.com", "smashfat.ca",
             "smash-fat.ca", "smash-fat.com", "peptidesalberta.ca",
             "where-do-i-get-peptides.ca", "where-do-i-get-peptides.com")

    # Affirmative claims. Phrased so a negation ("we hold no certificate of
    # analysis") does not match — it is the assertion that is banned, not the word.
    BANNED = [
        "COA on every", "COA available on request", "certificate of analysis is available",
        "batch-specific certificate", "batch-matched certificate", "COA-backed",
        "third-party tested", "third-party HPLC", "independently tested",
        "HPLC + MS", "HPLC/MS tested", "mass-spec verified", "HPLC-verified",
        "≥99% purity", "≥99% pure", "release purity", "High-purity", "high-purity",
        "Reference-grade", "reference-grade", "Analytically certified",
        "issued by Janoshik", "Janoshik",
    ]

    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog")
        call_command("seed_sites")

    def test_no_claims_on_any_homepage(self):
        for host in self.HOSTS:
            r = self.client.get("/", HTTP_HOST=host)
            self.assertEqual(r.status_code, 200, host)
            html = r.content.decode()
            for phrase in self.BANNED:
                self.assertNotIn(phrase, html, f"{phrase!r} still on {host}")

    def test_no_claims_on_product_pages(self):
        for host in self.HOSTS:
            for slug in ("bpc-157", "tb-500", "ghk-cu"):
                r = self.client.get(f"/product/{slug}/", HTTP_HOST=host)
                self.assertEqual(r.status_code, 200, f"{host}/product/{slug}/")
                html = r.content.decode()
                for phrase in self.BANNED:
                    self.assertNotIn(phrase, html, f"{phrase!r} on {host}/product/{slug}/")

    def test_no_claims_in_policies_or_regions(self):
        """Assert the page exists BEFORE asserting what isn't on it.

        The first version of this test requested /policy/shipping/, which does
        not exist — the real path is /shipping/. A 404 body contains none of the
        banned phrases, so the test passed without ever loading a policy page.
        A content assertion against an unchecked status code is not a test.
        """
        paths = ["/shipping/", "/returns/", "/privacy/", "/terms/",
                 "/research-peptides/alberta/"]
        for path in paths:
            r = self.client.get(path, HTTP_HOST="peptidesalberta.ca")
            self.assertEqual(r.status_code, 200, f"{path} did not resolve")
            html = r.content.decode()
            self.assertGreater(len(html), 2000, f"{path} looks like an error page")
            for phrase in self.BANNED:
                self.assertNotIn(phrase, html, f"{phrase!r} on {path}")

    def test_no_claims_in_machine_readable_feeds(self):
        """llms.txt and the COA endpoint are read by agents, not people — an
        unevidenced claim there is repeated verbatim by whatever consumes it."""
        for path in ("/llms.txt", "/llms-full.txt"):
            r = self.client.get(path, HTTP_HOST="smashfatbiolabs.ca")
            self.assertEqual(r.status_code, 200, path)
            body = r.content.decode()
            self.assertGreater(len(body), 500, f"{path} looks empty")
            for phrase in self.BANNED:
                self.assertNotIn(phrase, body, f"{phrase!r} in {path}")

    def test_no_purity_figure_is_rendered_anywhere(self):
        """The purity field is blank by default; nothing should print one."""
        from apps.catalog.models import Product
        self.assertFalse(Product.objects.exclude(purity="").exists())
        html = self.client.get("/product/bpc-157/", HTTP_HOST="smashfatbiolabs.ca").content.decode()
        self.assertNotIn("99%", html)

    def test_no_template_comment_leaked_onto_a_page(self):
        """Django's {# #} is single-line only.

        The rewrite added explanatory notes at every removed claim. A multi-line
        {# #} is not a comment — it renders — which would print the exact claims
        being removed, quoted, onto the live page. Fifteen were found in one
        theme during this change.
        """
        for host in self.HOSTS:
            html = self.client.get("/", HTTP_HOST=host).content.decode()
            for marker in ("{#", "#}", "{% comment", "endcomment"):
                self.assertNotIn(marker, html, f"{marker!r} leaked on {host}")


class DiscoveryFileTests(TestCase):
    """Per-site discovery/SEO files: every domain must serve its OWN robots,
    sitemap and security.txt — unique per site, not one network-wide copy."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog")
        call_command("seed_sites")

    def test_security_txt_serves_per_site(self):
        for host in ("smashfatbiolabs.ca", "smashfat.ca"):
            for path in ("/.well-known/security.txt", "/security.txt"):
                r = self.client.get(path, HTTP_HOST=host)
                self.assertEqual(r.status_code, 200, f"{host}{path}")
                body = r.content.decode()
                self.assertIn("Contact: mailto:", body)
                self.assertIn("Expires: ", body)
                self.assertIn(f"//{host}/.well-known/security.txt",
                              body)  # canonical is per-host

    def test_robots_is_unique_per_site(self):
        a = self.client.get("/robots.txt", HTTP_HOST="smashfatbiolabs.ca").content.decode()
        b = self.client.get("/robots.txt", HTTP_HOST="smashfat.ca").content.decode()
        self.assertNotEqual(a, b)
        self.assertIn("smashfatbiolabs.ca", a)
        self.assertIn("/blog/feed/", a)
        self.assertIn("security.txt", a)

    def test_sitemap_carries_lastmod_for_posts(self):
        from django.utils import timezone

        from apps.blog.models import BlogPost
        from apps.stores.models import Site
        site = Site.objects.get(domain="smashfat.ca")
        BlogPost.objects.create(site=site, title="SM post", slug="sm-post",
                                body="research use only", status="published",
                                published_at=timezone.now())
        sm = self.client.get("/sitemap.xml", HTTP_HOST="smashfat.ca").content.decode()
        self.assertIn("/blog/sm-post/", sm)
        self.assertIn("<lastmod>", sm)

    def test_rss_autodiscovery_link_on_every_theme(self):
        for host in ("smashfatbiolabs.ca", "smashfat.ca", "peptidesalberta.ca"):
            html = self.client.get("/", HTTP_HOST=host).content.decode()
            self.assertIn('type="application/rss+xml"', html, host)


class SeoHygieneTests(TestCase):
    """On-page SEO invariants Jeff asked for (2026-08-12): every page has
    exactly one h1, heading levels never skip, canonicals pin to the canonical
    domain, aliases 301, twinned sites emit a full hreflang block."""

    PATHS = ["/", "/product/bpc-157/", "/calculator/", "/rewards/", "/blog/",
             "/shipping/", "/privacy/"]

    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog")
        call_command("seed_sites")
        from django.utils import timezone

        from apps.blog.models import BlogPost
        from apps.stores.models import Site
        for s in Site.objects.filter(is_active=True):
            BlogPost.objects.create(
                site=s, slug="seo-post", title="SEO Post",
                body="# SEO Post\n\n## A section\nresearch use only",
                status="published", published_at=timezone.now(),
                excerpt="x", meta_description="x")

    @staticmethod
    def _headings(html):
        import re
        return [int(m.group(1)) for m in re.finditer(r"<h([1-6])[\s>]", html)]

    def test_one_h1_and_no_heading_skips_everywhere(self):
        from apps.stores.models import Site
        for s in Site.objects.filter(is_active=True):
            for path in self.PATHS + ["/blog/seo-post/"]:
                html = self.client.get(path, HTTP_HOST=s.domain).content.decode()
                hs = self._headings(html)
                self.assertEqual(hs.count(1), 1, f"{s.domain}{path}: h1 x{hs.count(1)}")
                prev = 0
                for lvl in hs:
                    self.assertLessEqual(
                        lvl, prev + 1 if prev else 6,
                        f"{s.domain}{path}: heading skip h{prev}->h{lvl}")
                    prev = lvl

    def test_canonical_pins_to_canonical_domain_even_on_alias(self):
        html = self.client.get("/", HTTP_HOST="smashfatbiolabs.ca").content.decode()
        self.assertIn('rel="canonical" href="http://smashfatbiolabs.ca/"', html)

    def test_alias_host_redirects_301_to_canonical_domain(self):
        r = self.client.get("/calculator/?x=1", HTTP_HOST="www.smashfatbiolabs.ca")
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r["Location"], "http://smashfatbiolabs.ca/calculator/?x=1")

    def test_hreflang_block_on_twinned_sites(self):
        html = self.client.get("/", HTTP_HOST="smashfatbiolabs.ca").content.decode()
        self.assertIn('hreflang="en-ca" href="http://smashfatbiolabs.ca/"', html)
        self.assertIn('hreflang="en-us" href="http://smashfatbiolabs.com/"', html)
        self.assertIn('hreflang="x-default"', html)
        # standalone site emits none (hreflang pointing at nothing is worse)
        alone = self.client.get("/", HTTP_HOST="peptidesalberta.ca").content.decode()
        self.assertNotIn("hreflang", alone)

    def test_blog_detail_title_not_duplicated_from_markdown(self):
        html = self.client.get("/blog/seo-post/",
                               HTTP_HOST="smashfatbiolabs.ca").content.decode()
        self.assertEqual(html.count("<h1"), 1)
        self.assertIn("<h1>SEO Post</h1>", html)


class AlbertaCityPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog")
        call_command("seed_sites")

    CITIES = ["calgary", "edmonton", "red-deer", "lethbridge",
              "medicine-hat", "grande-prairie"]

    def test_vancouver_is_a_bc_city_page_on_its_own_owner(self):
        self.assertEqual(
            self.client.get("/research-peptides/vancouver/",
                            HTTP_HOST="smashfatbiolabs.ca").status_code, 200)
        for other in ("peptidesalberta.ca", "smashfat.ca", "smashfatbiolabs.com"):
            self.assertEqual(
                self.client.get("/research-peptides/vancouver/",
                                HTTP_HOST=other).status_code, 404, other)

    def test_bc_page_links_to_vancouver_and_back(self):
        bc = self.client.get("/research-peptides/british-columbia/",
                             HTTP_HOST="smashfatbiolabs.ca").content.decode()
        self.assertIn("/research-peptides/vancouver/", bc)
        van = self.client.get("/research-peptides/vancouver/",
                              HTTP_HOST="smashfatbiolabs.ca").content.decode()
        self.assertIn("/research-peptides/british-columbia/", van)

    def test_city_pages_serve_only_on_peptidesalberta(self):
        for slug in self.CITIES:
            self.assertEqual(
                self.client.get(f"/research-peptides/{slug}/",
                                HTTP_HOST="peptidesalberta.ca").status_code, 200, slug)
            for other in ("smashfat.ca", "smashfatbiolabs.ca", "smash-fat.com"):
                self.assertEqual(
                    self.client.get(f"/research-peptides/{slug}/",
                                    HTTP_HOST=other).status_code, 404, f"{slug} on {other}")

    def test_city_pages_link_back_to_the_province(self):
        html = self.client.get("/research-peptides/calgary/",
                               HTTP_HOST="peptidesalberta.ca").content.decode()
        self.assertIn("/research-peptides/alberta/", html)

    def test_province_page_links_to_every_city(self):
        html = self.client.get("/research-peptides/alberta/",
                               HTTP_HOST="peptidesalberta.ca").content.decode()
        for slug in self.CITIES:
            self.assertIn(f"/research-peptides/{slug}/", html, slug)

    def test_cities_are_in_the_sitemap(self):
        sm = self.client.get("/sitemap.xml",
                             HTTP_HOST="peptidesalberta.ca").content.decode()
        for slug in self.CITIES:
            self.assertIn(f"/research-peptides/{slug}/", sm, slug)

    def test_city_pages_carry_no_shared_boilerplate_section(self):
        """Two distinctness audits found the compliance paragraph, repeated six
        ways, was the doorway signature — not the local copy. It is rendered
        once by the template instead."""
        from apps.stores import regions
        banned = ["certificate of analysis", "purity figure", "purity or potency"]
        for slug in self.CITIES:
            r = regions.get(slug)
            blob = " ".join([s["body"] for s in r["sections"]]
                            + [f["a"] for f in r["faqs"]]).lower()
            for phrase in banned:
                self.assertNotIn(phrase, blob, f"{slug} still carries {phrase!r}")

    def test_city_pages_do_not_share_a_uniform_shape(self):
        """A uniform section/FAQ count across sibling pages is itself a
        duplicate-content fingerprint."""
        from apps.stores import regions
        shapes = {(len(regions.get(s)["sections"]), len(regions.get(s)["faqs"]))
                  for s in self.CITIES}
        self.assertGreater(len(shapes), 1, "every city page has the same shape")

    def test_no_two_city_pages_share_a_heading(self):
        from apps.stores import regions
        seen = {}
        for slug in self.CITIES:
            for s in regions.get(slug)["sections"]:
                h = s["h2"].strip().lower()
                self.assertNotIn(h, seen, f"{slug} reuses {seen.get(h)}'s heading {h!r}")
                seen[h] = slug

    def test_city_copy_makes_no_banned_claim(self):
        banned = ["Ships from", "ships from", "same-day", "overnight", "express",
                  "dosage", "weight loss", "cheapest", "purest"]
        for slug in self.CITIES:
            html = self.client.get(f"/research-peptides/{slug}/",
                                   HTTP_HOST="peptidesalberta.ca").content.decode()
            for phrase in banned:
                self.assertNotIn(phrase, html, f"{phrase!r} on {slug}")
            self.assertIn("Research Use Only", html)


class SeoHygieneTests(TestCase):
    """Cheap, high-value checks that catch the SEO defects that actually recur."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog")
        call_command("seed_sites")

    def test_region_titles_and_metas_fit_in_a_serp(self):
        """A title over ~60 chars or a description over ~158 gets truncated.
        Five of the first six city pages written for this project blew both."""
        from apps.stores import regions
        for r in regions.REGIONS:
            self.assertLessEqual(len(r["title"]), 60,
                                 f"{r['slug']} title is {len(r['title'])} chars")
            self.assertLessEqual(len(r["meta_description"]), 158,
                                 f"{r['slug']} meta is {len(r['meta_description'])} chars")
            self.assertGreaterEqual(len(r["meta_description"]), 110,
                                    f"{r['slug']} meta is only {len(r['meta_description'])} chars")

    def test_region_pages_are_reachable_from_the_storefront(self):
        """Region pages were orphans — linked only from each other, so the sole
        route in was the sitemap. Internal links are how crawl priority gets
        there."""
        from apps.stores import regions
        from apps.stores.models import Site
        for site in Site.objects.filter(is_active=True):
            html = self.client.get("/", HTTP_HOST=site.domain).content.decode()
            owned = [r for r in regions.for_site(site) if not r.get("parent")]
            self.assertTrue(owned, f"{site.domain} owns no regions")
            for r in owned:
                self.assertIn(f"/research-peptides/{r['slug']}/", html,
                              f"{site.domain} home page does not link {r['slug']}")

    def test_a_site_never_links_a_region_it_does_not_serve(self):
        from apps.stores import regions
        from apps.stores.models import Site
        import re as _re
        for site in Site.objects.filter(is_active=True):
            html = self.client.get("/", HTTP_HOST=site.domain).content.decode()
            for slug in set(_re.findall(r'/research-peptides/([a-z\-]+)/', html)):
                self.assertEqual(regions.owner_of(slug), site.domain,
                                 f"{site.domain} links {slug}, owned by {regions.owner_of(slug)}")

    def test_every_region_page_self_canonicalises(self):
        from apps.stores import regions
        import re as _re
        for r in regions.REGIONS:
            html = self.client.get(f"/research-peptides/{r['slug']}/",
                                   HTTP_HOST=r["owner"], secure=True).content.decode()
            canon = _re.findall(r'<link rel="canonical" href="([^"]+)"', html)
            self.assertEqual(len(canon), 1, f"{r['slug']} has {len(canon)} canonicals")
            self.assertTrue(canon[0].endswith(f"/research-peptides/{r['slug']}/"),
                            f"{r['slug']} canonical points at {canon[0]}")


class RegionAnalyticalClaimTests(TestCase):
    """Commit 17cdb66 stripped testing/COA/purity claims from the storefronts,
    but the region pages were missed — eight of them were still telling buyers
    the catalogue is 'released at a threshold of 99 percent or higher by HPLC'
    for a business that holds no analytical documentation at all. The existing
    claim test only looked for shipping and medical phrases, so nothing caught
    it. These tokens are now banned outright: none of them is needed even to
    deny the claim."""

    BANNED = [
        "HPLC", "USP", "high-performance liquid chromatography",
        "mass spec", "mass-spec", "release threshold", "released at a threshold",
        "third-party tested", "third party tested", "pharmaceutical grade",
        "pharmaceutical-grade", "GMP", "99%", "99 percent",
    ]

    def test_no_region_asserts_testing_purity_or_a_grade(self):
        from apps.stores import regions
        for r in regions.REGIONS:
            blob = " ".join(
                [r["title"], r["meta_description"], r["intro"]]
                + [s["h2"] + " " + s["body"] for s in r["sections"]]
                + [f["q"] + " " + f["a"] for f in r["faqs"]]
            ).lower()
            for token in self.BANNED:
                self.assertNotIn(token.lower(), blob,
                                 f"{r['slug']} asserts {token!r} — we hold no analytical data")

    def test_pages_that_discuss_documentation_say_we_have_none(self):
        """Explaining what a COA is remains fine. Implying we issue one is not."""
        from apps.stores import regions
        for r in regions.REGIONS:
            blob = " ".join([s["h2"] + " " + s["body"] for s in r["sections"]]
                            + [f["q"] + " " + f["a"] for f in r["faqs"]]).lower()
            if "certificate of analysis" not in blob:
                continue
            self.assertTrue(
                any(p in blob for p in ("no certificate of analysis", "none is issued",
                                        "nothing of that kind exists", "no purity figure",
                                        "none is quoted", "none is published")),
                f"{r['slug']} discusses a COA without stating we hold none")


class SeoMetaTests(TestCase):
    """Titles and descriptions are built to a budget now, not assembled inline.

    The three defects this locks out, all found by `manage.py seo_audit` across
    848 pages: every page on a domain shared one meta description; the eight
    strengths of a compound shared one title; and 344 descriptions and 33 titles
    ran past the length Google renders, so the distinguishing part was the part
    that got cut.
    """

    def setUp(self):
        from apps.catalog.models import Category, Product
        self.site = Site.objects.create(
            domain="seo-test.ca", brand_name="SEO Test Labs", theme="biolabs",
            country="CA", currency="CAD", is_active=True,
            meta_description="A test storefront.", tagline="Testing",
        )
        self.cat = Category.objects.create(name="Metabolic", slug="metabolic")
        self.p10 = Product.objects.create(
            name="Retatrutide", slug="reta-10", category=self.cat, price=58.80,
            family="retatrutide", size_label="10mg", is_family_default=True,
            is_active=True)
        self.p30 = Product.objects.create(
            name="Retatrutide", slug="reta-30", category=self.cat, price=93.00,
            family="retatrutide", size_label="30mg", is_active=True)

    # --- lengths -----------------------------------------------------------
    def test_titles_fit_the_budget(self):
        for meta in (seo.product(self.site, self.p10),
                     seo.category(self.site, self.cat, 12),
                     seo.generic(self.site, "Shipping & Delivery", "How it ships.")):
            self.assertLessEqual(len(meta["title"]), seo.TITLE_BUDGET, meta["title"])
            self.assertLessEqual(len(meta["description"]), seo.DESC_BUDGET)

    def test_fit_never_cuts_a_word_in_half(self):
        out = seo.fit("Peptide Reconstitution And Dosage Calculator For Labs",
                      ["Research Compound"], required="Where Do I Get Peptides?")
        self.assertLessEqual(len(out), seo.TITLE_BUDGET)
        self.assertNotIn(" Calc…", out.replace("…", "…"))
        self.assertTrue(out.endswith("Where Do I Get Peptides?") or "…" in out)

    def test_required_segment_is_never_dropped(self):
        """Dropping the brand is how eight domains end up sharing a title."""
        out = seo.fit("Repair & Recovery", ["Research Compounds", "Canada"],
                      required="Where Do I Get Peptides?")
        self.assertIn("Where Do I Get Peptides?", out)
        self.assertLessEqual(len(out), seo.TITLE_BUDGET)

    # --- distinctness ------------------------------------------------------
    def test_size_variants_do_not_share_a_title(self):
        a = seo.product(self.site, self.p10)
        b = seo.product(self.site, self.p30)
        self.assertNotEqual(a["title"], b["title"])
        self.assertNotEqual(a["description"], b["description"])
        self.assertIn("10mg", a["title"])
        self.assertIn("30mg", b["title"])

    def test_the_same_page_on_two_domains_differs(self):
        other = Site.objects.create(
            domain="seo-test.com", brand_name="Other Labs", theme="clinical",
            country="US", currency="USD", is_active=True,
            meta_description="Another storefront.")
        for build in (lambda s: seo.product(s, self.p10),
                      lambda s: seo.category(s, self.cat, 12),
                      lambda s: seo.generic(s, "Returns", "A long returns policy "
                                            "summary " * 20)):
            a, b = build(self.site), build(other)
            self.assertNotEqual(a["title"], b["title"])
            self.assertNotEqual(a["description"], b["description"])

    def test_category_description_is_not_the_homepage_description(self):
        self.assertNotEqual(seo.category(self.site, self.cat, 3)["description"],
                            seo.home(self.site)["description"])


class CategoryPageTests(TestCase):
    """`/category/<slug>/` used to render the homepage with a filter chip.

    Same title, same description, same h1, same body — on seven categories
    across eight domains. Fifty-six URLs, each a duplicate of the page it was
    supposed to support.
    """

    def setUp(self):
        from apps.catalog.models import Category, Product
        self.site = Site.objects.create(
            domain="cat-test.ca", brand_name="Cat Test", theme="biolabs",
            country="CA", currency="CAD", is_active=True,
            meta_description="A test storefront.")
        self.cat = Category.objects.create(name="Metabolic", slug="metabolic")
        self.other = Category.objects.create(name="Neuropeptides",
                                             slug="neuropeptides")
        Product.objects.create(name="Retatrutide", slug="reta", category=self.cat,
                               price=58.80, size_label="10mg", is_active=True)
        Product.objects.create(name="Semax", slug="semax", category=self.other,
                               price=30.00, size_label="5mg", is_active=True)

    def _get(self, path):
        return self.client.get(path, HTTP_HOST="cat-test.ca", secure=True)

    def test_category_page_differs_from_the_homepage(self):
        home = self._get("/").content.decode()
        cat = self._get("/category/metabolic/").content.decode()
        self.assertNotEqual(
            re.search(r"<title>(.*?)</title>", home, re.S).group(1),
            re.search(r"<title>(.*?)</title>", cat, re.S).group(1))
        self.assertNotEqual(
            re.search(r'name="description" content="(.*?)"', home).group(1),
            re.search(r'name="description" content="(.*?)"', cat).group(1))

    def test_category_h1_names_the_category(self):
        html = self._get("/category/metabolic/").content.decode()
        h1s = re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.S)
        self.assertEqual(len(h1s), 1, h1s)
        self.assertIn("Metabolic", h1s[0])

    def test_two_categories_do_not_share_copy(self):
        a = self._get("/category/metabolic/").content.decode()
        b = self._get("/category/neuropeptides/").content.decode()
        self.assertNotEqual(
            re.search(r"<title>(.*?)</title>", a, re.S).group(1),
            re.search(r"<title>(.*?)</title>", b, re.S).group(1))
        self.assertIn("incretin", a)
        self.assertNotIn("incretin", b)

    def test_category_page_lists_only_its_own_products(self):
        html = self._get("/category/metabolic/").content.decode()
        self.assertIn("Retatrutide", html)
        self.assertNotIn("Semax", html)

    def test_unknown_category_404s(self):
        self.assertEqual(self._get("/category/not-a-category/").status_code, 404)

    def test_category_copy_makes_no_banned_claim(self):
        """The same rule the blog is held to. This copy ships on 56 URLs."""
        from apps.blog import guardrails
        from apps.catalog import copy
        for slug, block in copy.CATEGORIES.items():
            text = " ".join([block["lede"]] + block["body"]
                            + block.get("considerations", []))
            with self.subTest(category=slug):
                self.assertEqual(guardrails.scan(text)[0], [])
        for domain, para in copy.SITE_FRAMING.items():
            with self.subTest(site=domain):
                self.assertEqual(guardrails.scan(para)[0], [])

    def test_every_site_has_its_own_framing_paragraph(self):
        from apps.catalog import copy
        seeded = set(Site.objects.values_list("domain", flat=True)) - {"cat-test.ca"}
        for domain in seeded:
            self.assertIn(domain, copy.SITE_FRAMING, f"{domain} has no framing")
        self.assertEqual(len(set(copy.SITE_FRAMING.values())),
                         len(copy.SITE_FRAMING), "two sites share a paragraph")
