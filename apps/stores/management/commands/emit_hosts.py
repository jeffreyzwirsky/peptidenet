from django.core.management.base import BaseCommand

from apps.stores.models import Site


class Command(BaseCommand):
    help = "Print the ALLOWED_HOSTS value for every active site (set PEPTIDENET_HOSTS)."

    def handle(self, *args, **opts):
        hosts = []
        for s in Site.objects.filter(is_active=True):
            hosts += s.all_hostnames()
        hosts = sorted(set(hosts))
        self.stdout.write(",".join(hosts))
