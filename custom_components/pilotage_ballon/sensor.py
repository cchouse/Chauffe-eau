from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfTime

from .entity import BallonEntity
from .model import ETATS


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    b = entry.runtime_data
    async_add_entities([Etat(b), ProchainAllumage(b), DureePrevue(b), Confiance(b)])


class Etat(BallonEntity, SensorEntity):
    """État du ballon + tout ce que montre la carte (attributs non enregistrés dans l'historique)."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(ETATS)
    _unrecorded_attributes = frozenset({
        "plan", "actions", "cycle", "fin_chauffe", "garde_fous", "appris", "historique", "journal", "derniere_action",
        "drapeaux", "etat_libelle", "force", "boutons", "puissance", "prise"})

    def __init__(self, b) -> None:
        super().__init__(b, "etat")

    @property
    def native_value(self) -> str:
        return self.b.etat

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        from homeassistant.helpers import entity_registry as er
        reg = er.async_get(self.hass)
        e = self.b.entry.entry_id
        snap = self.b.snapshot()
        snap["boutons"] = {
            "forcer": reg.async_get_entity_id("button", "pilotage_ballon", f"{e}_forcer"),
            "arreter": reg.async_get_entity_id("button", "pilotage_ballon", f"{e}_arreter"),
            "auto": reg.async_get_entity_id("switch", "pilotage_ballon", f"{e}_auto"),
        }
        return snap


class ProchainAllumage(BallonEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, b) -> None:
        super().__init__(b, "prochain_allumage")

    @property
    def native_value(self) -> datetime | None:
        p = self.b.plan
        if p is None or not p.besoin or p.debut is None:
            return None
        return p.debut.astimezone(timezone.utc)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"raison": self.b.plan.raison if self.b.plan else None}


class DureePrevue(BallonEntity, SensorEntity):
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, b) -> None:
        super().__init__(b, "duree_prevue")

    @property
    def native_value(self) -> int:
        return round(self.b.appris.duree(float(self.b.opt["duree_defaut"])))


class Confiance(BallonEntity, SensorEntity):
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, b) -> None:
        super().__init__(b, "confiance")

    @property
    def native_value(self) -> int:
        return round(self.b.appris.confiance() * 100)
