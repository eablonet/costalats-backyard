from . import session
from .models import Course


def course(request):
    """Rend la course et le compte coureur actif disponibles dans tous les templates."""
    return {
        "course": Course.get(),
        "coureur_actif": session.actif(request),
        "nb_comptes": len(session.ids_connectes(request)),
        "galerie_visible": request.user.is_staff or bool(session.ids_connectes(request)),
    }
