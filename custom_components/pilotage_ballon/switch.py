from __future__ import annotations

from homeassistant.components.switch import SwitchEntity

from .entity import BallonEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    async_add_entities([Auto(entry.runtime_data)])


class Auto(BallonEntity, SwitchEntity):
    """Allumage automatique : désactivé par défaut (mode conseil)."""

    def __init__(self, b) -> None:
        super().__init__(b, "auto")

    @property
    def is_on(self) -> bool:
        return self.b.drapeaux["auto"]

    async def async_turn_on(self, **kwargs) -> None:
        await self.b.definir_drapeau("auto", True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.b.definir_drapeau("auto", False)
