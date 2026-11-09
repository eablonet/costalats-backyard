import csv

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView, LogoutView
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from .. import classements
from ..forms import CourseForm, ParticipantForm
from ..models import Boucle, Course, Participant
from ..templatetags.course_extras import chrono, km
from .commun import est_htmx, lignes

__all__ = [
    "GestionConnexion", "GestionDeconnexion",
    "gestion_liste", "gestion_ajouter", "gestion_participant",
    "gestion_supprimer", "gestion_plus_un", "gestion_course", "gestion_cloturer", "gestion_export",
]


# Toutes les pages de gestion renvoient vers NOTRE formulaire de connexion, pas /admin/.
staff_member_required = user_passes_test(lambda u: u.is_active and u.is_staff,
                                         login_url="course:gestion_connexion")


class ConnexionOrganisateurForm(AuthenticationForm):
    """Comme la connexion Django, mais réservée aux comptes staff."""

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise forms.ValidationError("Ce compte n'a pas accès à la gestion.", code="non_staff")


class GestionConnexion(LoginView):
    template_name = "course/gestion/connexion.html"
    authentication_form = ConnexionOrganisateurForm
    redirect_authenticated_user = True
    next_page = "course:gestion_liste"


class GestionDeconnexion(LogoutView):
    next_page = "course:accueil"


@staff_member_required
def gestion_liste(request):
    q = request.GET.get("q", "").strip()
    stats = classements.classement(classements.toutes_les_stats())
    if q:
        q_min = q.lower()
        stats = [s for s in stats if q_min in f"{s.participant.pseudo} {s.participant.nom_complet}".lower()]
    gabarit = "course/gestion/partials/tableau.html" if est_htmx(request) else "course/gestion/liste.html"
    return render(request, gabarit, {"stats": stats, "q": q})


@staff_member_required
def gestion_ajouter(request):
    form = ParticipantForm(request.POST or None)
    if form.is_valid():
        participant = form.save()
        messages.success(request, f"{participant} ajouté·e.")
        return redirect("course:gestion_ajouter" if "encore" in request.POST else "course:gestion_liste")
    return render(request, "course/gestion/formulaire.html", {"form": form, "titre": "Nouveau participant", "ajout": True})


@staff_member_required
def gestion_participant(request, pk):
    participant = get_object_or_404(Participant, pk=pk)
    course = Course.get()
    form = ParticipantForm(request.POST or None, instance=participant)
    if form.is_valid():
        form.save()
        messages.success(request, "Fiche mise à jour.")
        return redirect("course:gestion_participant", pk=pk)
    return render(request, "course/gestion/participant.html", {
        "participant": participant,
        "form": form,
        "stats": classements.stats_participant(participant, course),
        "lignes": lignes(participant, course),
    })


@staff_member_required
@require_POST
def gestion_supprimer(request, pk):
    participant = get_object_or_404(Participant, pk=pk)
    participant.delete()
    messages.success(request, f"{participant} supprimé·e.")
    return redirect("course:gestion_liste")


@staff_member_required
@require_POST
def gestion_plus_un(request, pk):
    """Bouton de la liste : coche / décoche la dernière boucle partie."""
    participant = get_object_or_404(Participant, pk=pk)
    course = Course.get()
    numero = course.nb_boucles_ouvertes()
    if numero:
        supprimees, _ = Boucle.objects.filter(participant=participant, numero=numero).delete()
        if not supprimees:
            Boucle.objects.create(participant=participant, numero=numero, saisie_par=Boucle.Source.GESTION)
    # On recalcule le classement complet pour afficher le vrai rang de la ligne.
    stats = next(s for s in classements.classement(classements.toutes_les_stats(course))
                 if s.participant.pk == participant.pk)
    return render(request, "course/gestion/partials/ligne.html", {"s": stats})


@staff_member_required
@require_POST
def gestion_cloturer(request):
    course = Course.get()
    course.cloturee = not course.cloturee
    course.save(update_fields=["cloturee"])
    messages.success(request, "Course clôturée : résultats définitifs." if course.cloturee
                     else "Course rouverte : les coureurs peuvent de nouveau valider.")
    return redirect("course:gestion_liste")


@staff_member_required
def gestion_export(request):
    """Résultats en CSV (séparateur ;, UTF-8 avec BOM : s'ouvre proprement dans Excel/LibreOffice).

    Une ligne par coureur, une colonne par boucle : chrono, « x » si faite sans chrono.
    """
    course = Course.get()
    stats = classements.classement(classements.toutes_les_stats(course))
    derniere = max((s.derniere_boucle or 0 for s in stats), default=0)
    numeros = range(1, max(derniere, course.boucle_en_cours()) + 1)

    reponse = HttpResponse(content_type="text/csv; charset=utf-8")
    reponse["Content-Disposition"] = f'attachment; filename="resultats-{slugify(course.nom)}.csv"'
    reponse.write("\ufeff")
    ecrivain = csv.writer(reponse, delimiter=";")
    ecrivain.writerow(["Rang", "Pseudo", "Prénom", "Nom", "Genre", "Boucles", "Km", "D+ (m)",
                       "Plus longue série", "Meilleur chrono", *[f"B{n}" for n in numeros]])
    for s in stats:
        p = s.participant
        par_numero = {b.numero: b for b in p.boucles.all()}
        cases = [chrono(par_numero[n].chrono) or "x" if n in par_numero else "" for n in numeros]
        ecrivain.writerow([s.rang, p.pseudo, p.prenom, p.nom, p.get_genre_display(), s.nb_boucles,
                           km(s.km), s.denivele, s.serie, chrono(s.meilleur_chrono), *cases])
    return reponse


@staff_member_required
def gestion_course(request):
    form = CourseForm(request.POST or None, instance=Course.get())
    if form.is_valid():
        form.save()
        messages.success(request, "Paramètres de la course enregistrés.")
        return redirect("course:gestion_liste")
    return render(request, "course/gestion/formulaire.html", {"form": form, "titre": "Paramètres de la course"})
