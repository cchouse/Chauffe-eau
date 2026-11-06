"""Exécution : lit la puissance de la prise, détecte les chauffes, apprend la durée, planifie et (si autorisé) pilote la prise."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time, timedelta
from typing import Any, Callable

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    ATTENTE_PUISSANCE_S, CONF_NOTIF, CONF_PRISE, CONF_PUISSANCE, DEBOUNCE_ARRET_S, DEBOUNCE_MARCHE_S, DOMAIN,
    ECHANTILLON_S, FORCE_MAX_S, HISTO_MAX, JOURNAL_MAX, OPTIONS_DEFAUT, TICK_S,
)
from .model import (
    CYCLE_MAX, CYCLE_MIN, ETATS, ETATS_LIBELLES, REPOS_PRINCIPAL_MIN, Appris, Detection, Plan, duree_txt, fenetre_hc,
    hhmm, planifier,
)

_LOGGER = logging.getLogger(__name__)
SIGNAL = f"{DOMAIN}_maj_{{}}"


def _heure(s: str) -> time:
    h = str(s).split(":")
    return time(int(h[0]), int(h[1]) if len(h) > 1 else 0)


class Ballon:
    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.hass = hass
        self.entry = entry
        self.cfg = dict(entry.data)
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self.appris = Appris()
        self.drapeaux = {"auto": False}
        self.journal: list[dict[str, Any]] = []
        self.historique: list[list[Any]] = []
        self.det = Detection()
        self.cycle: dict[str, Any] | None = None
        self.derniere_fin: float | None = None
        self.derniere_cmd: dict[str, Any] | None = None
        self.derniere_action: dict[str, Any] | None = None
        self.force: dict[str, float] | None = None
        self.ignore_nuit: float = 0.0
        self.etat = "inconnu"
        self.plan: Plan | None = None
        self.puissance: float | None = None
        self._dernier_ts: float | None = None
        self._dernier_echantillon = 0.0
        self._securite_ts: float | None = None
        self._unsubs: list[Callable[[], None]] = []
        self._verrou = asyncio.Lock()

    @property
    def opt(self) -> dict[str, Any]:
        return {**OPTIONS_DEFAUT, **self.entry.options}

    @property
    def signal(self) -> str:
        return SIGNAL.format(self.entry.entry_id)

    # ---------- cycle de vie ----------
    async def async_demarrer(self) -> None:
        d = await self.store.async_load() or {}
        self.appris = Appris.from_dict(d.get("appris"))
        self.drapeaux.update(d.get("drapeaux", {}))
        self.journal = d.get("journal", [])[-JOURNAL_MAX:]
        self.historique = d.get("historique", [])[-HISTO_MAX:]
        self.cycle = d.get("cycle")
        self.det.chauffe = bool(d.get("chauffe", False))
        self.derniere_fin = d.get("derniere_fin")
        self.derniere_cmd = d.get("derniere_cmd")
        self.force = d.get("force")
        self.ignore_nuit = float(d.get("ignore_nuit") or 0.0)
        ids = [self.cfg[CONF_PRISE], self.cfg[CONF_PUISSANCE]]
        self._unsubs.append(async_track_state_change_event(self.hass, ids, self._changement))
        self._unsubs.append(async_track_time_interval(self.hass, self._tick, timedelta(seconds=TICK_S)))
        await self._tick(None)

    async def async_arreter(self) -> None:
        for u in self._unsubs:
            u()
        self._unsubs.clear()
        await self.store.async_save(self._export())

    def _export(self) -> dict[str, Any]:
        return {"appris": self.appris.to_dict(), "drapeaux": self.drapeaux, "journal": self.journal[-JOURNAL_MAX:],
                "historique": self.historique[-HISTO_MAX:], "cycle": self.cycle, "chauffe": self.det.chauffe,
                "derniere_fin": self.derniere_fin, "derniere_cmd": self.derniere_cmd, "force": self.force,
                "ignore_nuit": self.ignore_nuit}

    def _sauver(self) -> None:
        self.store.async_delay_save(self._export, 30)

    @callback
    def _changement(self, _event) -> None:
        self.hass.async_create_task(self._tick(None))

    # ---------- lecture ----------
    def _lire_puissance(self) -> float | None:
        st = self.hass.states.get(self.cfg[CONF_PUISSANCE])
        if st is None or st.state in ("unknown", "unavailable", ""):
            return None
        try:
            return float(st.state)
        except ValueError:
            return None

    def _etat_prise(self) -> str:
        st = self.hass.states.get(self.cfg[CONF_PRISE])
        return "unavailable" if st is None else st.state

    # ---------- boucle ----------
    async def _tick(self, _now) -> None:
        async with self._verrou:
            await self._tick_interne()

    async def _tick_interne(self) -> None:
        now = dt_util.now()
        ts = now.timestamp()
        o = self.opt
        w = self._lire_puissance()
        prise = self._etat_prise()
        self.puissance = w
        # énergie du cycle en cours (intégration de la puissance)
        if self.cycle is not None and w is not None and self._dernier_ts is not None:
            self.cycle["wh"] += w * min(ts - self._dernier_ts, 180.0) / 3600.0
        self._dernier_ts = ts
        # historique pour la carte
        if ts - self._dernier_echantillon >= ECHANTILLON_S:
            self._dernier_echantillon = ts
            self.historique.append([int(ts), None if w is None else round(w), 1 if prise == "on" else 0])
            self.historique = self.historique[-HISTO_MAX:]
            self._sauver()
        # détection des chauffes
        if w is not None:
            ev, t = self.det.pas(ts, w, float(o["seuil_marche"]), float(o["seuil_arret"]), DEBOUNCE_MARCHE_S, DEBOUNCE_ARRET_S)
            if ev == "debut":
                self._debut_cycle(t)
            elif ev == "fin":
                await self._fin_cycle(t, ts)
        self.etat = "inconnu" if (w is None or prise in ("unavailable", "unknown")) else (
            "chauffe" if self.det.chauffe else ("coupe" if prise == "off" else "repos"))
        await self._forcage(ts)
        await self._securite(ts)
        self.plan = self._calculer_plan(now)
        await self._piloter(now, ts, prise)
        async_dispatcher_send(self.hass, self.signal)

    # ---------- cycles ----------
    def _source(self, debut: float) -> str:
        if self.force:
            return "force"
        c = self.derniere_cmd
        if c and c["service"] == "turn_on" and 0 <= debut - c["ts"] < 1800:
            return c["source"]
        return "thermostat"

    def _debut_cycle(self, t: float) -> None:
        repos = (t - self.derniere_fin) / 60 if self.derniere_fin else 9999.0
        self.cycle = {"debut": t, "wh": 0.0, "source": self._source(t), "repos_min": round(repos)}
        self._sauver()

    async def _fin_cycle(self, t_fin: float, ts: float) -> None:
        c = self.cycle
        self.cycle = None
        self.derniere_fin = t_fin
        if c is None:
            return
        duree = (t_fin - c["debut"]) / 60
        principal = (CYCLE_MIN <= duree <= CYCLE_MAX and c["repos_min"] >= REPOS_PRINCIPAL_MIN
                     and c["source"] != "force" and not c.get("interrompu"))
        self.journal.append({"debut": int(c["debut"]), "fin": int(t_fin), "duree_min": round(duree), "wh": round(c["wh"]),
                             "source": c["source"], "principal": principal, "interrompu": bool(c.get("interrompu"))})
        self.journal = self.journal[-JOURNAL_MAX:]
        if principal:
            self.appris.ajouter(duree, c["wh"])
        # correction quotidienne : une chauffe qui déborde des heures creuses avance l'allumage des nuits suivantes
        o = self.opt
        loc = dt_util.as_local(dt_util.utc_from_timestamp(c["debut"]))
        d, f, dedans = fenetre_hc(loc, _heure(o["hc_debut"]), _heure(o["hc_fin"]))
        if dedans and not c.get("interrompu") and duree >= CYCLE_MIN and c["source"] != "force":
            reste = (f.timestamp() - t_fin) / 60
            if reste < 0:
                self.appris.ajustement = min(90.0, self.appris.ajustement + 20.0)
            elif reste >= float(o["marge_fin"]) + 20 and self.appris.ajustement > 0:
                self.appris.ajustement = max(0.0, self.appris.ajustement - 10.0)
        if self.force and c["debut"] >= self.force["debut"] - 1:
            self.force = None
        self._sauver()

    async def _forcage(self, ts: float) -> None:
        f = self.force
        if not f:
            return
        if ts - f["debut"] > FORCE_MAX_S:
            self.force = None
            await self._commande("turn_off", "securite")
            await self._notifier("Ballon : chauffe forcée arrêtée par sécurité après 5 heures.")
        elif self.cycle is None and not self.det.chauffe and ts - f["debut"] > ATTENTE_PUISSANCE_S:
            self.force = None
            self.derniere_action = {"ts": ts, "service": "info", "source": "force",
                                    "raison": "La puissance n'est pas montée : le ballon est déjà chaud (thermostat ouvert)."}
            self._sauver()

    async def _securite(self, ts: float) -> None:
        c = self.cycle
        if c and c["source"] in ("auto", "force") and ts - c["debut"] > float(self.opt["marche_max"]) * 60:
            if self._securite_ts and ts - self._securite_ts < 900:
                return
            self._securite_ts = ts
            await self._commande("turn_off", "securite")
            await self._notifier(f"Ballon : arrêt de sécurité après {duree_txt(float(self.opt['marche_max']))} de chauffe.")

    # ---------- plan et pilotage ----------
    def _chaud_depuis(self, now: datetime) -> datetime | None:
        o = self.opt
        d, _f, dedans = fenetre_hc(now, _heure(o["hc_debut"]), _heure(o["hc_fin"]))
        if not dedans:
            return None
        for j in reversed(self.journal):
            if j["fin"] >= d.timestamp() and not j.get("interrompu") and j["duree_min"] >= CYCLE_MIN:
                return dt_util.as_local(dt_util.utc_from_timestamp(j["fin"]))
        return None

    def _calculer_plan(self, now: datetime) -> Plan:
        o = self.opt
        return planifier(now, _heure(o["hc_debut"]), _heure(o["hc_fin"]), float(o["marge_fin"]), float(o["marge_duree"]),
                         float(o["duree_defaut"]), self.appris, self._chaud_depuis(now), self.drapeaux["auto"])

    def _souhait(self, now: datetime, ts: float) -> bool | None:
        """État voulu de la prise : True = allumée, False = éteinte, None = je n'y touche pas."""
        if self.force:
            return True
        c = self.cycle
        if c and c["source"] == "auto":
            return True
        if not self.drapeaux["auto"]:
            return None
        p = self.plan
        if p is None:
            return None
        if p.dans_hc:
            if self.ignore_nuit == p.hc_fin.timestamp():
                return None                       # allumage annulé par vous pour cette nuit
            if not p.besoin:
                return None                       # déjà chaud cette nuit
            return bool(p.debut and now >= p.debut)
        if self.det.chauffe:
            return None                           # une chauffe déborde : on la laisse finir
        return False if self.opt["couper_hp"] else None

    async def _piloter(self, now: datetime, ts: float, prise: str) -> None:
        voulu = self._souhait(now, ts)
        if voulu is None or prise not in ("on", "off"):
            return
        if (voulu and prise == "on") or (not voulu and prise == "off"):
            return
        service = "turn_on" if voulu else "turn_off"
        c = self.derniere_cmd
        if c and c["service"] == service and ts - c["ts"] < 600:
            return                                # commande récente : on ne la renvoie pas
        source = "force" if self.force else "auto"
        await self._commande(service, source)
        if service == "turn_on" and source == "auto":
            await self._notifier(f"Ballon : prise allumée à {now.strftime('%H:%M')} "
                                 f"(durée apprise {duree_txt(self.appris.duree(float(self.opt['duree_defaut'])))}).")

    async def _commande(self, service: str, source: str) -> None:
        ts = dt_util.utcnow().timestamp()
        self.derniere_cmd = {"ts": ts, "service": service, "source": source}
        self.derniere_action = {"ts": ts, "service": service, "source": source}
        if service == "turn_off" and self.cycle is not None:
            self.cycle["interrompu"] = True
        try:
            await self.hass.services.async_call("switch", service, {"entity_id": self.cfg[CONF_PRISE]}, blocking=True)
        except Exception as err:  # noqa: BLE001 — on ne casse jamais la boucle
            _LOGGER.error("Commande %s refusée : %s", service, err)
            self.derniere_action["erreur"] = str(err)
        self._sauver()

    async def _notifier(self, message: str) -> None:
        try:
            if self.cfg.get(CONF_NOTIF):
                await self.hass.services.async_call("notify", "send_message",
                                                    {"entity_id": self.cfg[CONF_NOTIF], "message": message}, blocking=True)
            else:
                await self.hass.services.async_call("persistent_notification", "create",
                                                    {"title": "Pilotage ballon", "message": message}, blocking=True)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Notification impossible : %s", err)

    # ---------- actions utilisateur ----------
    async def forcer(self) -> None:
        ts = dt_util.utcnow().timestamp()
        self.force = {"debut": ts}
        await self._commande("turn_on", "force")
        await self._tick(None)

    async def arreter(self) -> None:
        """Arrête la chauffe forcée ou commandée, et annule l'allumage prévu pour cette nuit."""
        self.force = None
        if self.plan:
            self.ignore_nuit = self.plan.hc_fin.timestamp()
        if self._etat_prise() == "on" and (self.cycle is None or self.cycle["source"] != "thermostat" or True):
            await self._commande("turn_off", "annulation")
        self._sauver()
        await self._tick(None)

    async def definir_drapeau(self, nom: str, valeur: bool) -> None:
        self.drapeaux[nom] = valeur
        if nom == "auto" and valeur:
            self.ignore_nuit = 0.0
        self._sauver()
        await self._tick(None)

    # ---------- état pour l'interface ----------
    def snapshot(self) -> dict[str, Any]:
        now = dt_util.now()
        ts = now.timestamp()
        o = self.opt
        plan = self.plan
        base = self.appris.duree(float(o["duree_defaut"]))
        c = self.cycle
        bas = self.det.bas_depuis
        return {
            "etat": self.etat, "etat_libelle": ETATS_LIBELLES[self.etat], "puissance": self.puissance,
            "prise": self._etat_prise(), "drapeaux": dict(self.drapeaux),
            "force": None if not self.force else {"debut": int(self.force["debut"])},
            "plan": None if plan is None else {
                "besoin": plan.besoin, "debut": int(plan.debut.timestamp()) if plan.debut else None,
                "fin_estimee": int(plan.fin_estimee.timestamp()) if plan.fin_estimee else None,
                "fin_cible": int(plan.fin_cible.timestamp()) if plan.fin_cible else None,
                "hc_debut": int(plan.hc_debut.timestamp()), "hc_fin": int(plan.hc_fin.timestamp()),
                "dans_hc": plan.dans_hc, "duree_min": plan.duree_min, "repli": plan.repli, "serre": plan.serre,
                "raison": plan.raison, "annule": self.ignore_nuit == plan.hc_fin.timestamp()},
            "actions": [] if plan is None else plan.actions,
            "cycle": None if not c else {"debut": int(c["debut"]), "wh": round(c["wh"]), "source": c["source"],
                                          "duree_min": round((ts - c["debut"]) / 60)},
            "fin_chauffe": {
                "seuil_arret": o["seuil_arret"], "delai_min": round(DEBOUNCE_ARRET_S / 60), "en_chauffe": self.det.chauffe,
                "bas_depuis_min": None if not bas else round((ts - bas) / 60),
                "securite_min": round(float(o["marche_max"])) if c and c["source"] in ("auto", "force") else None},
            "garde_fous": {"hc": f"{o['hc_debut'][:5]}–{o['hc_fin'][:5]}", "marge_fin": o["marge_fin"],
                           "marche_max": o["marche_max"], "couper_hp": bool(o["couper_hp"]),
                           "seuil_marche": o["seuil_marche"], "seuil_arret": o["seuil_arret"]},
            "appris": {"n": len(self.appris.durees), "durees": self.appris.durees[-5:], "energies": self.appris.energies[-5:],
                       "duree": base, "fiable": self.appris.fiable(), "confiance": self.appris.confiance(),
                       "ajustement": self.appris.ajustement},
            "historique": self.historique[-HISTO_MAX:], "journal": self.journal[-8:][::-1],
            "derniere_action": self.derniere_action,
        }
