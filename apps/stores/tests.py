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
