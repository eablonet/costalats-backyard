from datetime import timedelta

from django import template

register = template.Library()


@register.filter
def chrono(duree):
    """timedelta -> '52:30' ou '1:10:05'. Vide si None."""
    if not isinstance(duree, timedelta):
        return ""
    total = int(duree.total_seconds())
    h, reste = divmod(total, 3600)
    m, s = divmod(reste, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


@register.filter
def km(valeur):
    """Nombre de km avec 1 décimale, virgule à la française."""
    return f"{valeur:.1f}".replace(".", ",")
