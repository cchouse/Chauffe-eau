"""Logique pure (sans Home Assistant) : fenêtre d'heures creuses, apprentissage de la durée, plan et actions prévues."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Any

from .const import CYCLES_FIABLES

ETATS = ("inconnu", "chauffe", "repos", "coupe")
ETATS_LIBELLES = {"inconnu": "État inconnu", "chauffe": "Chauffe en cours", "repos": "Ballon chaud, au repos",
                  "coupe": "Prise éteinte"}
CYCLE_MIN = 15.0          # minutes : une chauffe plus courte est un appoint, pas un cycle complet
CYCLE_MAX = 480.0
REPOS_PRINCIPAL_MIN = 180  # minutes de repos avant une chauffe pour qu'elle compte comme « complète »


def hhmm(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def duree_txt(minutes: float) -> str:
    m = int(round(minutes))
    return f"{m // 60} h {m % 60:02d}" if m >= 60 else f"{m} min"


@dataclass
class Appris:
    durees: list[float] = field(default_factory=list)     # minutes des chauffes complètes
    energies: list[float] = field(default_factory=list)   # Wh de ces chauffes
    ajustement: float = 0.0                               # minutes ajoutées après une nuit non terminée

    def ajouter(self, minutes: float, wh: float) -> None:
        if CYCLE_MIN <= minutes <= CYCLE_MAX:
            self.durees = (self.durees + [round(minutes, 1)])[-20:]
            self.energies = (self.energies + [round(wh)])[-20:]

    def fiable(self) -> bool:
        return len(self.durees) >= CYCLES_FIABLES

    def duree(self, defaut: float) -> float:
        """Durée de chauffe prévue : 80e centile des chauffes complètes récentes (prudent), sinon la valeur par défaut."""
        if not self.fiable():
            return float(defaut)
        d = sorted(self.durees)
        return d[min(len(d) - 1, int(0.8 * len(d)))]

    def confiance(self) -> float:
        return round(min(1.0, len(self.durees) / 5), 2)

    def to_dict(self) -> dict[str, Any]:
        return {"durees": self.durees, "energies": self.energies, "ajustement": self.ajustement}

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "Appris":
        d = d or {}
        return cls(list(d.get("durees", [])), list(d.get("energies", [])), float(d.get("ajustement", 0.0)))


def fenetre_hc(now: datetime, debut: time, fin: time) -> tuple[datetime, datetime, bool]:
    """(début, fin, dedans) de la fenêtre d'heures creuses en cours, sinon de la prochaine."""
    tz = now.tzinfo
    for k in (-1, 0, 1):
        d = datetime.combine(now.date() + timedelta(days=k), debut, tzinfo=tz)
        f = datetime.combine(now.date() + timedelta(days=k), fin, tzinfo=tz)
        if f <= d:
            f += timedelta(days=1)
        if d <= now < f:
            return d, f, True
    d = datetime.combine(now.date(), debut, tzinfo=tz)
    if d <= now:
        d += timedelta(days=1)
    f = datetime.combine(d.date(), fin, tzinfo=tz)
    if f <= d:
        f += timedelta(days=1)
    return d, f, False


@dataclass
class Plan:
    besoin: bool
    hc_debut: datetime
    hc_fin: datetime
    dans_hc: bool
    debut: datetime | None = None          # heure d'allumage conseillée
    fin_estimee: datetime | None = None    # fin de chauffe estimée
    fin_cible: datetime | None = None      # « chaud avant »
    duree_min: float = 0.0
    repli: bool = False
    serre: bool = False
    raison: str = ""
    actions: list[dict[str, Any]] = field(default_factory=list)


