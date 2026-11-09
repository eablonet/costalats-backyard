from django.shortcuts import get_object_or_404, redirect, render

from .. import classements
from ..models import Course, Participant
from .commun import est_htmx, lignes

__all__ = ["accueil", "bilan", "resume_course", "coureur", "horloge", "ecran"]


def _contexte_classement(request):
    """Lit les filtres (critère, genre, recherche) et calcule le classement."""
    critere = request.GET.get("critere")
    if critere not in classements.CRITERES:
        critere = "boucles"
    genre = request.GET.get("genre")
    if genre not in Participant.Genre.values:
        genre = None
    q = request.GET.get("q", "").strip()

    stats = classements.classement(classements.toutes_les_stats(genre=genre), critere)
    if q:  # filtrage APRÈS le classement : chacun garde son vrai rang
        stats = [s for s in stats if q.lower() in f"{s.participant.pseudo} {s.participant.nom_complet}".lower()]
    return {
        "stats": stats, "critere": critere, "genre": genre, "q": q,
        "criteres": [(cle, c.libelle) for cle, c in classements.CRITERES.items()],
        "genres": Participant.Genre.choices,
    }


def accueil(request):
    """Page Résultats : chiffres clés + graphique en haut, classements filtrables dessous."""
    ctx = _contexte_classement(request)
    if est_htmx(request):
        return render(request, "course/partials/classement.html", ctx)
    ctx["resume"] = classements.resume_course()
    return render(request, "course/accueil.html", ctx)


def bilan(request):
    """Ancienne page, fusionnée dans l'accueil."""
    return redirect("course:accueil")


def resume_course(request):
    return render(request, "course/partials/resume_course.html", {"resume": classements.resume_course()})


def coureur(request, pseudo):
    """Fiche publique d'un coureur : tout son historique."""
    participant = get_object_or_404(Participant, pseudo__iexact=pseudo)
    course = Course.get()
    return render(request, "course/coureur.html", {
        "participant": participant,
        "stats": classements.stats_participant(participant, course),
        "lignes": lignes(participant, course, avec_suivante=False),
        "lecture_seule": True,
    })


def horloge(request):
    return render(request, "course/partials/horloge.html")


def ecran(request):
    """Mode grand écran (projection) : un classement par catégorie, côte à côte.

    Le critère (boucles / série / chrono) est choisi par le JavaScript de la page,
    qui le fait tourner toutes les `ecran_bascule_minutes`.
    """
    course = Course.get()
    critere = request.GET.get("critere")
    if critere not in classements.CRITERES:
        critere = "boucles"
    stats = classements.toutes_les_stats(course)
    ctx = {
        "critere": critere,
        "criteres": [(cle, c.libelle) for cle, c in classements.CRITERES.items()],
        "par_genre": [
            (code, label, classements.classement([s for s in stats if s.participant.genre == code], critere))
            for code, label in Participant.Genre.choices
        ],
        "resume": classements.resume_course(course, stats),
    }
    gabarit = "course/partials/ecran_contenu.html" if est_htmx(request) else "course/ecran.html"
    return render(request, gabarit, ctx)
