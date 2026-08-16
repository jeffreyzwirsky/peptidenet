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

    def _checkout(self, host="smashfat.ca", **extra):
        """Post a valid checkout. The dropship flow requires a shipping address
        (the partner ships direct) and the research-use-only acknowledgement."""
        payload = {"name": "L", "email": "a@b.ca", "shipping_address": "1 Bench Rd",
                   "payment_method": "interac", "ruo_ack": "1"}
        payload.update(extra)
        return self.client.post("/checkout/", payload,
                                content_type="application/json", HTTP_HOST=host)

    def test_checkout_does_not_decrement_stock_under_dropship(self):
        """We hold no inventory — the manufacturing partner ships direct — so
        checkout must not draw down an owned stock pool. `stock_qty` is now a
        supplier-availability signal a human maintains."""
        p = Product.objects.get(slug="bpc-157")
        start = p.stock_qty
        self.client.get("/", HTTP_HOST="smashfat.ca")
        self.client.post("/cart/add/", {"product_id": p.id, "qty": 3},
                         content_type="application/json", HTTP_HOST="smashfat.ca")
        self._checkout()
        p.refresh_from_db()
        self.assertEqual(p.stock_qty, start)

    def test_checkout_decrements_stock_when_dropship_is_off(self):
        """PEPTIDENET_DROPSHIP=0 restores the owned-inventory behaviour."""
        p = Product.objects.get(slug="bpc-157")
        start = p.stock_qty
        self.client.get("/", HTTP_HOST="smashfat.ca")
        self.client.post("/cart/add/", {"product_id": p.id, "qty": 3},
                         content_type="application/json", HTTP_HOST="smashfat.ca")
        with self.settings(DROPSHIP=False):
            self._checkout()
        p.refresh_from_db()
        # stock_qty counts vials; the cart counted 3 PACKS.
        self.assertEqual(p.stock_qty, start - 3 * p.vials_per_pack)

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
        self._checkout()
        o = Order.objects.latest("created_at")
        # 2 packs of 10 vials — unit_cost is per vial, so COGS covers 20.
        self.assertEqual(o.cost_total, p.unit_cost * 2 * p.vials_per_pack)
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
        self.client.post(f"/manage/orders/{o.pk}/", {"status": "supplier_shipped"})
        o.refresh_from_db()
        self.assertEqual(o.status, "supplier_shipped")

    def test_purchase_order_raised_from_paid_order(self):
        """A PO is only ever raised against a paid order — we never commit to
        the supplier on money we haven't received."""
        from apps.stores.models import Site
        from apps.suppliers.models import PurchaseOrder, Supplier

        supplier = Supplier.objects.create(
            name="Partner Labs", slug="partner-labs", email="orders@example.com",
            whatsapp="+15555550123", is_default=True,
        )
        site = Site.objects.first()
        p = Product.objects.get(slug="bpc-157")
        self.client.get("/", HTTP_HOST="smashfat.ca")
        self.client.post("/cart/add/", {"product_id": p.id, "qty": 2},
                         content_type="application/json", HTTP_HOST="smashfat.ca")
        self._checkout()
        order = Order.objects.latest("created_at")
        order.mark_paid(method="interac", reference="REF123")

        po = PurchaseOrder.build_for(order)
        self.assertEqual(po.supplier, supplier)
        self.assertEqual(po.ship_to, "1 Bench Rd")
        self.assertEqual(po.items.count(), 1)
        # The PO is denominated in vials — 2 packs is 20 vials to the partner.
        self.assertEqual(po.items.first().qty, 2 * p.vials_per_pack)

        # Idempotent — building twice must not double-order from the supplier.
        self.assertEqual(PurchaseOrder.build_for(order).pk, po.pk)

        po.mark_sent(channel="whatsapp", by="jeff")
        order.refresh_from_db()
        self.assertEqual(order.status, "po_sent")

        po.mark_shipped(tracking_number="TRK99", carrier="EMS")
        order.refresh_from_db()
        self.assertEqual(order.status, "supplier_shipped")
        self.assertEqual(order.tracking_number, "TRK99")

    def test_purchase_order_text_carries_no_customer_pricing(self):
        """The PO goes to the supplier. It must carry what to ship and where —
        never what our customer paid."""
        from apps.stores.models import Site
        from apps.suppliers.dispatch import render_po_text, whatsapp_link
        from apps.suppliers.models import PurchaseOrder, Supplier

        Supplier.objects.create(name="Partner", slug="partner",
                                whatsapp="+15555550123", is_default=True)
        site = Site.objects.first()
        order = Order.objects.create(number="SFB-9", site=site, total=999,
                                     shipping_address="12 Lab Way\nWinnipeg MB")
        order.items.create(product_name="BPC-157", unit_price=420, unit_cost=210,
                           qty=2, pack_size=10, line_total=840)
        po = PurchaseOrder.build_for(order)
        text = render_po_text(po)
        # Vials, spelled out. An unlabelled "2" beside a compound name is the
        # ambiguity that ships a customer 2 vials instead of 20.
        self.assertIn("20 vials x BPC-157", text)
        self.assertIn("12 Lab Way", text)
        # No pricing of any kind reaches the supplier. (Asserting on the digits
        # alone would be flaky — the PO number is 8 random digits.)
        self.assertNotIn("$", text)
        self.assertNotIn("Total", text)
        self.assertTrue(whatsapp_link(po).startswith("https://wa.me/15555550123"))

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


