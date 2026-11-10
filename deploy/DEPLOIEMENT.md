# Déploiement sur le VPS OVH (Debian, nginx + gunicorn + systemd)

Adresse : **https://costalats-backyard.emeryk-ablonet.fr**
Dossier sur le VPS : **/srv/costalats-backyard** (code + `.venv` + `.env` + base + sauvegardes)

> ⚠️ Pas de tiret bas dans un nom de domaine : `costalats_backyard` serait refusé par
> Let's Encrypt et par Django. On utilise `costalats-backyard`.

Partout ci-dessous, remplacer `UTILISATEUR` par ton compte sur le VPS.

---

## 1. DNS (espace client OVH)

Zone DNS de `emeryk-ablonet.fr` → ajouter une entrée :

| Type  | Sous-domaine         | Cible                  |
|-------|----------------------|------------------------|
| CNAME | `costalats-backyard` | `emeryk-ablonet.fr.`   |

(ou un enregistrement A vers l'IP du VPS, comme ton domaine principal). Vérifier
la propagation, de quelques minutes à quelques heures :

```bash
dig +short costalats-backyard.emeryk-ablonet.fr
```

## 2. Dépôt Git (sur ta machine)

```bash
cd backyard
git init && git add . && git commit -m "Backyard : première version"
git remote add origin git@github.com:<toi>/costalats-backyard.git   # dépôt privé
git push -u origin main
```

Le `.env`, la base et les sauvegardes sont exclus par le `.gitignore`.

## 3. Installation sur le VPS

```bash
sudo mkdir -p /srv/costalats-backyard
sudo chown UTILISATEUR:www-data /srv/costalats-backyard
git clone git@github.com:<toi>/costalats-backyard.git /srv/costalats-backyard
cd /srv/costalats-backyard

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(50))"   # → coller dans DJANGO_SECRET_KEY
nano .env
chmod 600 .env

.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser        # ton compte organisateur
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py check --deploy
chmod +x deploy/*.sh
```

## 4. Service gunicorn (systemd)

```bash
sudo cp deploy/costalats-backyard.service /etc/systemd/system/
sudo nano /etc/systemd/system/costalats-backyard.service     # UTILISATEUR
sudo systemctl daemon-reload
sudo systemctl enable --now costalats-backyard
systemctl status costalats-backyard                          # doit être « active (running) »
```

## 5. nginx + HTTPS

```bash
sudo cp deploy/nginx-costalats-backyard.conf /etc/nginx/sites-available/costalats-backyard
sudo ln -s /etc/nginx/sites-available/costalats-backyard /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

**Le HTTPS ne s'applique pas tout seul au sous-domaine.** Ton certificat actuel ne
couvre très probablement que `emeryk-ablonet.fr` (et `www`). Pour vérifier :

```bash
sudo certbot certificates      # regarder la ligne « Domains: »
```

Sauf si tu y vois `*.emeryk-ablonet.fr` (certificat wildcard), demander un
certificat pour le sous-domaine. Certbot modifie lui-même le bloc nginx (HTTPS +
redirection), et le renouvellement automatique déjà en place le prendra en charge :

```bash
sudo certbot --nginx -d costalats-backyard.emeryk-ablonet.fr
```

Ouvrir https://costalats-backyard.emeryk-ablonet.fr : la page Résultats s'affiche.

## 6. Sauvegardes automatiques

```bash
crontab -e
# ajouter :
*/15 * * * * /srv/costalats-backyard/deploy/sauvegarde.sh
```

Les copies sont dans `/srv/costalats-backyard/sauvegardes/` et gardées 7 jours.
Après la course, en rapatrier une sur ta machine :

```bash
scp UTILISATEUR@vps:/srv/costalats-backyard/sauvegardes/db-AAAAMMJJ-HHMM.sqlite3.gz .
```

**Restaurer** une sauvegarde :

```bash
sudo systemctl stop costalats-backyard
gunzip -c sauvegardes/db-AAAAMMJJ-HHMM.sqlite3.gz > db.sqlite3
rm -f db.sqlite3-wal db.sqlite3-shm
sudo systemctl start costalats-backyard
```

## 7. Galerie photo

Les photos sont dans `/srv/costalats-backyard/media/` (exclu de Git), jamais servies
directement : Django vérifie que le visiteur est un coureur connecté ou un organisateur,
puis nginx envoie le fichier (`location /_protege/`).

À la première mise en place de la galerie :

1. ajouter `DJANGO_PHOTOS_X_ACCEL=1` dans le `.env` (voir `.env.example`) ;
2. mettre à jour le bloc nginx (`client_max_body_size 30m` et la `location /_protege/`) :
   reporter ces lignes dans `/etc/nginx/sites-available/costalats-backyard` **sans écraser**
   les lignes ajoutées par certbot (`listen 443`, `ssl_certificate`…), puis
   `sudo nginx -t && sudo systemctl reload nginx` ;
3. déployer (`deploy-backyard.sh`) : la migration ajoute la table des photos.

Espace disque : `df -h /srv`. Le zip final occupe autant que les photos (le JPEG ne se
compresse pas) : la gestion refuse de le créer s'il n'y a pas la place. On peut aussi le
créer à la main : `.venv/bin/python manage.py zip_photos`
→ `media/exports/photos-backyard.zip`.

Les sauvegardes automatiques ne copient que la base. Pour garder les photos, une copie
vers ta machine après la course suffit :

```bash
rsync -av UTILISATEUR@vps:/srv/costalats-backyard/media/photos/ ./photos-backyard/
```

## 8. Mises à jour

Sur ta machine : `git push`. Sur le VPS :

```bash
/srv/costalats-backyard/deploy/deploy-backyard.sh
```

Le script fait : `git pull`, sauvegarde, `pip install`, `migrate`, `collectstatic`,
`check --deploy`, redémarrage, puis vérifie que le site répond 200. Il peut aussi
être appelé depuis ton script `deploy-sitepro` si tu préfères une seule commande.

Un redémarrage coupe le site environ une seconde. Pendant la course, éviter de
déployer sauf urgence.

---

## Répétition

```bash
.venv/bin/python manage.py demo --force    # coureurs fictifs (refusé sans --force en production)
```

Pour repartir de zéro après la répétition : **Gestion → fiche → Supprimer**, ou en
une fois :

```bash
.venv/bin/python manage.py shell -c "from course.models import Participant; Participant.objects.all().delete()"
```

## Check-list du jour J

- [ ] Gestion → Paramètres : nom, **heure du premier départ**, nombre de boucles, km, D+, bascule de l'écran
- [ ] Un téléphone : inscription, validation de B1 (dans les 5 min avant le départ), chrono
- [ ] L'écran de projection ouvert sur `/ecran/`, plein écran (F11)
- [ ] Logs en direct si besoin : `sudo journalctl -u costalats-backyard -f`
- [ ] Un coureur test ajoute une photo depuis son téléphone (Galerie → Ajouter des photos)
- [ ] Fin de course : Gestion → **Clôturer la course**, puis **Export CSV**
- [ ] Gestion → **Préparer le zip de toutes les photos**, puis le télécharger
