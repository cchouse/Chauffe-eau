from __future__ import annotations

from homeassistant.components.button import ButtonEntity

from .entity import BallonEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    b = entry.runtime_data
    async_add_entities([Forcer(b), Arreter(b)])


class Forcer(BallonEntity, ButtonEntity):
    def __init__(self, b) -> None:
        super().__init__(b, "forcer")

    async def async_press(self) -> None:
        await self.b.forcer()


class Arreter(BallonEntity, ButtonEntity):
    def __init__(self, b) -> None:
        super().__init__(b, "arreter")

    async def async_press(self) -> None:
        await self.b.arreter()
