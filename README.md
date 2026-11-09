# Backyard — résultats live d'une course format backyard

Une seule course, un départ toutes les heures. Les coureurs déclarent eux-mêmes leurs
boucles (système de confiance) et peuvent ajouter leur chrono. La gestion peut tout corriger.

## Démarrer

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser        # compte de gestion
cp .env.example .env                    # puis mettre DJANGO_DEBUG=1 pour le développement
python manage.py demo                   # facultatif : 18 coureurs fictifs, course en cours
python manage.py runserver
```

- `/` page Résultats : chiffres clés et graphique des coureurs par boucle en haut, puis les classements filtrables par critère (Boucles / Série / Meilleur chrono) et par catégorie (Tous / Femmes / Hommes / Enfants), rafraîchis toutes les 30 s
- `/ecran/` mode grand écran pour la projection : chiffres clés, graphique, puis trois colonnes (Femmes / Hommes / Enfants). Le classement affiché alterne Boucles → Série → Meilleur chrono toutes les `ecran_bascule_minutes` (3 par défaut, réglable dans Paramètres ou dans l'admin, 0 = pas de bascule) ; les colonnes trop longues défilent seules
- recherche de coureur sur la page Résultats (le rang affiché reste le rang réel)
- `/inscription/`, `/connexion/` : compte coureur, pseudo seul pour se reconnecter
- `/moi/` carnet du coureur actif ; flèches ‹ › pour changer de compte sur l'appareil
- `/gestion/` liste + « +1 » réversible, fiches, paramètres, clôture de la course, export CSV (réservé au staff, connexion par `/gestion/connexion/` ou par le lien « Espace organisateur » en pied de page)
- `/admin/` filet de sécurité, et journal des boucles (qui, quand, saisi par qui)

Tests : `python manage.py test course`

## Architecture

```
config/                 réglages, urls racine
course/
  models.py             Course (singleton pk=1), Participant, Boucle
  classements.py        toutes les stats et tops, calculés en Python
  session.py            comptes coureurs multiples par appareil, expiration 24 h par compte
  forms.py              formulaires + parse_chrono ("52", "52:30", "1:10:00", "1h10")
  context_processors.py course et coureur actif dans tous les templates
  views/                public.py, participant.py, gestion.py, commun.py
  templates/course/     pages + partials/ (fragments HTMX)
  static/course/        style.css, htmx.min.js (inclus localement)
  management/commands/demo.py
```

### Règles métier

| Règle | Où |
|---|---|
| Pas de table « boucle de la course » : départ(n) = premier départ + (n−1) h | `Course.depart` |
| Un coureur peut cocher une boucle dès `tolerance_minutes` (5 par défaut) avant son départ, jamais une boucle future | `Course.boucle_ouverte`, `views/participant._verifier` |
| La gestion (staff) peut cocher ou décocher n'importe quelle boucle | idem |
| Tout chrono est accepté, même incohérent (> 1 h) | `forms.parse_chrono` |
| Saisir un chrono coche la boucle ; décocher supprime aussi le chrono | `saisir_chrono`, `basculer_boucle` |
| Pseudo unique, insensible à la casse | contrainte `Lower("pseudo")` + `ParticipantForm` |
| Trois classements (boucles, plus longue série, meilleur chrono) ; égalité = même rang, sans second critère | `classements.CRITERES`, `classements.classement` |
| Course clôturée : plus aucune modification côté coureur (la gestion garde la main) | `Course.cloturee`, `_verifier` |
| Coureur connecté sur un autre appareil : 403, pas d'usurpation silencieuse (mais n'importe qui peut taper un pseudo — choix assumé) | `commun.peut_modifier` |

### HTMX

- Cocher, décocher ou saisir un chrono renvoie la ligne `<li>` re-rendue, plus l'événement
  `boucles-modifiees` qui recharge le résumé du coureur.
- À zéro, le compte à rebours (`static/course/horloge.js`) émet l'événement `depart` : horloge, carnet, tableau de gestion et écran se rechargent seuls, sans recharger la page. Le carnet ne se recharge pas pendant la saisie d'un chrono.
- Le classement se recharge lui-même (`hx-trigger="every 30s"`) en gardant le filtre de genre.
- Le jeton CSRF est passé par `hx-headers` sur `<body>`.

## Configuration et mise en production

La configuration propre à chaque machine est dans un fichier `.env` (modèle : `.env.example`).
En local, `DJANGO_DEBUG=1` suffit. La procédure complète de déploiement sur le VPS
(DNS, systemd, nginx, HTTPS, sauvegardes, mises à jour, check-list du jour J) est dans
**`deploy/DEPLOIEMENT.md`**.
