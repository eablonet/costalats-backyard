"""Outils partagés par les vues coureur et gestion."""

from dataclasses import dataclass
from datetime import datetime

from .. import session
from ..models import Boucle


@dataclass
class Ligne:
    """Une ligne du carnet de course : la boucle n et ce que le coureur a déclaré."""

    numero: int
    depart: datetime
    boucle: Boucle | None
    ouverte: bool          # la boucle est partie (tolérance comprise)
    verrouillee: bool = False  # course clôturée

    @property
    def faite(self):
        return self.boucle is not None

    @property
    def modifiable(self):
        """Modifiable par le coureur (la gestion, elle, peut toujours)."""
        return self.ouverte and not self.verrouillee


def lignes(participant, course, avec_suivante=True):
    """Lignes du carnet, la plus récente en haut.

    avec_suivante : ajoute la prochaine boucle (grisée) — utile dans le carnet,
    pas sur la fiche publique qui ne montre que l'historique.
    """
    faites = {b.numero: b for b in participant.boucles.all()}
    ouvertes = course.nb_boucles_ouvertes()
    fin = ouvertes + 1 if avec_suivante and not course.cloturee else ouvertes
    fin = min(max(fin, *faites, 0), course.nb_boucles_max)
    return [
        Ligne(n, course.depart(n), faites.get(n), n <= ouvertes, course.cloturee)
        for n in range(fin, 0, -1)
    ]


def ligne(participant, course, numero):
    boucle = participant.boucles.filter(numero=numero).first()
    return Ligne(numero, course.depart(numero), boucle, course.boucle_ouverte(numero), course.cloturee)


def est_htmx(request):
    return request.headers.get("HX-Request") == "true"


def peut_modifier(request, participant):
    """Le coureur connecté sur cet appareil, ou la gestion."""
    return request.user.is_staff or participant.pk in session.ids_connectes(request)


def source(request, participant):
    if participant.pk in session.ids_connectes(request):
        return Boucle.Source.COUREUR
    return Boucle.Source.GESTION
