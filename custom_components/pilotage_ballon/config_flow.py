"""Configuration par listes déroulantes ; réglages avancés dans « Configurer »."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import CONF_NOTIF, CONF_PRISE, CONF_PUISSANCE, DOMAIN, OPTIONS_DEFAUT


def _schema_principal(d: dict[str, Any] | None = None) -> vol.Schema:
    d = d or {}

    def req(k):
        return vol.Required(k, default=d[k]) if d.get(k) else vol.Required(k)

    return vol.Schema({
        req(CONF_PRISE): selector.EntitySelector(selector.EntitySelectorConfig(domain="switch")),
        req(CONF_PUISSANCE): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor", device_class="power")),
        vol.Optional(CONF_NOTIF, description={"suggested_value": d.get(CONF_NOTIF)}): selector.EntitySelector(
            selector.EntitySelectorConfig(domain="notify")),
    })


def _nettoyer(u: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in u.items() if v not in (None, "")}


class PilotageBallonConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title="Pilotage ballon", data=_nettoyer(user_input))
        return self.async_show_form(step_id="user", data_schema=_schema_principal())

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            return self.async_update_reload_and_abort(entry, data=_nettoyer(user_input))
        return self.async_show_form(step_id="reconfigure", data_schema=_schema_principal(dict(entry.data)))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return OptionsFlowHandler()


def _schema_options(d: dict[str, Any]) -> vol.Schema:
    def num(mn, mx, st=1, u=None):
        cfg = {"min": mn, "max": mx, "step": st, "mode": selector.NumberSelectorMode.BOX}
        if u:
            cfg["unit_of_measurement"] = u
        return selector.NumberSelector(selector.NumberSelectorConfig(**cfg))

    return vol.Schema({
        vol.Required("hc_debut", default=d["hc_debut"]): selector.TimeSelector(),
        vol.Required("hc_fin", default=d["hc_fin"]): selector.TimeSelector(),
        vol.Required("marge_fin", default=d["marge_fin"]): num(0, 180, 5, "min"),
        vol.Required("marge_duree", default=d["marge_duree"]): num(1.0, 2.0, 0.05),
        vol.Required("duree_defaut", default=d["duree_defaut"]): num(30, 480, 5, "min"),
        vol.Required("seuil_marche", default=d["seuil_marche"]): num(20, 5000, 10, "W"),
        vol.Required("seuil_arret", default=d["seuil_arret"]): num(0, 1000, 5, "W"),
        vol.Required("marche_max", default=d["marche_max"]): num(60, 720, 10, "min"),
        vol.Required("couper_hp", default=d["couper_hp"]): selector.BooleanSelector(),
    })


class OptionsFlowHandler(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        erreurs: dict[str, str] = {}
        if user_input is not None:
            if float(user_input["seuil_arret"]) >= float(user_input["seuil_marche"]):
                erreurs["seuil_arret"] = "seuils"
            else:
                for k in ("marge_fin", "duree_defaut", "seuil_marche", "seuil_arret", "marche_max"):
                    user_input[k] = int(user_input[k])
                return self.async_create_entry(data=user_input)
        d = user_input or {**OPTIONS_DEFAUT, **self.config_entry.options}
        return self.async_show_form(step_id="init", data_schema=_schema_options({**OPTIONS_DEFAUT, **d}), errors=erreurs)
