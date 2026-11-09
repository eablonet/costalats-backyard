// Compte à rebours jusqu'au prochain départ.
// Tout élément [data-cible="date ISO"] affiche le temps restant (h:mm:ss ou m:ss).
// À zéro, on émet l'événement HTMX « depart » sur <body> : chaque zone qui écoute
// `hx-trigger="depart from:body"` (horloge, carnet, tableau de gestion, écran)
// se recharge seule. Plus de rechargement complet de la page.

function enSaisie() {
  // Vrai si un coureur est en train de taper un chrono : on ne rafraîchit pas son carnet.
  return document.activeElement?.name === "chrono" || !!document.querySelector(".boucle__chrono[open]");
}

function majHorloges() {
  document.querySelectorAll("[data-cible]").forEach(el => {
    const reste = Math.max(0, Math.round((new Date(el.dataset.cible) - Date.now()) / 1000));
    const h = Math.floor(reste / 3600), m = Math.floor(reste % 3600 / 60), s = reste % 60;
    el.textContent = (h ? h + ":" : "") + String(m).padStart(h ? 2 : 1, "0") + ":" + String(s).padStart(2, "0");
    if (reste === 0 && !el.dataset.fini) {
      el.dataset.fini = "1";
      // 2 s de marge pour que le serveur considère bien la nouvelle boucle comme partie.
      setTimeout(() => htmx.trigger(document.body, "depart"), 2000);
    }
  });
}

majHorloges();
setInterval(majHorloges, 1000);
