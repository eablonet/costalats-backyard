// Grand écran : bascule automatique du critère + défilement des colonnes trop longues.

// --- Bascule Boucles -> Série -> Meilleur chrono -> … -------------------------
// La durée vient de l'admin (data-bascule, en minutes) et est relue à chaque tick :
// un changement de réglage est pris en compte au rafraîchissement suivant (≤ 30 s).
let debutBascule = Date.now();

function basculer(cible) {
  // cible : critère choisi au clic ; sinon on passe au suivant.
  const champ = document.getElementById("ecran-critere");
  const cles = [...document.querySelectorAll(".ecran__criteres [data-cle]")].map(el => el.dataset.cle);
  champ.value = cible ?? cles[(cles.indexOf(champ.value) + 1) % cles.length];
  debutBascule = Date.now();  // le chrono de bascule repart de 0
  // Retour visuel immédiat, sans attendre la réponse du serveur.
  document.querySelectorAll(".ecran__criteres [data-cle]").forEach(el => el.classList.toggle("actif", el.dataset.cle === champ.value));
  const barre = document.querySelector(".ecran__progression i");
  if (barre) { barre.style.transition = "none"; barre.style.width = "0"; barre.offsetWidth; barre.style.transition = ""; }
  for (const cle in etatDefilement) delete etatDefilement[cle];  // nouvelles listes : on repart du haut
  htmx.trigger(document.body, "bascule");  // #ecran-contenu se recharge avec le nouveau critère
}

function tickBascule() {
  const minutes = parseFloat(document.getElementById("ecran-contenu")?.dataset.bascule) || 0;
  const barre = document.querySelector(".ecran__progression i");
  if (!minutes) return;
  const avancement = (Date.now() - debutBascule) / (minutes * 60000);
  if (barre) barre.style.width = Math.min(100, avancement * 100) + "%";
  if (avancement >= 1) basculer();
}
setInterval(tickBascule, 500);

// Clic sur une étiquette : bascule tout de suite sur ce classement.
document.addEventListener("click", e => {
  const etiquette = e.target.closest(".ecran__criteres [data-cle]");
  if (etiquette) basculer(etiquette.dataset.cle);
});

// --- Défilement automatique ---------------------------------------------------
// Descend doucement, pause, revient en haut. L'état est gardé par colonne (data-cle)
// pour survivre aux rafraîchissements HTMX qui remplacent le contenu.
const etatDefilement = {};
const VITESSE = 30, PAUSE = 4;  // px/s, secondes
let avant = performance.now();

function defiler(maintenant) {
  const dt = (maintenant - avant) / 1000;
  avant = maintenant;
  document.querySelectorAll(".ecran__liste").forEach(el => {
    const max = el.scrollHeight - el.clientHeight;
    const st = etatDefilement[el.dataset.cle] ??= { pos: 0, pause: PAUSE };
    if (max <= 0) { st.pos = 0; el.scrollTop = 0; return; }
    if (st.pause > 0) st.pause -= dt;
    else if (st.pos >= max) { st.pos = 0; st.pause = PAUSE; }
    else { st.pos = Math.min(max, st.pos + VITESSE * dt); if (st.pos >= max) st.pause = PAUSE; }
    el.scrollTop = st.pos;
  });
  requestAnimationFrame(defiler);
}
requestAnimationFrame(defiler);
