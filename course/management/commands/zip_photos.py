"""Crée media/exports/photos-backyard.zip avec toutes les photos, bien nommées.

Lancée en tâche de fond par le bouton de la gestion ; utilisable aussi à la main :
    python manage.py zip_photos
"""

from django.core.management.base import BaseCommand, CommandError

from course import photos


class Command(BaseCommand):
    help = "Crée le zip de toutes les photos (prenom_nom_01.jpg, depart_B03_01.jpg…)."

    def handle(self, *args, **options):
        try:
            photos.verifier_espace_disque()
        except photos.PhotoRefusee as e:
            photos.chemin_zip_en_cours().unlink(missing_ok=True)
            raise CommandError(str(e))
        chemin = photos.creer_zip()
        self.stdout.write(self.style.SUCCESS(f"Zip prêt : {chemin} ({chemin.stat().st_size / 1024**2:.0f} Mo)"))
