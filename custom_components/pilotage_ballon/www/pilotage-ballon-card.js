/* Carte « Pilotage ballon » — chargée automatiquement par l'intégration.
 * Répond à : que fait le ballon, quand l'allumer et POURQUOI, quelles sont les prochaines étapes, et que puis-je forcer ou annuler. */
const VERSION = "0.1.0";
const fmt = (x, n = 1) => (x === null || x === undefined || Number.isNaN(x)) ? "–" : Number(x).toFixed(n).replace(".", ",");
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const hhmm = (ts) => new Date(ts * 1000).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
const jjmm = (ts) => new Date(ts * 1000).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
const duree = (m) => { m = Math.round(m); return m >= 60 ? `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")}` : `${m} min`; };
const ICONE = { chauffe: "●", repos: "○", coupe: "⏻", inconnu: "?" };
const SOURCES = { auto: "automatique", force: "forcé", thermostat: "thermostat" };
const STYLE = `
:host { display:block; } ha-card { padding:16px; } * { box-sizing:border-box; }
.tete { display:flex; justify-content:space-between; align-items:center; gap:8px; margin-bottom:10px; }
.titre { font-size:1.1rem; font-weight:600; color:var(--primary-text-color); }
.puce { font-size:.9rem; font-weight:600; padding:6px 12px; border-radius:999px; border:2px solid var(--primary-color); color:var(--primary-text-color); white-space:nowrap; }
.puce.pb { border-color:var(--error-color,#b3261e); }
.bandeau { border:2px solid var(--divider-color); border-radius:12px; padding:12px; }
.bandeau.act { border-color:var(--primary-color); }
.heure { font-size:2.1rem; font-weight:600; line-height:1.1; color:var(--primary-text-color); }
.sous { font-size:.9rem; color:var(--secondary-text-color); line-height:1.45; margin-top:6px; }
.pourquoi { font-size:.92rem; color:var(--primary-text-color); line-height:1.5; margin-top:8px; }
.mode { display:inline-block; margin-top:8px; font-size:.8rem; font-weight:600; padding:4px 10px; border:1px solid var(--divider-color); border-radius:999px; color:var(--secondary-text-color); }
.actions { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:12px; }
button { font:inherit; color:var(--primary-text-color); cursor:pointer; }
button.b { min-height:52px; border-radius:12px; border:2px solid var(--primary-color); background:transparent; font-weight:600; padding:0 10px; }
button.b:hover { background:color-mix(in srgb, var(--primary-color) 12%, transparent); }
button.b:disabled { opacity:.5; cursor:not-allowed; }
button:focus-visible { outline:3px solid var(--primary-color); outline-offset:2px; }
.inter { display:grid; grid-template-columns:1fr; gap:8px; margin-top:12px; }
button.t { min-height:48px; display:flex; justify-content:space-between; align-items:center; padding:0 14px; border-radius:12px; border:2px solid var(--divider-color); background:transparent; font-weight:600; text-align:left; }
button.t[aria-pressed="true"] { border-color:var(--primary-color); background:color-mix(in srgb, var(--primary-color) 14%, transparent); }
.sec { margin-top:18px; } .sec h3 { margin:0 0 6px; font-size:.95rem; font-weight:600; color:var(--primary-text-color); }
.petit { font-size:.8rem; color:var(--secondary-text-color); line-height:1.4; }
svg.g { width:100%; height:auto; display:block; }
.lg { display:flex; flex-wrap:wrap; gap:12px; font-size:.75rem; color:var(--secondary-text-color); margin-top:4px; }
.lg i { display:inline-block; width:16px; height:10px; margin-right:4px; vertical-align:middle; border-radius:2px; }
.piece { padding:10px; border:2px solid transparent; border-radius:10px; font-size:.9rem; color:var(--primary-text-color); }
.piece.lim { border-color:var(--primary-color); }
.piece .l1 { display:flex; justify-content:space-between; gap:8px; font-weight:600; }
.piece .l2 { color:var(--secondary-text-color); font-size:.8rem; margin-top:2px; }
ul { list-style:none; margin:0; padding:0; } li { padding:6px 0; border-bottom:1px solid var(--divider-color); font-size:.88rem; color:var(--primary-text-color); } li:last-child { border:0; }
.vide { color:var(--secondary-text-color); font-size:.88rem; }
details { margin-top:14px; border:1px solid var(--divider-color); border-radius:12px; padding:0 12px; }
summary { min-height:48px; display:flex; align-items:center; cursor:pointer; font-weight:600; color:var(--primary-text-color); }
details p, details ul { margin:0 0 12px; font-size:.9rem; color:var(--primary-text-color); line-height:1.5; }
ha-card { display:block; container-type:inline-size; }
.grille { display:grid; grid-template-columns:1fr; gap:0 18px; align-items:start; }
.c1, .c2, .c3 { min-width:0; }
@container (min-width: 520px) { .grille { grid-template-columns:1fr 1fr; } .c3 { grid-column:1 / -1; display:grid; grid-template-columns:1fr 1fr; gap:0 18px; align-items:start; } .c3 > * { min-width:0; } }
.c3 > details { grid-column:1 / -1; }
@container (min-width: 880px) { .grille { grid-template-columns:minmax(0,1fr) minmax(0,1.1fr) minmax(0,1fr); } .c3 { grid-column:auto; display:block; } }
.zt { display:grid; grid-template-columns:1fr 1fr; gap:8px; margin:8px 0; }
button.zb { min-height:48px; border-radius:12px; border:2px solid var(--divider-color); background:transparent; font-weight:600; }
button.zb[aria-pressed="true"] { border-color:var(--primary-color); background:color-mix(in srgb, var(--primary-color) 14%, transparent); }
.cons { display:flex; align-items:center; justify-content:space-between; gap:8px; margin:10px 0 4px; flex-wrap:wrap; }
.cons .val { font-size:2rem; font-weight:600; color:var(--primary-text-color); }
.cons .pm { display:flex; gap:8px; } button.pm1 { min-width:56px; min-height:56px; border-radius:12px; border:2px solid var(--primary-color); background:transparent; font-size:1.4rem; font-weight:600; }
.jr { display:grid; grid-template-columns:repeat(7,1fr); gap:4px; margin:10px 0; }
button.j { min-height:48px; min-width:0; padding:0; border-radius:10px; border:2px solid var(--divider-color); background:transparent; font-weight:600; }
button.j[aria-pressed="true"] { border-color:var(--primary-color); background:color-mix(in srgb, var(--primary-color) 14%, transparent); }
.tr { display:grid; grid-template-columns:1fr 1fr 48px; gap:8px; align-items:center; margin:6px 0; }
.tr label { display:flex; flex-direction:column; font-size:.75rem; color:var(--secondary-text-color); }
.tr input { min-height:48px; font:inherit; font-size:1rem; padding:0 8px; border-radius:10px; border:2px solid var(--divider-color); background:transparent; color:var(--primary-text-color); color-scheme:light dark; width:100%; }
.tr input:focus-visible { outline:3px solid var(--primary-color); outline-offset:2px; }
button.x { min-height:48px; min-width:48px; border-radius:10px; border:2px solid var(--divider-color); background:transparent; font-size:1.1rem; }
.ok { font-weight:600; }
@media (forced-colors: active) { .puce,.bandeau.act,button.b,button.t[aria-pressed="true"],.piece.lim { border-color:Highlight; } }
@media (prefers-reduced-motion: reduce) { * { transition:none !important; animation:none !important; } }
`;

