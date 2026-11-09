"""Modèle de données.

Il n'y a PAS de table « boucle de la course » : l'heure de départ de la boucle n
se calcule (premier départ + (n-1) h). La table `Boucle` enregistre seulement
« le participant P déclare avoir fait la boucle n (chrono facultatif) ».
"""

import math
from datetime import timedelta

from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

DUREE_BOUCLE = timedelta(hours=1)


class Course(models.Model):
    """Singleton : une seule course, toujours pk=1. Utiliser Course.get()."""

    nom = models.CharField(max_length=120, default="Backyard")
    premier_depart = models.DateTimeField()
    nb_boucles_max = models.PositiveSmallIntegerField(default=24)
    distance_km = models.DecimalField(max_digits=5, decimal_places=2, default=6.71)
    denivele_m = models.PositiveIntegerField("D+ (m)", default=0)
    tolerance_minutes = models.PositiveSmallIntegerField(
        default=5,
        help_text="Une boucle peut être cochée ce nombre de minutes avant son départ.",
    )
    ecran_bascule_minutes = models.PositiveSmallIntegerField(
        "bascule de l'écran (minutes)", default=3,
        help_text="Le grand écran alterne Boucles / Série / Meilleur chrono à ce rythme. 0 = pas de bascule.",
    )
    cloturee = models.BooleanField(
        "clôturée", default=False,
        help_text="Résultats définitifs : les coureurs ne peuvent plus rien modifier (la gestion si).",
    )

    class Meta:
        verbose_name = "course"

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        prochaine_heure = (timezone.now() + DUREE_BOUCLE).replace(minute=0, second=0, microsecond=0)
        course, _ = cls.objects.get_or_create(pk=1, defaults={"premier_depart": prochaine_heure})
        return course

    # --- Calendrier --------------------------------------------------------
    @property
    def numeros(self):
        return range(1, self.nb_boucles_max + 1)

    @property
    def numeros_partis(self):
        """1..boucle en cours : sert à dessiner la frise des boucles."""
        return range(1, self.boucle_en_cours() + 1)

    @property
    def terminee(self):
        return timezone.now() >= self.depart(self.nb_boucles_max) + DUREE_BOUCLE

    def depart(self, numero):
        return self.premier_depart + (numero - 1) * DUREE_BOUCLE

    def nb_boucles_ouvertes(self, maintenant=None):
        """Nombre de boucles qu'on peut cocher maintenant (0 avant le début)."""
        maintenant = maintenant or timezone.now()
        ecart = maintenant + timedelta(minutes=self.tolerance_minutes) - self.premier_depart
        if ecart < timedelta(0):
            return 0
        return min(math.floor(ecart / DUREE_BOUCLE) + 1, self.nb_boucles_max)

    def boucle_ouverte(self, numero, maintenant=None):
        return 1 <= numero <= self.nb_boucles_ouvertes(maintenant)

    def boucle_en_cours(self, maintenant=None):
        """Numéro de la boucle partie le plus récemment (0 si pas commencé)."""
        maintenant = maintenant or timezone.now()
        if maintenant < self.premier_depart:
            return 0
        return min(math.floor((maintenant - self.premier_depart) / DUREE_BOUCLE) + 1, self.nb_boucles_max)

    def prochain_depart(self, maintenant=None):
        """(numéro, datetime) du prochain départ, ou None si la course est finie."""
        n = self.boucle_en_cours(maintenant) + 1
        return (n, self.depart(n)) if n <= self.nb_boucles_max else None


class Participant(models.Model):
    class Genre(models.TextChoices):
        FEMME = "F", "Femme"
        HOMME = "H", "Homme"
        ENFANT = "E", "Enfant"

    prenom = models.CharField("prénom", max_length=60)
    nom = models.CharField(max_length=60)
    pseudo = models.CharField(max_length=30)
    genre = models.CharField(max_length=1, choices=Genre.choices)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["pseudo"]
        constraints = [
            models.UniqueConstraint(Lower("pseudo"), name="pseudo_unique_insensible_casse"),
        ]

    def __str__(self):
        return self.pseudo

    @property
    def nom_complet(self):
        return f"{self.prenom} {self.nom}"


class Boucle(models.Model):
    """Une boucle déclarée par un participant (chrono facultatif)."""

    class Source(models.TextChoices):
        COUREUR = "coureur", "Coureur"
        GESTION = "gestion", "Gestion"

    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name="boucles")
    numero = models.PositiveSmallIntegerField("n° de boucle")
    chrono = models.DurationField(null=True, blank=True)
    saisie_par = models.CharField(max_length=10, choices=Source.choices, default=Source.COUREUR)
    declare_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["participant", "numero"]
        constraints = [
            models.UniqueConstraint(fields=["participant", "numero"], name="une_boucle_par_numero"),
        ]

    def __str__(self):
        return f"{self.participant} – boucle {self.numero}"
