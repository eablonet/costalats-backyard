"""Comptes coureurs connectés sur un appareil (sans mot de passe).

La session stocke une liste ordonnée [[id, horodatage_connexion], ...] et l'indice
du compte actif. Chaque compte expire 24 h après SA connexion : on peut donc
ajouter un deuxième coureur le lendemain sans prolonger le premier.
"""

from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

from .models import Participant

CLE_COMPTES = "comptes"
CLE_ACTIF = "compte_actif"


def _duree():
    return timedelta(hours=getattr(settings, "DUREE_CONNEXION_COUREUR_H", 24))


def _comptes_valides(request):
    """Purge les comptes expirés et renvoie la liste [[id, iso], ...]."""
    limite = timezone.now() - _duree()
    comptes = request.session.get(CLE_COMPTES, [])
    valides = [c for c in comptes if datetime.fromisoformat(c[1]) > limite]
    if valides != comptes:
        request.session[CLE_COMPTES] = valides
        request.session[CLE_ACTIF] = min(request.session.get(CLE_ACTIF, 0), max(len(valides) - 1, 0))
    return valides


def ids_connectes(request):
    return [c[0] for c in _comptes_valides(request)]


def participants_connectes(request):
    ids = ids_connectes(request)
    par_id = Participant.objects.in_bulk(ids)
    return [par_id[i] for i in ids if i in par_id]


def actif(request):
    ids = ids_connectes(request)
    if not ids:
        return None
    return Participant.objects.filter(pk=ids[request.session.get(CLE_ACTIF, 0) % len(ids)]).first()


def connecter(request, participant):
    """Ajoute le compte (ou le rafraîchit) et le rend actif."""
    comptes = [c for c in _comptes_valides(request) if c[0] != participant.pk]
    comptes.append([participant.pk, timezone.now().isoformat()])
    request.session[CLE_COMPTES] = comptes
    request.session[CLE_ACTIF] = len(comptes) - 1


def basculer(request, sens):
    """sens = +1 ou -1 ; boucle circulairement sur les comptes connectés."""
    n = len(_comptes_valides(request))
    if n:
        request.session[CLE_ACTIF] = (request.session.get(CLE_ACTIF, 0) + sens) % n


def deconnecter(request, participant_id):
    comptes = [c for c in _comptes_valides(request) if c[0] != participant_id]
    request.session[CLE_COMPTES] = comptes
    request.session[CLE_ACTIF] = max(len(comptes) - 1, 0)
