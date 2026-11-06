"""Pilotage ballon : décale l'allumage du chauffe-eau en heures creuses pour qu'il soit chaud juste avant leur fin."""
from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, URL_CARTE, VERSION
from .runtime import Ballon

PLATFORMS = ["sensor", "switch", "button"]
type BallonConfigEntry = ConfigEntry[Ballon]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    chemin = Path(__file__).parent / "www" / "pilotage-ballon-card.js"
    await hass.http.async_register_static_paths([StaticPathConfig(URL_CARTE, str(chemin), False)])
    add_extra_js_url(hass, f"{URL_CARTE}?v={VERSION}")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: BallonConfigEntry) -> bool:
    ballon = Ballon(hass, entry)
    await ballon.async_demarrer()
    entry.runtime_data = ballon
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_recharger))
    return True


async def _recharger(hass: HomeAssistant, entry: BallonConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: BallonConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        await entry.runtime_data.async_arreter()
    return ok
