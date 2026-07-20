"""Set up the walled staff portal.

  python manage.py setup_portal                 # just ensure the group exists
  python manage.py setup_portal --user frontdesk # + create a walled staff user

A "walled" staff user is is_staff=False, is_superuser=False, and in the
"Portal Staff" group. Because is_staff=False, Django admin refuses them — the
/portal/ console is their only door. Set their password afterwards with:
  python manage.py changepassword <username>
(Passwords are never set here — they can't be typed by an assistant.)
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from apps.manage.access import PORTAL_GROUP


class Command(BaseCommand):
    help = "Create the Portal Staff group and, optionally, a walled staff user."

    def add_arguments(self, parser):
        parser.add_argument("--user", help="Username of a walled staff user to create.")
        parser.add_argument("--email", default="", help="Optional email for --user.")

    def handle(self, *args, **opts):
        group, created = Group.objects.get_or_create(name=PORTAL_GROUP)
        self.stdout.write(
            self.style.SUCCESS(f"Group '{PORTAL_GROUP}' {'created' if created else 'ready'}.")
        )

        username = opts.get("user")
        if not username:
            self.stdout.write("No --user given; group only. Done.")
            return

        User = get_user_model()
        user, made = User.objects.get_or_create(
            username=username,
            defaults={"email": opts.get("email", ""), "is_staff": False, "is_superuser": False},
        )
        # Enforce the wall even if the user already existed.
        user.is_staff = False
        user.is_superuser = False
        if made:
            user.set_unusable_password()
        user.save()
        user.groups.add(group)

        self.stdout.write(self.style.SUCCESS(
            f"{'Created' if made else 'Updated'} walled staff user '{username}'."
        ))
        self.stdout.write(self.style.WARNING(
            f"Set their password now:  python manage.py changepassword {username}"
        ))
        self.stdout.write("They sign in at /portal/  (they cannot reach the Django admin).")