class PurchasingTests(TestCase):
    """The dropship queue: confirm payment, raise the PO, send it, track it."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog")
        call_command("seed_sites")

    def setUp(self):
        from django.contrib.auth.models import User
        self.staff = User.objects.create_user("boss", password="x", is_staff=True,
                                              is_superuser=True)
        self.client.force_login(self.staff)

    def test_page_loads_and_warns_when_no_supplier(self):
        r = self.client.get("/manage/purchasing/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "No supplier configured")

    def test_cannot_raise_po_on_unpaid_order(self):
        """We never commit to a supplier on money we haven't received."""
        from apps.stores.models import Site
        from apps.suppliers.models import PurchaseOrder, Supplier
        Supplier.objects.create(name="P", slug="p", email="a@b.c", is_default=True)
        o = Order.objects.create(number="SFB-2", site=Site.objects.first(),
                                 total=50, status="payment_review")
        self.client.post("/manage/purchasing/", {"action": "raise_po", "order_id": o.pk},
                         follow=True)
        self.assertFalse(PurchaseOrder.objects.filter(order=o).exists())

    def test_full_queue_walkthrough(self):
        from apps.stores.models import Site
        from apps.suppliers.models import PurchaseOrder, Supplier
        Supplier.objects.create(name="P", slug="p", email="a@b.c",
                                whatsapp="+15555550123", is_default=True)
        o = Order.objects.create(number="SFB-3", site=Site.objects.first(), total=50,
                                 status="payment_review", shipping_address="1 Rd")
        o.items.create(product_name="BPC-157", unit_price=42, unit_cost=21, qty=1,
                       line_total=42)

        self.client.post("/manage/purchasing/", {
            "action": "mark_paid", "order_id": o.pk,
            "payment_method": "interac", "payment_reference": "R1"})
        o.refresh_from_db()
        self.assertEqual(o.status, "paid")
        self.assertIsNotNone(o.paid_at)

        self.client.post("/manage/purchasing/", {"action": "raise_po", "order_id": o.pk})
        po = PurchaseOrder.objects.get(order=o)

        self.client.post("/manage/purchasing/", {
            "action": "mark_sent", "po_id": po.pk, "channel": "whatsapp"})
        o.refresh_from_db()
        self.assertEqual(o.status, "po_sent")

        self.client.post("/manage/purchasing/", {
            "action": "add_tracking", "po_id": po.pk,
            "tracking_number": "T1", "tracking_carrier": "EMS"})
        o.refresh_from_db()
        self.assertEqual(o.status, "supplier_shipped")
        self.assertEqual(o.tracking_number, "T1")

    def test_customer_can_see_order_status_page(self):
        from apps.stores.models import Site
        site = Site.objects.get(domain="smashfat.ca")
        o = Order.objects.create(number="SFB-4", site=site, total=42,
                                 status="paid", shipping_address="1 Rd")
        o.items.create(product_name="BPC-157", unit_price=42, unit_cost=21, qty=1,
                       line_total=42)
        r = self.client.get(f"/order/{o.number}/", HTTP_HOST="smashfat.ca")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "SFB-4")
        self.assertContains(r, "10–15 days")
        self.assertContains(r, "noindex")


