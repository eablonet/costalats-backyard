from django.urls import path

from . import views

app_name = "course"

urlpatterns = [
    # Public
    path("", views.accueil, name="accueil"),
    path("bilan/", views.bilan, name="bilan"),  # redirige vers l'accueil
    path("resume-course/", views.resume_course, name="resume_course"),
    path("coureur/<str:pseudo>/", views.coureur, name="coureur"),
    path("ecran/", views.ecran, name="ecran"),
    path("horloge/", views.horloge, name="horloge"),
    # Coureur
    path("inscription/", views.inscription, name="inscription"),
    path("connexion/", views.connexion, name="connexion"),
    path("moi/", views.moi, name="moi"),
    path("moi/<str:sens>/", views.basculer_compte, name="basculer_compte"),
    path("deconnexion/<int:pk>/", views.deconnexion, name="deconnexion"),
    # Actions HTMX sur une boucle (coureur connecté ou gestion)
    path("p/<int:pk>/boucle/<int:numero>/basculer/", views.basculer_boucle, name="basculer_boucle"),
    path("p/<int:pk>/boucle/<int:numero>/chrono/", views.saisir_chrono, name="saisir_chrono"),
    path("p/<int:pk>/resume/", views.resume, name="resume"),
    path("p/<int:pk>/carnet/", views.carnet, name="carnet"),
    # Gestion
    path("gestion/", views.gestion_liste, name="gestion_liste"),
    path("gestion/connexion/", views.GestionConnexion.as_view(), name="gestion_connexion"),
    path("gestion/deconnexion/", views.GestionDeconnexion.as_view(), name="gestion_deconnexion"),
    path("gestion/ajouter/", views.gestion_ajouter, name="gestion_ajouter"),
    path("gestion/course/", views.gestion_course, name="gestion_course"),
    path("gestion/cloturer/", views.gestion_cloturer, name="gestion_cloturer"),
    path("gestion/export.csv", views.gestion_export, name="gestion_export"),
    path("gestion/p/<int:pk>/", views.gestion_participant, name="gestion_participant"),
    path("gestion/p/<int:pk>/supprimer/", views.gestion_supprimer, name="gestion_supprimer"),
    path("gestion/p/<int:pk>/plus-un/", views.gestion_plus_un, name="gestion_plus_un"),
]
