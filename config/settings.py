"""Réglages du projet Backyard.

Toute la configuration propre à une machine (clé secrète, mode debug, domaine,
emplacement de la base) est lue dans un fichier `.env` à la racine du projet.
Modèle commenté : `.env.example`. Sans `.env`, on est en mode développement local.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(nom, defaut=False):
    return os.environ.get(nom, str(defaut)).strip().lower() in ("1", "true", "oui", "yes", "on")


def env_liste(nom, defaut=""):
    return [x.strip() for x in os.environ.get(nom, defaut).split(",") if x.strip()]


DEBUG = env_bool("DJANGO_DEBUG", False)
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError("DJANGO_SECRET_KEY manquante : la définir dans .env (voir .env.example).")
    SECRET_KEY = "dev-seulement-jamais-en-production"

ALLOWED_HOSTS = env_liste("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = [f"https://{h}" for h in ALLOWED_HOSTS if h not in ("localhost", "127.0.0.1")]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "course",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "course.context_processors.course",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# SQLite réglé pour des écritures concurrentes (plusieurs dizaines de téléphones
# qui valident leur boucle au même moment) :
#  - WAL : les lectures ne bloquent plus les écritures ;
#  - IMMEDIATE : une écriture réserve la base dès le début de la transaction,
#    ce qui évite les erreurs « database is locked » en cours de requête ;
#  - timeout : une écriture attend jusqu'à 20 s son tour au lieu d'échouer.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DJANGO_DB_PATH", BASE_DIR / "db.sqlite3"),
        "OPTIONS": {
            "timeout": 20,
            "transaction_mode": "IMMEDIATE",
            "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;",
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = Path(os.environ.get("DJANGO_STATIC_ROOT", BASE_DIR / "staticfiles"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Photos ---------------------------------------------------------------
# Les fichiers ne sont PAS servis publiquement : Django vérifie l'accès, puis
# (en production) délègue l'envoi à nginx via X-Accel-Redirect.
MEDIA_ROOT = Path(os.environ.get("DJANGO_MEDIA_ROOT", BASE_DIR / "media"))
PHOTOS_X_ACCEL = env_bool("DJANGO_PHOTOS_X_ACCEL", False)  # True en production, derrière nginx
PHOTOS_X_ACCEL_PREFIXE = "/_protege/"                       # location « internal » de nginx
PHOTOS_QUOTA_OCTETS = int(float(os.environ.get("DJANGO_PHOTOS_QUOTA_GO", "10")) * 1024**3)
PHOTOS_COTE_MAX = 2560        # px, côté le plus long
PHOTOS_COTE_MINIATURE = 480   # px
PHOTOS_QUALITE_JPEG = 85
PHOTOS_TAILLE_ENVOI_MAX = 25 * 1024**2  # un fichier envoyé (si le navigateur n'a pas pu réduire)
DATA_UPLOAD_MAX_MEMORY_SIZE = PHOTOS_TAILLE_ENVOI_MAX + 1024**2

# --- Production (derrière nginx en HTTPS) --------------------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")  # nginx transmet le schéma
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    # La redirection HTTP -> HTTPS est faite par nginx. Pas de HSTS ici : il est
    # géré (ou non) au niveau du domaine principal, partagé avec ton autre site.
    SILENCED_SYSTEM_CHECKS = ["security.W004", "security.W008"]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},  # -> journalctl
    "root": {"handlers": ["console"], "level": "WARNING"},
}

# --- Spécifique à l'appli -------------------------------------------------
# Chaque compte coureur ajouté sur un appareil reste connecté 24 h
# (géré compte par compte dans course/session.py). Le cookie, lui, vit un peu plus.
DUREE_CONNEXION_COUREUR_H = 24
SESSION_COOKIE_AGE = 60 * 60 * 48

LOGIN_URL = "course:gestion_connexion"
