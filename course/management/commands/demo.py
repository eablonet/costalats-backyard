"""Remplit la base avec une course en cours et des coureurs fictifs.

    python manage.py demo            # course partie il y a 9 h 20
    python manage.py demo --vider    # efface d'abord participants et boucles
"""

import random
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from course.models import Boucle, Course, Participant

COUREURS = [
    ("Léa", "Martin", "lea_trail", "F"), ("Hugo", "Bernard", "hugo64", "H"), ("Chloé", "Dubois", "chlochlo", "F"),
    ("Lucas", "Thomas", "lulu", "H"), ("Manon", "Robert", "manon_runs", "F"), ("Nathan", "Richard", "nat", "H"),
    ("Inès", "Petit", "ines.p", "F"), ("Théo", "Durand", "theo_d", "H"), ("Camille", "Leroy", "cam", "F"),
    ("Louis", "Moreau", "loulou", "H"), ("Jade", "Simon", "jade", "E"), ("Gabin", "Laurent", "gabin", "E"),
    ("Sarah", "Lefebvre", "sarah_l", "F"), ("Arthur", "Michel", "tutur", "H"), ("Emma", "Garcia", "emma_g", "F"),
    ("Paul", "David", "paulo", "H"), ("Lina", "Bertrand", "lina", "E"), ("Jules", "Roux", "jujules", "H"),
]


class Command(BaseCommand):
    help = "Crée une course de démonstration avec des coureurs et des boucles."

    def add_arguments(self, parser):
        parser.add_argument("--vider", action="store_true")
        parser.add_argument("--force", action="store_true", help="Autoriser hors mode DEBUG (répétition).")

    def handle(self, *args, vider=False, force=False, **options):
        if not settings.DEBUG and not force:
            raise CommandError(
                "Refusé en production : cette commande mélangerait des coureurs fictifs aux vrais. "
                "Pour une répétition, ajouter --force."
            )
        if vider:
            Participant.objects.all().delete()
        course = Course.get()
        course.nom = "Backyard des Costalats"
        course.premier_depart = (timezone.now() - timedelta(hours=9, minutes=20)).replace(second=0, microsecond=0)
        course.nb_boucles_max = 24
        course.distance_km = 6.71
        course.denivele_m = 180
        course.save()

        ouvertes = course.nb_boucles_ouvertes()
        aleas = random.Random(42)
        for prenom, nom, pseudo, genre in COUREURS:
            p, _ = Participant.objects.get_or_create(
                pseudo=pseudo, defaults={"prenom": prenom, "nom": nom, "genre": genre}
            )
            debut = aleas.randint(1, 4)
            assiduite = aleas.uniform(0.35, 1.0)
            for n in range(debut, ouvertes + 1):
                if aleas.random() < assiduite:
                    chrono = timedelta(minutes=aleas.randint(38, 58), seconds=aleas.randint(0, 59))
                    Boucle.objects.get_or_create(
                        participant=p, numero=n,
                        defaults={"chrono": chrono if aleas.random() < 0.7 else None},
                    )
        self.stdout.write(self.style.SUCCESS(
            f"{Participant.objects.count()} coureurs, {Boucle.objects.count()} boucles, boucle {course.boucle_en_cours()} en cours."
        ))
