import re
from datetime import timedelta

from django import forms

from .models import Course, Participant


def parse_chrono(texte):
    """'52' -> 52 min ; '52:30' -> 52 min 30 ; '1:10:00' ou '1h10' -> 1 h 10.

    Aucune vérification de cohérence : tout chrono est accepté (choix assumé).
    """
    texte = texte.strip().lower().replace(" ", "")
    if m := re.fullmatch(r"(\d+)h(\d{1,2})?", texte):
        return timedelta(hours=int(m[1]), minutes=int(m[2] or 0))
    parties = texte.split(":")
    if not texte or not all(p.isdigit() for p in parties) or len(parties) > 3:
        raise forms.ValidationError("Format attendu : 52, 52:30, 1:10:00 ou 1h10.")
    nombres = [int(p) for p in parties]
    if len(nombres) == 1:
        return timedelta(minutes=nombres[0])
    if len(nombres) == 2:
        return timedelta(minutes=nombres[0], seconds=nombres[1])
    return timedelta(hours=nombres[0], minutes=nombres[1], seconds=nombres[2])


class ParticipantForm(forms.ModelForm):
    class Meta:
        model = Participant
        fields = ["prenom", "nom", "pseudo", "genre"]
        widgets = {"genre": forms.RadioSelect}

    def clean_pseudo(self):
        pseudo = self.cleaned_data["pseudo"].strip()
        doublons = Participant.objects.filter(pseudo__iexact=pseudo).exclude(pk=self.instance.pk)
        if doublons.exists():
            raise forms.ValidationError("Ce pseudo est déjà pris.")
        return pseudo


class GestionParticipantForm(ParticipantForm):
    """Fiche vue par l'organisation : en plus, la limite de photos (30 par défaut, 150 max)."""

    class Meta(ParticipantForm.Meta):
        fields = ParticipantForm.Meta.fields + ["limite_photos"]


class ConnexionForm(forms.Form):
    pseudo = forms.CharField(max_length=30)

    def clean_pseudo(self):
        pseudo = self.cleaned_data["pseudo"].strip()
        try:
            self.participant = Participant.objects.get(pseudo__iexact=pseudo)
        except Participant.DoesNotExist:
            raise forms.ValidationError("Pseudo inconnu. Crée ton compte d'abord !")
        return pseudo


class ChronoForm(forms.Form):
    chrono = forms.CharField(max_length=10, required=False)

    def clean_chrono(self):
        texte = self.cleaned_data["chrono"]
        return parse_chrono(texte) if texte.strip() else None


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ["nom", "premier_depart", "nb_boucles_max", "distance_km", "denivele_m", "tolerance_minutes", "ecran_bascule_minutes"]
        widgets = {"premier_depart": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M")}
