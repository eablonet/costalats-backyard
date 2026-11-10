"""Galerie photo — PRIVÉE : coureurs connectés sur l'appareil et organisateurs uniquement."""

import subprocess
import sys
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.db.models import Count
from django.http import FileResponse, Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .. import photos as service
from .. import session
from ..models import Course, Participant, Photo
from .commun import est_htmx

__all__ = [
    "galerie", "galerie_envoyer", "galerie_supprimer", "photo_fichier",
    "gestion_photos", "gestion_zip_lancer", "gestion_zip_telecharger",
]

NB_CARROUSEL = 30


def peut_voir_galerie(request):
    return request.user.is_staff or bool(session.ids_connectes(request))


def galerie_requise(vue):
    @wraps(vue)
    def enveloppe(request, *args, **kwargs):
        if not peut_voir_galerie(request):
            if est_htmx(request) or request.method == "POST":
                return HttpResponseForbidden("Connexion requise.")
            messages.info(request, "La galerie est réservée aux coureurs : connecte-toi avec ton pseudo.")
            return redirect("course:connexion")
        return vue(request, *args, **kwargs)
    return enveloppe


def staff_requis(vue):
    @wraps(vue)
    def enveloppe(request, *args, **kwargs):
        if not request.user.is_staff:
            return redirect("course:gestion_connexion")
        return vue(request, *args, **kwargs)
    return enveloppe


def photos_carrousel(nombre=NB_CARROUSEL):
    return list(Photo.objects.select_related("auteur")[:nombre])


def peut_supprimer(request, photo):
    return request.user.is_staff or (photo.auteur_id and photo.auteur_id in session.ids_connectes(request))


# --- Page Galerie ------------------------------------------------------------

def _filtrer(request):
    """Filtres de la grille : tri (recentes / anciennes) et auteur (orga, departs, ou pk)."""
    tri = "anciennes" if request.GET.get("tri") == "anciennes" else "recentes"
    auteur = request.GET.get("auteur", "")
    photos = Photo.objects.select_related("auteur")
    if auteur == "orga":
        photos = photos.filter(auteur__isnull=True, boucle__isnull=True)
    elif auteur == "departs":
        photos = photos.filter(auteur__isnull=True, boucle__isnull=False)
    elif auteur.isdigit():
        photos = photos.filter(auteur_id=int(auteur))
    else:
        auteur = ""
    photos = photos.order_by("ajoutee_le" if tri == "anciennes" else "-ajoutee_le")
    return {"photos": photos, "tri": tri, "auteur": auteur}


def _identites_envoi(request):
    """Au nom de qui cet appareil peut publier : [(valeur, libellé, photos restantes ou None)]."""
    identites = []
    if request.user.is_staff:
        identites.append(("orga", "Organisation", None))
    for p in session.participants_connectes(request):
        identites.append((str(p.pk), p.pseudo, max(p.limite_photos - p.photos.count(), 0)))
    return identites


@galerie_requise
def galerie(request):
    ctx = _filtrer(request)
    if est_htmx(request):
        return render(request, "course/partials/galerie_grille.html", _avec_droits(request, ctx))
    ctx.update({
        "carrousel": photos_carrousel(),
        "auteurs": Participant.objects.annotate(nb=Count("photos")).filter(nb__gt=0).order_by("pseudo"),
        "nb_orga": Photo.objects.filter(auteur__isnull=True, boucle__isnull=True).count(),
        "nb_departs": Photo.objects.filter(auteur__isnull=True, boucle__isnull=False).count(),
        "identites": _identites_envoi(request),
        "boucles": range(1, Course.get().nb_boucles_max + 1),
        "cote_max": settings.PHOTOS_COTE_MAX,
    })
    return render(request, "course/galerie.html", _avec_droits(request, ctx))


def _avec_droits(request, ctx):
    """Marque chaque photo supprimable ou non (les templates ne peuvent pas appeler de fonction)."""
    photos = list(ctx["photos"])
    for photo in photos:
        photo.supprimable = peut_supprimer(request, photo)
    ctx["photos"] = photos
    return ctx


