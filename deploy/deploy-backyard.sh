#!/usr/bin/env bash
# Met en ligne la dernière version poussée sur Git.
#
# Usage (sur le VPS, depuis ton compte d'administration) :
#     /srv/costalats-backyard/deploy/deploy-backyard.sh
#
# Toutes les commandes de l'appli (git, pip, migrate…) s'exécutent sous le compte
# PROPRIÉTAIRE du dossier (celui qui fait tourner le service, ex. « sitepro ») :
# git accepte alors le dépôt et les fichiers créés gardent le bon propriétaire.
# Seul le redémarrage du service passe par sudo (mot de passe demandé si besoin).
set -euo pipefail

APP_DIR=/srv/costalats-backyard
SERVICE=costalats-backyard
URL=https://costalats-backyard.emeryk-ablonet.fr/

PROPRIO=$(stat -c %U "$APP_DIR")
PY="$APP_DIR/.venv/bin/python"

# Exécute une commande sous le compte propriétaire (directement si on l'est déjà).
en_proprio() {
    if [ "$(id -un)" = "$PROPRIO" ]; then "$@"; else sudo -u "$PROPRIO" -H "$@"; fi
}

cd "$APP_DIR"
echo "→ Compte de l'appli : $PROPRIO"

echo "→ Récupération du code"
en_proprio git -C "$APP_DIR" pull --ff-only

echo "→ Sauvegarde de la base avant migration"
en_proprio "$APP_DIR/deploy/sauvegarde.sh"

echo "→ Dépendances"
en_proprio "$APP_DIR/.venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

echo "→ Migrations et fichiers statiques"
en_proprio "$PY" "$APP_DIR/manage.py" migrate --noinput
en_proprio "$PY" "$APP_DIR/manage.py" collectstatic --noinput --verbosity 0

echo "→ Vérifications de production"
en_proprio "$PY" "$APP_DIR/manage.py" check --deploy --fail-level WARNING

echo "→ Redémarrage"
sudo systemctl restart "$SERVICE"
sleep 2
systemctl is-active --quiet "$SERVICE" || { echo "✗ Le service ne tourne pas :"; sudo journalctl -u "$SERVICE" -n 30 --no-pager; exit 1; }

code=$(curl -s -o /dev/null -w '%{http_code}' "$URL" || true)
if [ "$code" = "200" ]; then echo "✓ En ligne : $URL"; else echo "⚠ $URL répond $code"; exit 1; fi
