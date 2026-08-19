from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.security.models import ConsoleMfaDevice


class Command(BaseCommand):
    help = "Remove a console user's TOTP device so they can enroll again after password verification."

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args, **options):
        user = get_user_model().objects.filter(username=options["username"]).first()
        if user is None:
            raise CommandError("No such user.")
        deleted, _ = ConsoleMfaDevice.objects.filter(user=user).delete()
        self.stdout.write(self.style.SUCCESS(
            f"MFA reset for {user.get_username()} ({'device removed' if deleted else 'no device existed'})."
        ))