class PilotageBallonCard extends HTMLElement {
  setConfig(config) {
    if (!config || !config.entity) throw new Error("Choisissez l'entité « État du ballon ».");
    this._config = config; if (!this.shadowRoot) this.attachShadow({ mode: "open" }); this._cle = null;
  }
  set hass(h) {
    this._hass = h; const st = h.states[this._config.entity];
    const cle = st ? st.last_updated + "|" + st.state : "absent";
    if (cle === this._cle) return; this._cle = cle; this._dessiner(st);
  }
  getCardSize() { return 8; }
  getGridOptions() { return { columns: 12, min_columns: 6, rows: "auto" }; }
  static getConfigElement() { return document.createElement("pilotage-ballon-card-editor"); }
  static getStubConfig(h) {
    const e = Object.keys(h.states).find((k) => k.startsWith("sensor.") && h.states[k].attributes && h.states[k].attributes.fin_chauffe && h.states[k].attributes.boutons);
    return { entity: e || "" };
  }
  _appel(domaine, service, eid) { if (eid) this._hass.callService(domaine, service, { entity_id: eid }); }

  _frise(a) {
    const h = a.historique || []; const p = a.plan; const now = Math.floor(Date.now() / 1000);
    const t0 = now - 12 * 3600, t1 = now + 12 * 3600, W = 340, pad = 8, Hs = 34;
    const X = (t) => pad + ((Math.min(Math.max(t, t0), t1) - t0) / (t1 - t0)) * (W - 2 * pad);
    let hc = "";
    if (p) for (const k of [-1, 0, 1]) { const d = p.hc_debut + k * 86400, f = p.hc_fin + k * 86400; if (f > t0 && d < t1)
      hc += `<rect x="${X(d).toFixed(1)}" y="4" width="${Math.max(0, X(f) - X(d)).toFixed(1)}" height="${Hs - 4}" fill="var(--primary-color)" opacity=".12"/>`; }
    const seuil = (a.garde_fous || {}).seuil_marche || 200; let barres = "";
    for (let i = 0; i < h.length; i++) {
      const [ts, w] = h[i]; const fin = i + 1 < h.length ? h[i + 1][0] : now; if (w == null || w < seuil) continue;
      barres += `<rect x="${X(Math.max(ts, t0)).toFixed(1)}" y="8" width="${Math.max(1.5, X(fin) - X(Math.max(ts, t0))).toFixed(1)}" height="${Hs - 12}" fill="var(--primary-color)"/>`; }
    let prevu = "";
    if (p && p.besoin && p.debut && p.fin_estimee) { const x0 = X(Math.max(p.debut, now)), x1 = X(p.fin_estimee);
      if (x1 > x0) prevu = `<rect x="${x0.toFixed(1)}" y="8" width="${(x1 - x0).toFixed(1)}" height="${Hs - 12}" fill="none" stroke="var(--primary-color)" stroke-width="2" stroke-dasharray="4 3"/>`; }
    let axe = "";
    for (let k = -12; k <= 12; k += 3) { const t = now + k * 3600; const d = new Date(t * 1000);
      axe += `<text x="${X(t).toFixed(1)}" y="${Hs + 12}" font-size="9" text-anchor="middle" fill="var(--secondary-text-color)">${String(d.getHours()).padStart(2, "0")}h</text>`; }
    return `<svg class="g" viewBox="0 0 ${W} ${Hs + 16}" role="img" aria-label="Frise du ballon : chauffe passée, chauffe prévue et heures creuses sur 24 heures">
      <rect x="${pad}" y="8" width="${W - 2 * pad}" height="${Hs - 12}" fill="var(--divider-color)" opacity=".4" rx="3"/>${hc}${barres}${prevu}
      <line x1="${X(now)}" x2="${X(now)}" y1="2" y2="${Hs - 2}" stroke="var(--primary-text-color)" stroke-width="2"/>${axe}</svg>
      <div class="lg"><span><i style="background:var(--primary-color)"></i>Chauffe</span><span><i style="border:2px dashed var(--primary-color)"></i>Chauffe prévue</span><span><i style="background:var(--primary-color);opacity:.2"></i>Heures creuses</span><span>| Maintenant</span></div>`;
  }

