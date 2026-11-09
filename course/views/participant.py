from django.contrib import messages
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .. import classements, session
from ..forms import ChronoForm, ConnexionForm, ParticipantForm
from ..models import Boucle, Course, Participant
from .commun import ligne, lignes, peut_modifier, source

__all__ = [
    "inscription", "connexion", "moi", "basculer_compte", "deconnexion",
    "basculer_boucle", "saisir_chrono", "resume", "carnet",
]


def inscription(request):
    form = ParticipantForm(request.POST or None)
    if form.is_valid():
        participant = form.save()
        session.connecter(request, participant)
        messages.success(request, f"Bienvenue {participant.prenom} ! Bonne course.")
        return redirect("course:moi")
    return render(request, "course/inscription.html", {"form": form})


def connexion(request):
    form = ConnexionForm(request.POST or None)
    if form.is_valid():
        session.connecter(request, form.participant)
        return redirect("course:moi")
    return render(request, "course/connexion.html", {"form": form})


def moi(request):
    """Carnet de course du compte actif sur cet appareil."""
    participant = session.actif(request)
    if participant is None:
        return redirect("course:connexion")
    course = Course.get()
    return render(request, "course/moi.html", {
        "participant": participant,
        "stats": classements.stats_participant(participant, course),
        "lignes": lignes(participant, course),
        "comptes": session.participants_connectes(request),
    })


@require_POST
def basculer_compte(request, sens):
    session.basculer(request, 1 if sens == "suivant" else -1)
    return redirect("course:moi")


@require_POST
def deconnexion(request, pk):
    session.deconnecter(request, pk)
    return redirect("course:moi" if session.ids_connectes(request) else "course:accueil")


# --- Actions HTMX sur une boucle (coureur ou gestion) ---------------------

def _rendre_ligne(request, participant, course, numero):
    reponse = render(request, "course/partials/ligne_boucle.html", {
        "participant": participant,
        "ligne": ligne(participant, course, numero),
    })
    reponse["HX-Trigger"] = "boucles-modifiees"  # met à jour le résumé en haut de page
    return reponse


def _verifier(request, pk, numero):
    """Renvoie (participant, course, erreur_http_ou_None)."""
    participant = get_object_or_404(Participant, pk=pk)
    course = Course.get()
    if not peut_modifier(request, participant):
        return participant, course, HttpResponseForbidden("Compte non connecté sur cet appareil.")
    if not (1 <= numero <= course.nb_boucles_max):
        return participant, course, HttpResponse("Boucle inexistante.", status=400)
    # La gestion peut corriger n'importe quelle boucle, le coureur seulement les boucles parties.
    if not request.user.is_staff:
        if course.cloturee:
            return participant, course, HttpResponse("La course est clôturée.", status=400)
        if not course.boucle_ouverte(numero):
            return participant, course, HttpResponse("Cette boucle n'est pas encore partie.", status=400)
    return participant, course, None


@require_POST
def basculer_boucle(request, pk, numero):
    participant, course, erreur = _verifier(request, pk, numero)
    if erreur:
        return erreur
    supprimees, _ = Boucle.objects.filter(participant=participant, numero=numero).delete()
    if not supprimees:
        Boucle.objects.create(participant=participant, numero=numero, saisie_par=source(request, participant))
    return _rendre_ligne(request, participant, course, numero)


@require_POST
def saisir_chrono(request, pk, numero):
    """Enregistre (ou efface si vide) le chrono ; coche la boucle au passage."""
    participant, course, erreur = _verifier(request, pk, numero)
    if erreur:
        return erreur
    form = ChronoForm(request.POST)
    if not form.is_valid():
        return render(request, "course/partials/ligne_boucle.html", {
            "participant": participant,
            "ligne": ligne(participant, course, numero),
            "erreur": form.errors["chrono"][0],
            "chrono_ouvert": True,
        })
    Boucle.objects.update_or_create(
        participant=participant, numero=numero,
        defaults={"chrono": form.cleaned_data["chrono"]},
        create_defaults={"chrono": form.cleaned_data["chrono"], "saisie_par": source(request, participant)},
    )
    return _rendre_ligne(request, participant, course, numero)


def resume(request, pk):
    """Petit bloc de stats (boucles, km, D+, série), rechargé après chaque action."""
    participant = get_object_or_404(Participant, pk=pk)
    return render(request, "course/partials/resume.html", {
        "stats": classements.stats_participant(participant, Course.get()),
    })


def carnet(request, pk):
    """Liste des boucles d'un coureur, rechargée à chaque départ."""
    participant = get_object_or_404(Participant, pk=pk)
    return render(request, "course/partials/carnet.html", {
        "participant": participant,
        "lignes": lignes(participant, Course.get()),
    })
