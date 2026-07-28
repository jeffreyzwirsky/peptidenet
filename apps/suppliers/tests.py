"""Cost-plus pricing: the guards, not the arithmetic.

The maths is one division. What makes an unattended job that edits live retail
prices safe is what it refuses to do, so that is what these tests pin.
"""
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.catalog.models import Product
from apps.suppliers.models import FxRate, PriceChange, SupplierPrice


class SupplierPriceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog")
        call_command("import_supplier_prices", verbosity=0)

    def test_pack_price_converts_to_a_per_vial_cost(self):
        bpc = SupplierPrice.objects.get(cat_no="BC10")
        self.assertEqual(bpc.pack_size, 10)
        self.assertEqual(bpc.pack_price, Decimal("64"))
        self.assertEqual(bpc.unit_price, Decimal("6.40"))

    def test_volumes_are_not_treated_as_boxes_of_ten(self):
        """A 10ml bottle is one bottle. Dividing it by ten would understate the
        cost of every consumable by an order of magnitude."""
        water = SupplierPrice.objects.get(cat_no="WA10")
        self.assertEqual(water.pack_size, 1)
        self.assertEqual(water.unit_price, water.pack_price)

    def test_reimport_moves_prices_without_duplicating(self):
        before = SupplierPrice.objects.count()
        SupplierPrice.objects.filter(cat_no="BC10").update(pack_price=Decimal("1"))
        call_command("import_supplier_prices", verbosity=0)
        self.assertEqual(SupplierPrice.objects.count(), before)
        self.assertEqual(SupplierPrice.objects.get(cat_no="BC10").pack_price,
                         Decimal("64"))

    def test_risk_classes_are_carried_through(self):
        self.assertEqual(SupplierPrice.objects.get(cat_no="SM10").risk, "patented")
        self.assertEqual(SupplierPrice.objects.get(cat_no="H10").risk, "hormone")
        self.assertEqual(SupplierPrice.objects.get(cat_no="DR5").risk, "controlled")
        self.assertTrue(SupplierPrice.objects.get(cat_no="SM10").needs_legal_review)
        self.assertFalse(SupplierPrice.objects.get(cat_no="BC10").needs_legal_review)


