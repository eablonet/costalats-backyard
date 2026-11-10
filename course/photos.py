"""Tout ce qui touche aux fichiers photo : traitement, quotas, zip final.

Le navigateur réduit déjà les photos à 2560 px avant l'envoi (static/course/galerie.js).
Le serveur refait quand même tout le travail, par sécurité et pour les cas où le
navigateur n'a pas pu (vieux téléphone, format HEIC sur Android…) :
  - vérifie que c'est une vraie image ;
  - redresse selon l'orientation EXIF, puis réencode en JPEG SANS aucune métadonnée
    (les photos de téléphone contiennent la position GPS) ;
  - limite à 2560 px et crée une miniature de 480 px.
"""

import io
import shutil
import zipfile
from collections import defaultdict

from django.conf import settings
from django.db.models import Sum
from django.utils.text import slugify
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import Photo

try:  # HEIC/HEIF (iPhone) : facultatif, si pillow-heif est installé
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:  # pragma: no cover
    pass

Image.MAX_IMAGE_PIXELS = 120_000_000  # refuse les « bombes » (images géantes forgées)


class PhotoRefusee(Exception):
    """Message destiné à l'utilisateur."""


# --- Quotas ------------------------------------------------------------------

def espace_utilise():
    return Photo.objects.aggregate(total=Sum("taille"))["total"] or 0


def verifier_quotas(auteur):
    """Lève PhotoRefusee si l'auteur (Participant, ou None = organisation) ne peut plus ajouter."""
    if espace_utilise() >= settings.PHOTOS_QUOTA_OCTETS:
        raise PhotoRefusee("L'espace photos du site est plein.")
    if auteur is not None and auteur.photos.count() >= auteur.limite_photos:
        raise PhotoRefusee(
            f"Limite atteinte : {auteur.limite_photos} photos maximum. "
            "Supprime une photo pour en ajouter une autre."
        )


# --- Traitement d'une image -----------------------------------------------

def _jpeg(image, cote):
    copie = image.copy()
    copie.thumbnail((cote, cote), Image.Resampling.LANCZOS)
    tampon = io.BytesIO()
    # Pas de paramètre exif= : le fichier enregistré ne contient aucune métadonnée.
    copie.save(tampon, "JPEG", quality=settings.PHOTOS_QUALITE_JPEG, optimize=True, progressive=True)
    return copie.size, tampon.getvalue()


def enregistrer(fichier, auteur=None, boucle=None):
    """Traite un fichier envoyé et crée la Photo. Lève PhotoRefusee en cas de problème."""
    if fichier.size > settings.PHOTOS_TAILLE_ENVOI_MAX:
        raise PhotoRefusee("Fichier trop lourd (25 Mo maximum).")
    verifier_quotas(auteur)
    try:
        image = Image.open(fichier)
        image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise PhotoRefusee("Ce fichier n'est pas une image lisible.")

    image = ImageOps.exif_transpose(image).convert("RGB")
    (largeur, hauteur), contenu = _jpeg(image, settings.PHOTOS_COTE_MAX)
    _, miniature = _jpeg(image, settings.PHOTOS_COTE_MINIATURE)

    photo = Photo(auteur=auteur, boucle=boucle, largeur=largeur, hauteur=hauteur,
                  taille=len(contenu) + len(miniature))
    for chemin, octets in ((photo.chemin, contenu), (photo.chemin_miniature, miniature)):
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_bytes(octets)
    photo.save()
    return photo


def supprimer_fichiers(photo):
    for chemin in (photo.chemin, photo.chemin_miniature):
        chemin.unlink(missing_ok=True)


# --- Zip final -----------------------------------------------------------------

def _morceau(texte):
    """« Jean-Pierre » -> « jean-pierre » ; « Léa  Martin » -> « lea-martin »."""
    return slugify(texte) or "x"


def _prefixe(photo):
    if photo.auteur:
        return f"{_morceau(photo.auteur.prenom)}_{_morceau(photo.auteur.nom)}"
    return f"depart_B{photo.boucle:02d}" if photo.boucle else "organisation"


def _groupe(photo):
    """Ce qui partage une même numérotation : un coureur, un départ, ou l'organisation."""
    return photo.auteur_id or (f"depart{photo.boucle}" if photo.boucle else "organisation")


def noms_dans_zip(photos):
    """[(photo, nom)] : prenom_nom_01.jpg, depart_B03_01.jpg, organisation_01.jpg.

    Numérotation par groupe, dans l'ordre d'ajout. Deux homonymes (même prénom et nom)
    reçoivent leur pseudo en plus, pour ne pas mélanger leurs photos.
    """
    photos = sorted(photos, key=lambda p: p.ajoutee_le)
    groupes_par_prefixe = defaultdict(set)
    for p in photos:
        groupes_par_prefixe[_prefixe(p)].add(_groupe(p))

    numeros, noms = defaultdict(int), []
    for p in photos:
        prefixe = _prefixe(p)
        if len(groupes_par_prefixe[prefixe]) > 1:
            prefixe += f"_{_morceau(p.auteur.pseudo)}"
        numeros[_groupe(p)] += 1
        noms.append((p, f"{prefixe}_{numeros[_groupe(p)]:02d}.jpg"))
    return noms


DOSSIER_EXPORT = "exports"
NOM_ZIP = "photos-backyard.zip"


def chemin_zip():
    return settings.MEDIA_ROOT / DOSSIER_EXPORT / NOM_ZIP


def chemin_zip_en_cours():
    return chemin_zip().with_suffix(".zip.part")


def etat_zip():
    """'en_cours', 'pret' ou None."""
    if chemin_zip_en_cours().exists():
        return "en_cours"
    if chemin_zip().exists():
        return "pret"
    return None


def verifier_espace_disque():
    """Le zip occupe autant que les photos (le JPEG ne se compresse pas) : on vérifie avant."""
    libre = shutil.disk_usage(settings.MEDIA_ROOT).free
    besoin = espace_utilise() + 200 * 1024**2
    if libre < besoin:
        raise PhotoRefusee(
            f"Pas assez d'espace disque pour le zip : {libre / 1024**3:.1f} Go libres, "
            f"{besoin / 1024**3:.1f} Go nécessaires."
        )


def creer_zip():
    """Écrit le zip dans un fichier .part, puis le renomme : jamais de zip à moitié fait."""
    partiel, final = chemin_zip_en_cours(), chemin_zip()
    partiel.parent.mkdir(parents=True, exist_ok=True)
    photos = Photo.objects.select_related("auteur")
    try:
        with zipfile.ZipFile(partiel, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
            for photo, nom in noms_dans_zip(photos):
                if photo.chemin.exists():
                    archive.write(photo.chemin, nom)
        partiel.replace(final)
    finally:
        partiel.unlink(missing_ok=True)
    return final
