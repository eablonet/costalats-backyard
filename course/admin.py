from django.contrib import admin

from .models import Boucle, Course, Participant


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ["nom", "premier_depart", "nb_boucles_max", "distance_km", "denivele_m", "ecran_bascule_minutes", "cloturee"]

    def has_add_permission(self, request):
        return not Course.objects.exists()


class BoucleInline(admin.TabularInline):
    model = Boucle
    extra = 0
    fields = ["numero", "chrono", "saisie_par", "declare_le", "modifie_le"]
    readonly_fields = ["declare_le", "modifie_le"]


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ["pseudo", "prenom", "nom", "genre", "cree_le"]
    list_filter = ["genre"]
    search_fields = ["pseudo", "prenom", "nom"]
    inlines = [BoucleInline]


@admin.register(Boucle)
class BoucleAdmin(admin.ModelAdmin):
    """Sert aussi de journal : qui a déclaré quoi, et quand."""

    list_display = ["participant", "numero", "chrono", "saisie_par", "declare_le", "modifie_le"]
    list_filter = ["saisie_par", "numero"]
    search_fields = ["participant__pseudo"]