class RecordingProxyTests(TestCase):
    """Playing a voicemail from the console.

    Jeff, 2026-08-16: "we can't actually play the voicemails in the super admin
    portal." The Play button linked straight at `recording_url`, which is a
    Twilio API URL requiring HTTP Basic auth — confirmed on the live console,
    where all nine Play links pointed at api.twilio.com. A browser cannot send
    those credentials, so every click showed Twilio's 401 XML.

    Same root cause as the empty-transcript bug: Twilio recording media needs
    credentials. That one was fixed server-side for Whisper; nobody checked the
    other consumer.
    """

    @classmethod
    def setUpTestData(cls):
        call_command("seed_sites")
        from apps.comms.models import Voicemail
        cls.boss = get_user_model().objects.create_user(
            "boss2", password="x", is_staff=True, is_superuser=True)
        cls.vm = Voicemail.objects.create(
            from_number="+12045551234", duration_sec=12,
            recording_url="https://api.twilio.com/2010-04-01/Accounts/AC1/Recordings/RE1")
        cls.evil = Voicemail.objects.create(
            from_number="+12045551235", duration_sec=3,
            recording_url="https://169.254.169.254/latest/meta-data/")

    def _url(self, vm):
        return f"/manage/recording/vm/{vm.pk}/"

    def test_anonymous_cannot_fetch_a_recording(self):
        r = self.client.get(self._url(self.vm))
        self.assertIn(r.status_code, (302, 403))

    def test_console_page_no_longer_links_at_twilio(self):
        """The actual reported symptom.

        A Call row AND a Voicemail row, because the two render through separate
        template branches. An earlier version of this test created only a
        voicemail, so the call branch never rendered — and a multi-line {# #}
        "comment" in that branch (Django's {# #} is single-line only, so it is
        not a comment) leaked into the live page 20 times while this test stayed
        green. A fixture that misses a branch is a test that proves nothing
        about it.
        """
        from apps.comms.models import Call
        Call.objects.create(direction="in", twilio_sid="CA-T1",
                            from_number="+12045551234", duration_sec=9,
                            recording_url="https://api.twilio.com/2010-04-01/"
                                          "Accounts/AC1/Recordings/RE2")
        self.client.force_login(self.boss)
        r = self.client.get("/manage/calls/")
        body = r.content.decode()
        self.assertIn("/manage/recording/call/", body)   # the call branch rendered
        self.assertNotIn("api.twilio.com", body)
        self.assertIn(f"/manage/recording/vm/{self.vm.pk}/", body)
        self.assertIn("<audio", body)
        self.assertIn('preload="none"', body)

    def test_it_streams_audio_when_twilio_returns_audio(self):
        from apps.comms import providers
        self.client.force_login(self.boss)

        class _Resp:
            status_code = 200
            headers = {"content-type": "audio/mpeg"}
            content = b"ID3fake-mp3-bytes"

        real = providers.fetch_recording
        providers.fetch_recording = lambda url, timeout=30: (_Resp(), "")
        try:
            r = self.client.get(self._url(self.vm))
        finally:
            providers.fetch_recording = real
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "audio/mpeg")
        self.assertEqual(r.content, b"ID3fake-mp3-bytes")
        # A customer's voice must not sit in a shared cache.
        self.assertIn("no-store", r["Cache-Control"])
        self.assertIn("private", r["Cache-Control"])

    def test_a_failed_fetch_is_loud_not_an_empty_200(self):
        """The failure-as-absence pattern this codebase keeps paying for. A
        silently empty 200 renders a player that just never plays."""
        from apps.comms import providers
        self.client.force_login(self.boss)
        real = providers.fetch_recording
        providers.fetch_recording = lambda url, timeout=30: (None, "fetch_failed")
        try:
            r = self.client.get(self._url(self.vm))
        finally:
            providers.fetch_recording = real
        self.assertEqual(r.status_code, 502)
        self.assertIn(b"fetch_failed", r.content)

    def test_it_refuses_a_stored_url_that_is_not_twilio(self):
        """SSRF guard. `recording_url` is written from a webhook body and the
        write-time check only enforces https, so a forged webhook could plant
        any https host — including link-local metadata. The proxy must refuse
        it, and must refuse it without making the request."""
        self.client.force_login(self.boss)
        r = self.client.get(self._url(self.evil))
        self.assertEqual(r.status_code, 502)
        self.assertIn(b"bad_url", r.content)

    def test_the_client_cannot_supply_a_url(self):
        """The route takes a row id. There is no parameter that becomes a
        fetch target."""
        self.client.force_login(self.boss)
        r = self.client.get("/manage/recording/vm/99999/")
        self.assertEqual(r.status_code, 404)

    def test_unknown_kind_is_404(self):
        self.client.force_login(self.boss)
        r = self.client.get("/manage/recording/bogus/1/")
        self.assertIn(r.status_code, (404, 400))


class RecordingUrlValidationTests(TestCase):
    def test_only_https_twilio_passes(self):
        from apps.comms.providers import recording_url_ok
        ok = "https://api.twilio.com/2010-04-01/Accounts/AC1/Recordings/RE1"
        self.assertTrue(recording_url_ok(ok))
        for bad in [
            "http://api.twilio.com/x",                      # not https
            "https://169.254.169.254/latest/meta-data/",    # cloud metadata
            "https://api.twilio.com.evil.test/x",           # suffix trick
            "https://evil.test/api.twilio.com/x",           # path trick
            "javascript:alert(1)",
            "", None,
        ]:
            self.assertFalse(recording_url_ok(bad), f"should refuse: {bad!r}")
