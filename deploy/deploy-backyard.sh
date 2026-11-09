#!/usr/bin/env bash
# Met en ligne la dernière version poussée sur Git.
# Usage (sur le VPS) : /srv/costalats-backyard/deploy/deploy-backyard.sh
set -euo pipefail

APP_DIR=/srv/costalats-backyard
SERVICE=costalats-backyard
URL=https://costalats-backyard.emeryk-ablonet.fr/

cd "$APP_DIR"
PY="$APP_DIR/.venv/bin/python"

echo "→ Récupération du code"
git pull --ff-only

echo "→ Sauvegarde de la base avant migration"
"$APP_DIR/deploy/sauvegarde.sh"

echo "→ Dépendances"
"$APP_DIR/.venv/bin/pip" install --quiet -r requirements.txt

echo "→ Migrations et fichiers statiques"
"$PY" manage.py migrate --noinput
"$PY" manage.py collectstatic --noinput --verbosity 0

echo "→ Vérifications de production"
"$PY" manage.py check --deploy --fail-level WARNING

echo "→ Redémarrage"
sudo systemctl restart "$SERVICE"
sleep 2
systemctl is-active --quiet "$SERVICE" || { echo "✗ Le service ne tourne pas :"; sudo journalctl -u "$SERVICE" -n 30 --no-pager; exit 1; }

code=$(curl -s -o /dev/null -w '%{http_code}' "$URL" || true)
if [ "$code" = "200" ]; then echo "✓ En ligne : $URL"; else echo "⚠ $URL répond $code"; exit 1; fi
