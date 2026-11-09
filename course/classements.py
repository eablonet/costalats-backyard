"""Calcul des statistiques et classements.

Tout se calcule en Python à partir d'une seule requête (participants + boucles
préchargées) : pour quelques centaines de coureurs c'est instantané, et bien plus
lisible que des agrégats SQL pour les séries consécutives.
"""

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from itertools import groupby

from .models import Course, Participant


def serie_max(numeros):
    """Longueur de la plus longue suite de numéros consécutifs.

    Astuce des « îlots » : dans une liste triée, numero - rang est constant
    à l'intérieur d'une série. [1,2,3,5,6,9] -> clés [1,1,1,2,2,4] -> 3.
    """
    numeros = sorted(set(numeros))
    return max(
        (len(list(g)) for _, g in groupby(enumerate(numeros), key=lambda t: t[1] - t[0])),
        default=0,
    )


@dataclass
class Stats:
    participant: Participant
    numeros: list = field(default_factory=list)
    chronos: list = field(default_factory=list)  # chronos renseignés uniquement
    km: float = 0.0
    denivele: int = 0
    rang: int | None = None

    @property
    def nb_boucles(self):
        return len(self.numeros)

    @property
    def serie(self):
        return serie_max(self.numeros)

    @property
    def meilleur_chrono(self):
        return min(self.chronos, default=None)

    @property
    def derniere_boucle(self):
        return max(self.numeros, default=None)


def stats_participant(participant, course):
    boucles = list(participant.boucles.all())
    numeros = [b.numero for b in boucles]
    return Stats(
        participant=participant,
        numeros=numeros,
        chronos=[b.chrono for b in boucles if b.chrono],
        km=float(course.distance_km) * len(numeros),
        denivele=course.denivele_m * len(numeros),
    )


def toutes_les_stats(course=None, genre=None):
    course = course or Course.get()
    participants = Participant.objects.prefetch_related("boucles")
    if genre:
        participants = participants.filter(genre=genre)
    return [stats_participant(p, course) for p in participants]


@dataclass(frozen=True)
class Critere:
    libelle: str
    valeur: Callable          # Stats -> valeur comparable
    croissant: bool = False   # True : la plus petite valeur gagne (chrono)
    retenu: Callable = lambda s: True  # qui apparaît dans ce classement


CRITERES = {
    "boucles": Critere("Boucles", lambda s: s.nb_boucles),
    "serie": Critere("Série", lambda s: s.serie, retenu=lambda s: s.nb_boucles > 0),
    "chrono": Critere("Meilleur chrono", lambda s: s.meilleur_chrono, croissant=True,
                      retenu=lambda s: s.meilleur_chrono is not None),
}


def classement(stats, critere="boucles"):
    """Classe selon un critère de CRITERES. Égalité = même rang (1, 2, 2, 4…),
    sans second critère ; à égalité, ordre alphabétique pour l'affichage seulement.
    """
    c = CRITERES[critere]
    retenus = [s for s in stats if c.retenu(s)]
    retenus.sort(key=lambda s: s.participant.pseudo.lower())
    retenus.sort(key=c.valeur, reverse=not c.croissant)  # tri stable : l'alphabet départage
    for i, s in enumerate(retenus):
        egal = i and c.valeur(retenus[i - 1]) == c.valeur(s)
        s.rang = retenus[i - 1].rang if egal else i + 1
    return retenus


def coureurs_par_boucle(course, stats):
    """[(numero, nb de coureurs)] pour chaque boucle déjà partie."""
    compte = Counter(n for s in stats for n in s.numeros)
    return [(n, compte[n]) for n in course.numeros_partis]


def resume_course(course=None, stats=None):
    """Chiffres clés + données du graphique, en haut de la page Résultats et sur l'écran."""
    course = course or Course.get()
    stats = stats if stats is not None else toutes_les_stats(course)
    par_boucle = coureurs_par_boucle(course, stats)
    return {
        "participants": len(stats),
        "partis": sum(1 for s in stats if s.nb_boucles),
        "boucles": sum(s.nb_boucles for s in stats),
        "km": sum(s.km for s in stats),
        "denivele": sum(s.denivele for s in stats),
        "par_boucle": par_boucle,
        "max_par_boucle": max((c for _, c in par_boucle), default=0),
    }