def planifier(now: datetime, hc_debut: time, hc_fin: time, marge_fin: float, marge_duree: float, duree_defaut: float,
              appris: Appris, deja_chaud: datetime | None, auto: bool) -> Plan:
    """Heure d'allumage à rebours depuis la fin des heures creuses, ou dès le début tant que rien n'est appris."""
    d, f, dedans = fenetre_hc(now, hc_debut, hc_fin)
    cible = f - timedelta(minutes=marge_fin)
    if deja_chaud is not None and dedans and deja_chaud >= d:
        p = Plan(False, d, f, dedans, fin_cible=cible, raison=f"Le ballon a fini de chauffer à {hhmm(deja_chaud)} : rien à faire cette nuit.")
        p.actions = _actions(p, auto, now)
        return p
    base = appris.duree(duree_defaut)
    duree = base * marge_duree + appris.ajustement
    repli = not appris.fiable()
    debut = d if repli else cible - timedelta(minutes=duree)
    serre = False
    if debut < d:
        debut, serre = d, True
    fin_est = debut + timedelta(minutes=base)
    if repli:
        raison = (f"Je n'ai pas encore observé {CYCLES_FIABLES} chauffes complètes ({len(appris.durees)} pour l'instant) : "
                  f"par sécurité, chauffe dès le début des heures creuses ({hhmm(d)}). Je mesure la durée à chaque nuit "
                  f"et je décalerai l'allumage ensuite. Durée supposée en attendant : {duree_txt(base)}.")
    else:
        raison = (f"Allumage conseillé à {hhmm(debut)} : le ballon met en général {duree_txt(base)} à chauffer "
                  f"(80e centile de {len(appris.durees)} chauffes), plus {round((marge_duree - 1) * 100)} %"
                  f"{' et ' + str(round(appris.ajustement)) + ' min de correction' if appris.ajustement else ''} de marge, "
                  f"pour qu'il soit chaud à {hhmm(cible)}, {round(marge_fin)} min avant la fin des heures creuses ({hhmm(f)}).")
        if serre:
            raison += " Ça laisse très peu de marge : je commence dès le début des heures creuses."
    p = Plan(True, d, f, dedans, debut, fin_est, cible, round(duree), repli, serre, raison)
    p.actions = _actions(p, auto, now)
    return p


def _actions(p: Plan, auto: bool, now: datetime) -> list[dict[str, Any]]:
    """Les prochaines étapes, écrites en clair (avec ce que je fais seul et ce qui reste à faire à la main)."""
    mode = "auto" if auto else "conseil"
    out: list[dict[str, Any]] = []

    def add(ts: datetime, texte: str, m: str = mode) -> None:
        out.append({"ts": int(ts.timestamp()), "heure": hhmm(ts), "texte": texte, "mode": m, "passe": ts <= now})

    add(p.hc_debut, "Début des heures creuses." + (
        f" La prise reste éteinte jusqu'à {hhmm(p.debut)}." if auto and p.besoin and p.debut and p.debut > p.hc_debut else ""), "info")
    if p.besoin and p.debut:
        add(p.debut, "J'allume la prise : le ballon chauffe." if auto else "Allumage conseillé : allumez la prise (mode conseil, je ne pilote pas la prise).")
        add(p.fin_estimee, "Fin de chauffe estimée : le thermostat coupe, la puissance retombe.", "info")
    add(p.hc_fin, "Fin des heures creuses.", "info")
    return out


@dataclass
class Detection:
    """Détecte les débuts et fins de chauffe à partir de la puissance seule (avec anti-rebond)."""
    chauffe: bool = False
    haut_depuis: float | None = None
    bas_depuis: float | None = None

    def pas(self, ts: float, w: float, seuil_marche: float, seuil_arret: float, deb_marche: float, deb_arret: float) -> tuple[str | None, float]:
        """Retourne (« debut » | « fin » | None, instant réel du changement)."""
        if not self.chauffe:
            if w >= seuil_marche:
                self.haut_depuis = self.haut_depuis or ts
                if ts - self.haut_depuis >= deb_marche:
                    t = self.haut_depuis
                    self.chauffe, self.haut_depuis, self.bas_depuis = True, None, None
                    return "debut", t
            else:
                self.haut_depuis = None
        else:
            if w <= seuil_arret:
                self.bas_depuis = self.bas_depuis or ts
                if ts - self.bas_depuis >= deb_arret:
                    t = self.bas_depuis
                    self.chauffe, self.haut_depuis, self.bas_depuis = False, None, None
                    return "fin", t
            else:
                self.bas_depuis = None
        return None, ts
