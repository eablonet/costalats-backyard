from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Photo
from .photos import supprimer_fichiers


@receiver(post_delete, sender=Photo)
def effacer_fichiers_photo(sender, instance, **kwargs):
    """Aussi quand un participant est supprimé (ses photos partent en cascade)."""
    supprimer_fichiers(instance)