class FxTests(TestCase):
    def test_no_rate_means_no_conversion_not_a_guess(self):
        self.assertIsNone(FxRate.convert(Decimal("10"), "USD", "CAD"))

    def test_same_currency_needs_no_rate(self):
        self.assertEqual(FxRate.convert(Decimal("10"), "USD", "USD"), Decimal("10"))

    def test_rate_goes_stale(self):
        fx = FxRate.objects.create(base="USD", quote="CAD", rate=Decimal("1.37"))
        self.assertFalse(fx.is_stale)
        FxRate.objects.filter(pk=fx.pk).update(
            fetched_at=timezone.now() - timedelta(hours=FxRate.STALE_AFTER_HOURS + 1))
        self.assertTrue(FxRate.objects.get(pk=fx.pk).is_stale)

    def test_manual_rate_outside_plausible_range_is_refused(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            call_command("fetch_fx", set="94.2", verbosity=0)
        self.assertFalse(FxRate.objects.exists())


class RepriceGuardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog")
        call_command("import_supplier_prices", verbosity=0)

    def _run(self, **kw):
        out = StringIO()
        call_command("reprice", stdout=out, stderr=out, **kw)
        return out.getvalue()

    def _fx(self, rate="1.37"):
        return FxRate.objects.create(base="USD", quote="CAD",
                                     rate=Decimal(rate), source="test")

    def test_refuses_to_run_with_no_rate(self):
        p = Product.objects.get(slug="bpc-157")
        before = p.price
        out = self._run()
        self.assertIn("No USD/CAD rate", out)
        self.assertEqual(Product.objects.get(pk=p.pk).price, before)

    def test_refuses_to_run_on_a_stale_rate(self):
        """The failure this design is most exposed to: the feed goes quiet and
        prices keep recalculating from a number nobody checked."""
        fx = self._fx()
        FxRate.objects.filter(pk=fx.pk).update(
            fetched_at=timezone.now() - timedelta(hours=FxRate.STALE_AFTER_HOURS + 1))
        p = Product.objects.get(slug="bpc-157")
        before = p.price
        out = self._run()
        self.assertIn("stale", out.lower())
        self.assertEqual(Product.objects.get(pk=p.pk).price, before)

    def test_big_moves_are_blocked_not_applied(self):
        """A mistyped cost is likelier than a genuine 40% swing."""
        self._fx()
        p = Product.objects.get(slug="bpc-157")
        p.auto_price = True
        p.target_margin_pct = Decimal("10")   # would slash the price
        p.save()
        before = p.price
        out = self._run(slug="bpc-157")
        self.assertIn("move exceeds", out)
        self.assertEqual(Product.objects.get(pk=p.pk).price, before)
        self.assertFalse(PriceChange.objects.filter(product=p).exists())

    def test_force_applies_a_blocked_move_and_records_it(self):
        self._fx()
        p = Product.objects.get(slug="bpc-157")
        p.auto_price = True
        p.target_margin_pct = Decimal("10")
        p.save()
        self._run(force=True, slug="bpc-157")
        p.refresh_from_db()
        self.assertLess(p.price, Decimal("42.00"))
        change = PriceChange.objects.get(product=p)
        self.assertEqual(change.new_price, p.price)
        self.assertEqual(change.fx_rate, Decimal("1.370000"))

    def test_small_fx_wobble_does_not_move_public_prices(self):
        """Without a threshold the nightly rate wobble would nudge every price."""
        self._fx("1.37")
        call_command("reprice", "--calibrate", stdout=StringIO())
        p = Product.objects.get(slug="bpc-157")
        before = p.price
        self._fx("1.372")           # a 0.15% move
        self._run()
        self.assertEqual(Product.objects.get(pk=p.pk).price, before)

    def test_calibrate_makes_switching_on_a_no_op(self):
        """Turning cost-plus on must not reprice a live catalogue in one go."""
        self._fx()
        prices = dict(Product.objects.filter(auto_price=True)
                      .values_list("pk", "price"))
        self.assertTrue(prices)
        call_command("reprice", "--calibrate", stdout=StringIO())
        self._run()
        for pk, old in prices.items():
            self.assertEqual(Product.objects.get(pk=pk).price, old)

    def test_comparison_price_is_never_recomputed(self):
        """`list_price` is what we used to charge — a historical fact. Deriving
        it would manufacture a 'was' price that was never charged."""
        self._fx()
        p = Product.objects.get(slug="bpc-157")
        p.auto_price = True
        p.target_margin_pct = Decimal("10")
        p.save()
        was = p.list_price
        self._run(force=True, slug="bpc-157")
        self.assertEqual(Product.objects.get(pk=p.pk).list_price, was)

    def test_products_without_a_supplier_link_are_left_alone(self):
        self._fx()
        p = Product.objects.get(slug="bpc-157")
        p.auto_price = True
        p.supplier_cat_no = ""
        p.save()
        before = p.price
        self._run()
        self.assertEqual(Product.objects.get(pk=p.pk).price, before)


class PricingPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth import get_user_model
        call_command("seed_catalog")
        call_command("seed_sites")
        call_command("import_supplier_prices", verbosity=0)
        cls.staff = get_user_model().objects.create_user(
            "boss", password="x", is_staff=True, is_superuser=True)

    def test_page_requires_login(self):
        self.assertEqual(self.client.get("/manage/pricing/").status_code, 302)

    def test_page_shows_costs_and_flags(self):
        self.client.force_login(self.staff)
        html = self.client.get("/manage/pricing/").content.decode()
        self.assertIn("Price list", html)
        self.assertIn("BC10", html)
        self.assertIn("Not for listing without a decision", html)

    def test_cost_data_never_reaches_a_storefront(self):
        """The supplier, the catalogue codes and the costs are staff-only. This
        is the same silence the storefronts keep about origin."""
        for path in ("/", "/product/bpc-157/"):
            html = self.client.get(path, HTTP_HOST="smashfatbiolabs.ca").content.decode()
            for secret in ("BC10", "BBKG80", "supplier_cat_no", "unit_cost",
                           "target_margin", "Warehouse"):
                self.assertNotIn(secret, html, f"{secret} leaked on {path}")