@require_POST
@galerie_requise
def galerie_envoyer(request):
    """Reçoit UNE photo (le navigateur les envoie une par une). Répond en JSON."""
    qui = request.POST.get("auteur", "")
    boucle = None
    if qui == "orga":
        if not request.user.is_staff:
            return JsonResponse({"ok": False, "message": "Réservé aux organisateurs."}, status=403)
        auteur = None
        if request.POST.get("boucle", "").isdigit():
            boucle = int(request.POST["boucle"])
    else:
        if not qui.isdigit() or int(qui) not in session.ids_connectes(request):
            return JsonResponse({"ok": False, "message": "Compte non connecté sur cet appareil."}, status=403)
        auteur = get_object_or_404(Participant, pk=int(qui))

    fichier = request.FILES.get("photo")
    if fichier is None:
        return JsonResponse({"ok": False, "message": "Aucun fichier reçu."}, status=400)
    try:
        photo = service.enregistrer(fichier, auteur=auteur, boucle=boucle)
    except service.PhotoRefusee as e:
        return JsonResponse({"ok": False, "message": str(e)}, status=400)

    restant = None if auteur is None else max(auteur.limite_photos - auteur.photos.count(), 0)
    return JsonResponse({"ok": True, "uuid": str(photo.uuid), "restant": restant})


@require_POST
@galerie_requise
def galerie_supprimer(request, uuid):
    photo = get_object_or_404(Photo, uuid=uuid)
    if not peut_supprimer(request, photo):
        return HttpResponseForbidden("Tu ne peux supprimer que tes propres photos.")
    photo.delete()  # le signal post_delete efface les fichiers
    reponse = HttpResponse("")  # HTMX remplace la vignette par… rien
    reponse["HX-Trigger"] = "photos-modifiees"
    return reponse


def _servir(chemin, en_piece_jointe=None):
    """Envoie un fichier de MEDIA_ROOT après contrôle d'accès.

    En production, nginx fait l'envoi (X-Accel-Redirect vers une location « internal ») :
    Django ne fait que dire oui. En développement, Django envoie le fichier lui-même.
    """
    if not chemin.exists():
        raise Http404
    if settings.PHOTOS_X_ACCEL:
        relatif = chemin.relative_to(settings.MEDIA_ROOT).as_posix()
        reponse = HttpResponse()
        reponse["X-Accel-Redirect"] = settings.PHOTOS_X_ACCEL_PREFIXE + relatif
        reponse["Content-Type"] = "application/zip" if en_piece_jointe else "image/jpeg"
    else:
        reponse = FileResponse(open(chemin, "rb"))
    if en_piece_jointe:
        reponse["Content-Disposition"] = f'attachment; filename="{en_piece_jointe}"'
    reponse["Cache-Control"] = "private, max-age=86400"
    reponse["X-Robots-Tag"] = "noindex"
    return reponse


@galerie_requise
def photo_fichier(request, uuid, format):
    photo = get_object_or_404(Photo, uuid=uuid)
    return _servir(photo.chemin_miniature if format == "mini" else photo.chemin)


# --- Gestion : jauge et zip -------------------------------------------------

@staff_requis
def gestion_photos(request):
    """Bloc « Photos » de la gestion (rechargé par HTMX pendant la création du zip)."""
    utilise = service.espace_utilise()
    quota = settings.PHOTOS_QUOTA_OCTETS
    return render(request, "course/gestion/partials/photos.html", {
        "nb_photos": Photo.objects.count(),
        "utilise": utilise,
        "quota": quota,
        "pourcentage": round(100 * utilise / quota) if quota else 0,
        "etat_zip": service.etat_zip(),
        "taille_zip": service.chemin_zip().stat().st_size if service.etat_zip() == "pret" else 0,
    })


@require_POST
@staff_requis
def gestion_zip_lancer(request):
    """Lance `manage.py zip_photos` en tâche de fond : la création peut durer plusieurs
    minutes, bien plus que les 30 s qu'une requête web a le droit de prendre."""
    if service.etat_zip() != "en_cours":
        try:
            service.verifier_espace_disque()
        except service.PhotoRefusee as e:
            messages.error(request, str(e))
            return redirect("course:gestion_liste")
        service.chemin_zip_en_cours().parent.mkdir(parents=True, exist_ok=True)
        service.chemin_zip_en_cours().touch()  # l'état « en cours » est visible tout de suite
        subprocess.Popen(
            [sys.executable, str(settings.BASE_DIR / "manage.py"), "zip_photos"],
            cwd=settings.BASE_DIR, start_new_session=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    if est_htmx(request):
        return gestion_photos(request)
    return redirect("course:gestion_liste")


@staff_requis
def gestion_zip_telecharger(request):
    if service.etat_zip() != "pret":
        raise Http404
    return _servir(service.chemin_zip(), en_piece_jointe=service.NOM_ZIP)
