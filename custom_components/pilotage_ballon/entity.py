from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .runtime import Ballon


class BallonEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, b: Ballon, cle: str) -> None:
        self.b = b
        self._attr_translation_key = cle
        self._attr_unique_id = f"{b.entry.entry_id}_{cle}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, b.entry.entry_id)}, name="Pilotage ballon",
                                            manufacturer="B-Home", model="Pilotage ballon")

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(async_dispatcher_connect(self.hass, self.b.signal, self._maj))

    @callback
    def _maj(self) -> None:
        self.async_write_ha_state()
