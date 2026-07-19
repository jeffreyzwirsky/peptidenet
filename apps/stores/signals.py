from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .middleware import clear_host_cache
from .models import Site


@receiver(post_save, sender=Site)
@receiver(post_delete, sender=Site)
def _bust_host_cache(sender, **kwargs):
    clear_host_cache()
