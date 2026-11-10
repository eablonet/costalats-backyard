// Galerie : carrousels, visionneuse plein écran, envoi des photos.

// --- Carrousels ([data-carrousel]) -------------------------------------------
// Une diapo visible (.actif), on passe à la suivante toutes les 5 s ; flèches ‹ ›.
const DELAI_CARROUSEL = 5000;

function avancerCarrousel(carrousel, sens) {
  const diapos = [...carrousel.querySelectorAll(".carrousel__diapo")];
  if (diapos.length < 2) return;
  const i = diapos.findIndex(d => d.classList.contains("actif"));
  diapos[i].classList.remove("actif");
  diapos[(i + sens + diapos.length) % diapos.length].classList.add("actif");
}

setInterval(() => {
  document.querySelectorAll("[data-carrousel]").forEach(c => {
    if (!c.matches(":hover")) avancerCarrousel(c, 1);  // pause au survol
  });
}, DELAI_CARROUSEL);

// --- Visionneuse (<dialog id="visionneuse">) -------------------------------
// Clic sur une image [data-grande] : affichage plein écran, flèches pour naviguer
// parmi les images de la même zone (carrousel ou grille).
let groupeVisionneuse = [], indexVisionneuse = 0;

function afficherDansVisionneuse(i) {
  const v = document.getElementById("visionneuse");
  indexVisionneuse = (i + groupeVisionneuse.length) % groupeVisionneuse.length;
  const img = groupeVisionneuse[indexVisionneuse];
  v.querySelector("img").src = img.dataset.grande;
  v.querySelector(".visionneuse__legende").textContent = img.dataset.legende || "";
}

document.addEventListener("click", e => {
  const fleche = e.target.closest("[data-sens]");
  if (fleche) return avancerCarrousel(fleche.closest("[data-carrousel]"), +fleche.dataset.sens);

  const v = document.getElementById("visionneuse");
  if (!v) return;
  const nav = e.target.closest("[data-visionneuse]");
  if (nav) return afficherDansVisionneuse(indexVisionneuse + +nav.dataset.visionneuse);
  if (e.target.closest(".visionneuse__fermer") || e.target === v) return v.close();

  const img = e.target.closest("img[data-grande]");
  if (img) {
    const zone = img.closest("[data-carrousel], .grille-photos");
    groupeVisionneuse = [...zone.querySelectorAll("img[data-grande]")];
    afficherDansVisionneuse(groupeVisionneuse.indexOf(img));
    v.showModal();
  }
});

document.addEventListener("keydown", e => {
  const v = document.getElementById("visionneuse");
  if (v?.open && (e.key === "ArrowLeft" || e.key === "ArrowRight")) {
    afficherDansVisionneuse(indexVisionneuse + (e.key === "ArrowRight" ? 1 : -1));
  }
});

// --- Filtre « Plus récentes / Plus anciennes » ------------------------------
document.addEventListener("click", e => {
  const onglet = e.target.closest("[data-tri]");
  if (!onglet) return;
  document.getElementById("filtre-tri").value = onglet.dataset.tri;
  document.querySelectorAll("[data-tri]").forEach(o => o.classList.toggle("actif", o === onglet));
});

// --- Envoi des photos -----------------------------------------------------------
// 1. Le navigateur réduit chaque photo à 2560 px (JPEG 85 %) : ~800 Ko au lieu de ~5 Mo,
//    beaucoup plus rapide en 4G et presque aucun travail pour le serveur.
// 2. Les photos partent UNE PAR UNE : 300 photos font la queue au lieu d'arriver ensemble.
// Si le navigateur ne sait pas lire le fichier (ex. HEIC sur Android), on envoie
// l'original : le serveur sait le convertir.

async function reduire(fichier, cote) {
  try {
    const image = await createImageBitmap(fichier, { imageOrientation: "from-image" });
    const echelle = Math.min(1, cote / Math.max(image.width, image.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(image.width * echelle);
    canvas.height = Math.round(image.height * echelle);
    canvas.getContext("2d").drawImage(image, 0, 0, canvas.width, canvas.height);
    image.close();
    const blob = await new Promise(ok => canvas.toBlob(ok, "image/jpeg", 0.85));
    return blob || fichier;
  } catch {
    return fichier;
  }
}

function jetonCsrf() {
  return JSON.parse(document.body.getAttribute("hx-headers") || "{}")["X-CSRFToken"] || "";
}

async function envoyerPhotos(fichiers) {
  const envoi = document.getElementById("envoi");
  const suivi = document.getElementById("envoi-suivi");
  const auteur = document.getElementById("envoi-auteur");
  const boucle = document.getElementById("envoi-boucle");
  const cote = +envoi.dataset.cote || 2560;
  let reussies = 0;

  for (const fichier of fichiers) {
    const ligne = document.createElement("li");
    ligne.textContent = `${fichier.name} — réduction…`;
    suivi.prepend(ligne);

    const donnees = new FormData();
    donnees.append("photo", await reduire(fichier, cote), fichier.name.replace(/\.\w+$/, "") + ".jpg");
    donnees.append("auteur", auteur.value);
    if (auteur.value === "orga" && boucle?.value) donnees.append("boucle", boucle.value);

    ligne.textContent = `${fichier.name} — envoi…`;
    try {
      const reponse = await fetch(envoi.dataset.url, {
        method: "POST", body: donnees, headers: { "X-CSRFToken": jetonCsrf() },
      });
      const resultat = await reponse.json();
      if (resultat.ok) {
        reussies++;
        ligne.textContent = `✓ ${fichier.name}`;
        ligne.className = "ok";
        if (resultat.restant !== null) majRestant(auteur, resultat.restant);
      } else {
        ligne.textContent = `✗ ${fichier.name} : ${resultat.message}`;
        ligne.className = "ko";
        if (/Limite atteinte|plein/.test(resultat.message)) break;  // inutile d'insister
      }
    } catch {
      ligne.textContent = `✗ ${fichier.name} : connexion perdue, réessaie plus tard.`;
      ligne.className = "ko";
    }
  }
  if (reussies) htmx.trigger(document.body, "photos-modifiees");  // la grille se recharge
}

function majRestant(select, restant) {
  const option = select.selectedOptions[0];
  option.dataset.restant = restant;
  option.textContent = option.textContent.replace(/encore \d+ photos?/, `encore ${restant} photo${restant > 1 ? "s" : ""}`);
}

document.addEventListener("change", e => {
  if (e.target.id === "envoi-fichiers" && e.target.files.length) {
    envoyerPhotos([...e.target.files]);
    e.target.value = "";  // permet de rechoisir les mêmes fichiers
  }
  if (e.target.id === "envoi-auteur") {
    const champ = document.getElementById("envoi-boucle-champ");
    if (champ) champ.hidden = e.target.value !== "orga";
  }
});
