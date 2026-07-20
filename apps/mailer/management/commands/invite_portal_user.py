"""Invite a portal staff user by email (or (re)send them a set-password link).

  python manage.py invite_portal_user frontdesk --email desk@example.com

Ensures the user exists as a walled staff member (is_staff=False, in the Portal
Staff group), then builds a single-use set-password link and emails it through
Mailgun. The link is ALSO printed, so you can hand it over even before email is
live. Works for users who have never set a password (unlike the self-serve
'forgot password' form).
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.tokens import default_token_generator
from django.core.management.base import BaseCommand, CommandError
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.manage.access import PORTAL_GROUP
from apps.mailer import mailer


class Command(BaseCommand):
    help = "Create/ensure a walled staff user and email them a set-password link."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("--email", default="")

    def handle(self, *args, **opts):
        from django.conf import settings

        User = get_user_model()
        username = opts["username"]
        user, made = User.objects.get_or_create(username=username)
        user.is_staff = False
        user.is_superuser = False
        if opts.get("email"):
            user.email = opts["email"]
        if made:
            user.set_unusable_password()
        user.save()
        group, _ = Group.objects.get_or_create(name=PORTAL_GROUP)
        user.groups.add(group)

        if not user.email:
            raise CommandError(
                f"User '{username}' has no email. Re-run with --email you@example.com"
            )

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        path = reverse("password_reset_confirm", args=[uid, token])
        url = settings.PORTAL_BASE_URL.rstrip("/") + path

        sent = mailer.send_invite(user, url)
        self.stdout.write(self.style.SUCCESS(f"{'Created' if made else 'Updated'} '{username}'."))
        self.stdout.write(f"Set-password link (single-use):\n  {url}")
        self.stdout.write(
            self.style.SUCCESS("Invite emailed.") if sent
            else self.style.WARNING("Email is stubbed (not live) — hand them the link above.")
        )
