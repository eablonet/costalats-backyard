#!/usr/bin/env bash
# Copie cohérente de la base SQLite (même pendant que l'appli écrit), compressée.
# Garde 7 jours d'historique. Lancé par cron toutes les 15 min et avant chaque déploiement.
#   crontab -e  →  */15 * * * * /srv/costalats-backyard/deploy/sauvegarde.sh
set -euo pipefail

APP_DIR=/srv/costalats-backyard
BASE="$APP_DIR/db.sqlite3"
DOSSIER="$APP_DIR/sauvegardes"

[ -f "$BASE" ] || exit 0
mkdir -p "$DOSSIER"
CIBLE="$DOSSIER/db-$(date +%Y%m%d-%H%M).sqlite3"

# L'API de sauvegarde de SQLite (via Python, pas besoin du paquet sqlite3) gère le mode WAL.
"$APP_DIR/.venv/bin/python" -c "
import sqlite3, sys
src = sqlite3.connect(sys.argv[1]); dst = sqlite3.connect(sys.argv[2])
src.backup(dst); dst.close(); src.close()
" "$BASE" "$CIBLE"
gzip -f "$CIBLE"

find "$DOSSIER" -name 'db-*.sqlite3.gz' -mtime +7 -delete