  _courbe(a) {
    const h = (a.historique || []).filter((x) => x[1] != null); if (h.length < 2) return `<div class="vide">La courbe apparaîtra après quelques mesures (un point toutes les 5 minutes).</div>`;
    const W = 340, H = 110, pad = 8; const hi = Math.max(500, ...h.map((x) => x[1])) * 1.05;
    const a0 = h[0][0], a1 = h[h.length - 1][0];
    const X = (t) => pad + ((t - a0) / Math.max(1, a1 - a0)) * (W - 2 * pad), Y = (v) => H - pad - (v / hi) * (H - 2 * pad);
    const d = h.map((p, k) => `${k ? "L" : "M"}${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join(" ");
    const s = (a.garde_fous || {}).seuil_marche || 200;
    return `<svg class="g" viewBox="0 0 ${W} ${H}" role="img" aria-label="Puissance de la prise sur 24 heures"><path d="${d}" fill="none" stroke="var(--primary-text-color)" stroke-width="2.2"/>
      <line x1="${pad}" x2="${W - pad}" y1="${Y(s).toFixed(1)}" y2="${Y(s).toFixed(1)}" stroke="var(--secondary-text-color)" stroke-dasharray="3 3"/>
      <text x="${pad}" y="10" font-size="9" fill="var(--secondary-text-color)">${fmt(hi, 0)} W</text><text x="${pad}" y="${H - 1}" font-size="9" fill="var(--secondary-text-color)">0 W</text></svg>
      <div class="lg"><span>━ Puissance</span><span>┈ Seuil de chauffe (${s} W)</span></div>`;
  }

  _dessiner(st) {
    const r = this.shadowRoot;
    if (!st) { r.innerHTML = `<style>${STYLE}</style><ha-card><p>Entité introuvable : ${esc(this._config.entity)}</p></ha-card>`; return; }
    const a = st.attributes || {}; const b = a.boutons || {}; const d = a.drapeaux || {}; const p = a.plan; const ap = a.appris || {};
    const gf = a.garde_fous || {}; const fc = a.fin_chauffe || {}; const cy = a.cycle; const pb = a.etat === "inconnu";
    let ban;
    if (a.etat === "chauffe" && cy) ban = `<div class="heure">${esc(a.etat_libelle)}</div><div class="sous">Depuis ${hhmm(cy.debut)} (${duree(cy.duree_min)}) · ${fmt(cy.wh / 1000)} kWh · ${esc(SOURCES[cy.source] || cy.source)}${a.puissance != null ? " · " + fmt(a.puissance, 0) + " W" : ""}</div>${p && p.fin_estimee ? `<div class="pourquoi">${p.besoin ? "" : ""}Fin de chauffe estimée vers ${hhmm(Math.max(cy.debut + (ap.duree || 0) * 60, Date.now() / 1000))}.</div>` : ""}`;
    else if (p && p.besoin && p.debut) ban = `<div class="heure">${hhmm(p.debut)}</div><div class="sous">${p.dans_hc && p.debut <= Date.now() / 1000 ? "Allumage maintenant" : "Prochain allumage conseillé"} — chaud avant ${hhmm(p.fin_cible)}</div><div class="pourquoi">${esc(p.raison)}</div>`;
    else ban = `<div class="heure">Rien à faire</div><div class="pourquoi">${esc(p ? p.raison : "En attente des premières mesures.")}</div>`;
    const mode = d.auto ? "Automatique : je pilote la prise" : "Mode conseil : la prise n'est pas pilotée";
    const actions = (a.actions || []).map((x) => `<li class="${x.passe ? "passe" : ""}"><b>${esc(x.heure)}</b> ${x.passe ? "✓" : "→"} ${esc(x.texte)}</li>`).join("") || `<li class="vide">Aucune action prévue.</li>`;
    const journal = (a.journal || []).map((j) => `<li>${jjmm(j.debut)} → ${hhmm(j.fin)} · ${duree(j.duree_min)} · ${fmt(j.wh / 1000)} kWh · ${esc(SOURCES[j.source] || j.source)}${j.principal ? " · ✓ compte pour l'apprentissage" : j.interrompu ? " · interrompue" : " · appoint"}</li>`).join("") || `<li class="vide">Aucune chauffe enregistrée pour l'instant.</li>`;
    const inter = `<button class="t" id="auto" aria-pressed="${!!d.auto}" ${b.auto ? "" : "disabled"}><span>Allumage automatique</span><span>${d.auto ? "● Activé" : "○ Désactivé"}</span></button>`;
    const da = a.derniere_action;
    r.innerHTML = `<style>${STYLE} li.passe { color:var(--secondary-text-color); } li b { font-variant-numeric:tabular-nums; }</style><ha-card>
      <div class="tete"><span class="titre">Ballon d'eau chaude</span><span class="puce ${pb ? "pb" : ""}"><span aria-hidden="true">${ICONE[a.etat] || "?"}</span> ${esc(a.etat_libelle)}</span></div>
      ${a.force ? `<div class="bandeau act" style="margin-bottom:10px"><b>Chauffe forcée</b> depuis ${hhmm(a.force.debut)} : je m'arrête quand le thermostat coupe.</div>` : ""}
      <div class="grille">
      <div class="c1">
        <div class="bandeau ${d.auto ? "act" : ""}">${ban}<span class="mode">${mode}</span></div>
        <div class="actions"><button class="b" id="forcer" ${b.forcer ? "" : "disabled"}>▶ Chauffer maintenant</button>
          <button class="b" id="arreter" ${b.arreter ? "" : "disabled"}>■ Arrêter / annuler l'allumage prévu</button></div>
        <div class="inter">${inter}</div>
        <details ${a.etat === "chauffe" ? "open" : ""}><summary>Quand la chauffe s'arrête</summary><ul>
          <li>${fc.en_chauffe ? "●" : "○"} Le thermostat coupe : la puissance reste sous ${fc.seuil_arret} W pendant ${fc.delai_min} min${fc.bas_depuis_min != null ? ` — ${fc.bas_depuis_min} min` : ""}</li>
          ${fc.securite_min ? `<li>Sécurité : arrêt de la prise après ${duree(fc.securite_min)} de chauffe commandée</li>` : ""}
          <li>Vous pouvez aussi arrêter à tout moment avec « Arrêter / annuler ».</li></ul></details>
        <details><summary>Garde-fous actifs</summary><ul>
          <li>Heures creuses : ${esc(gf.hc)}</li><li>Chaud ${gf.marge_fin} min avant la fin des heures creuses</li>
          <li>Seuil de chauffe : ${gf.seuil_marche} W · seuil d'arrêt : ${gf.seuil_arret} W</li>
          <li>Arrêt de sécurité d'une chauffe commandée : ${duree(gf.marche_max)}</li>
          <li>Prise ${gf.couper_hp ? "coupée" : "laissée telle quelle"} en heures pleines</li>
          <li>Tant que moins de 3 chauffes complètes sont observées : chauffe dès le début des heures creuses</li></ul></details>
      </div>
      <div class="c2">
        <div class="sec"><h3>Ce qui est prévu</h3><ul>${actions}</ul></div>
        <div class="sec"><h3>Le ballon sur 24 heures</h3>${this._frise(a)}</div>
        <details><summary>Ce que j'ai appris (${Math.round((ap.confiance || 0) * 100)} % de confiance)</summary>
          <ul><li>Durée de chauffe : ${ap.fiable ? `${duree(ap.duree)} (prudent, sur ${ap.n} chauffes complètes)` : `valeur par défaut ${duree(ap.duree)} — ${ap.n} chauffe(s) complète(s) observée(s) sur 3 nécessaires`}</li>
          ${ap.durees && ap.durees.length ? `<li>Dernières chauffes : ${ap.durees.map((x) => duree(x)).join(", ")}</li>` : ""}
          ${ap.ajustement ? `<li>Correction de prudence : +${Math.round(ap.ajustement)} min (une nuit a débordé)</li>` : ""}</ul>
          <p class="petit">Seules les chauffes qui suivent au moins 3 heures de repos comptent : les appoints de la nuit ne faussent pas la durée.</p></details>
      </div>
      <div class="c3">
        <div class="sec"><h3>Puissance de la prise${a.puissance != null ? " : " + fmt(a.puissance, 0) + " W" : ""}</h3>${this._courbe(a)}</div>
        <details><summary>Dernières chauffes</summary><ul>${journal}</ul>${da ? `<p class="petit">Dernière commande : ${esc(da.service === "turn_on" ? "allumage" : da.service === "turn_off" ? "arrêt" : "information")} (${esc(da.source)}) à ${jjmm(da.ts)}${da.raison ? " — " + esc(da.raison) : ""}${da.erreur ? " — refusée : " + esc(da.erreur) : ""}</p>` : ""}</details>
      </div>
      </div>
    </ha-card>`;
    r.getElementById("forcer")?.addEventListener("click", () => this._appel("button", "press", b.forcer));
    r.getElementById("arreter")?.addEventListener("click", () => this._appel("button", "press", b.arreter));
    r.getElementById("auto")?.addEventListener("click", () => this._appel("switch", d.auto ? "turn_off" : "turn_on", b.auto));
  }
}

class PilotageBallonCardEditor extends HTMLElement {
  setConfig(c) { this._config = c; this._rendre(); }
  set hass(h) { this._hass = h; this._rendre(); }
  _rendre() {
    if (!this._hass || !this._config) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = () => "Entité « État du ballon »";
      this._form.addEventListener("value-changed", (e) => this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: e.detail.value }, bubbles: true, composed: true })));
      this.appendChild(this._form);
    }
    this._form.hass = this._hass; this._form.data = this._config;
    this._form.schema = [{ name: "entity", required: true, selector: { entity: { domain: "sensor", integration: "pilotage_ballon", device_class: "enum" } } }];
  }
}
customElements.get("pilotage-ballon-card") || customElements.define("pilotage-ballon-card", PilotageBallonCard);
customElements.get("pilotage-ballon-card-editor") || customElements.define("pilotage-ballon-card-editor", PilotageBallonCardEditor);
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "pilotage-ballon-card")) window.customCards.push({ type: "pilotage-ballon-card", name: "Pilotage ballon", description: "Prochain allumage et pourquoi, étapes prévues, frise 24 h, puissance, apprentissage, forçage.", preview: false });
console.info(`%c PILOTAGE-BALLON %c ${VERSION}`, "background:#1F5A4A;color:#fff", "");
