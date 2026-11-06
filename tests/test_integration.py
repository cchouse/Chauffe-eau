from datetime import timedelta

from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.pilotage_ballon.const import CONF_PRISE, CONF_PUISSANCE, DOMAIN

PRISE, PUISSANCE = "switch.ballon", "sensor.ballon_puissance"


def eid(hass, entry, domaine, cle):
    return er.async_get(hass).async_get_entity_id(domaine, DOMAIN, f"{entry.entry_id}_{cle}")


async def installer(hass, freezer, heure="2026-11-06 21:50:00+01:00", prise="on", w="0"):
    await hass.config.async_set_time_zone("Europe/Paris")
    freezer.move_to(heure)
    hass.states.async_set(PRISE, prise)
    hass.states.async_set(PUISSANCE, w, {"unit_of_measurement": "W", "device_class": "power"})
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert r["type"] is FlowResultType.FORM
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {CONF_PRISE: PRISE, CONF_PUISSANCE: PUISSANCE})
    assert r["type"] is FlowResultType.CREATE_ENTRY, r
    await hass.async_block_till_done()
    # les simulacres après l'installation : sinon la plateforme « switch » de l'intégration remplace les services
    appels = {"on": async_mock_service(hass, "switch", "turn_on"), "off": async_mock_service(hass, "switch", "turn_off"),
              "notif": async_mock_service(hass, "persistent_notification", "create")}
    return hass.config_entries.async_entries(DOMAIN)[0], appels


async def avancer(hass, freezer, entry, minutes, w=None):
    """Avance par pas d'une minute (comme la vraie boucle), avec une puissance donnée."""
    for _ in range(int(minutes)):
        if w is not None:
            hass.states.async_set(PUISSANCE, str(w), {"unit_of_measurement": "W", "device_class": "power"})
        freezer.tick(timedelta(minutes=1))
        await entry.runtime_data._tick(None)
    await hass.async_block_till_done()


async def bascule(hass, entry, cle="auto", on=True):
    """Active l'allumage automatique (directement : les services switch sont simulés dans ces tests)."""
    await entry.runtime_data.definir_drapeau(cle, on)
    await hass.async_block_till_done()


def fiable(entry, duree=180.0, n=5):
    for _ in range(n):
        entry.runtime_data.appris.ajouter(duree, duree * 30)


async def test_installation_et_entites(hass, freezer):
    entry, _ = await installer(hass, freezer)
    for d, c in (("sensor", "etat"), ("sensor", "prochain_allumage"), ("sensor", "duree_prevue"), ("sensor", "confiance"),
                 ("switch", "auto"), ("button", "forcer"), ("button", "arreter")):
        assert eid(hass, entry, d, c), c
    assert hass.states.get(eid(hass, entry, "switch", "auto")).state == "off"      # mode conseil par défaut
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert r["type"] is FlowResultType.ABORT                                       # une seule instance


async def test_formulaires_serialisables_comme_l_interface(hass, freezer):
    import voluptuous_serialize
    from homeassistant.helpers import config_validation as cv
    entry, _ = await installer(hass, freezer)
    r = await hass.config_entries.options.async_init(entry.entry_id)
    voluptuous_serialize.convert(r["data_schema"], custom_serializer=cv.custom_serializer)
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "reconfigure", "entry_id": entry.entry_id})
    voluptuous_serialize.convert(r["data_schema"], custom_serializer=cv.custom_serializer)


async def test_seuils_incoherents_refuses(hass, freezer):
    entry, _ = await installer(hass, freezer)
    r = await hass.config_entries.options.async_init(entry.entry_id)
    donnees = {"hc_debut": "22:00:00", "hc_fin": "06:00:00", "marge_fin": 30, "marge_duree": 1.15, "duree_defaut": 240,
               "seuil_marche": 100, "seuil_arret": 200, "marche_max": 360, "couper_hp": False}
    r = await hass.config_entries.options.async_configure(r["flow_id"], donnees)
    assert r["type"] is FlowResultType.FORM and r["errors"]


async def test_detection_d_une_chauffe_duree_et_energie(hass, freezer):
    entry, _ = await installer(hass, freezer, heure="2026-11-06 22:00:00+01:00")
    await avancer(hass, freezer, entry, 30, w=0)
    await avancer(hass, freezer, entry, 180, w=2000)                 # 3 h de chauffe à 2 kW
    assert entry.runtime_data.etat == "chauffe"
    await avancer(hass, freezer, entry, 10, w=0)                     # le thermostat coupe
    assert entry.runtime_data.etat == "repos"
    j = entry.runtime_data.journal[-1]
    assert 175 <= j["duree_min"] <= 182 and j["principal"] and j["source"] == "thermostat"
    assert 5600 <= j["wh"] <= 6400                                   # ≈ 6 kWh
    assert len(entry.runtime_data.appris.durees) == 1


async def test_un_appoint_court_n_apprend_pas(hass, freezer):
    entry, _ = await installer(hass, freezer, heure="2026-11-06 01:00:00+01:00")
    await avancer(hass, freezer, entry, 30, w=0)
    await avancer(hass, freezer, entry, 10, w=2000)                  # 10 min : un appoint
    await avancer(hass, freezer, entry, 10, w=0)
    assert not entry.runtime_data.appris.durees and not entry.runtime_data.journal[-1]["principal"]


async def test_repli_puis_allumage_decale(hass, freezer):
    entry, _ = await installer(hass, freezer)
    p = entry.runtime_data
    assert p.plan.repli and p.plan.debut.strftime("%H:%M") == "22:00"          # rien appris : dès le début
    assert "pas encore observé" in p.plan.raison
    fiable(entry, 180.0)
    await avancer(hass, freezer, entry, 1)
    assert not p.plan.repli
    # fin visée 05:30, durée 180 × 1,15 = 207 min : allumage à 02:03
    assert p.plan.debut.strftime("%H:%M") == "02:03" and p.plan.fin_cible.strftime("%H:%M") == "05:30"
    assert "02:03" in p.plan.raison and "05:30" in p.plan.raison
    assert hass.states.get(eid(hass, entry, "sensor", "duree_prevue")).state == "180"


async def test_mode_conseil_ne_touche_pas_a_la_prise(hass, freezer):
    entry, appels = await installer(hass, freezer, heure="2026-11-06 21:58:00+01:00")
    fiable(entry)
    await avancer(hass, freezer, entry, 300)
    assert appels["on"] == [] and appels["off"] == []


async def test_mode_automatique_eteint_puis_allume_au_bon_moment(hass, freezer):
    entry, appels = await installer(hass, freezer, heure="2026-11-06 21:58:00+01:00", prise="on")
    fiable(entry)
    await bascule(hass, entry)
    await avancer(hass, freezer, entry, 5)                           # 22:03 : début des heures creuses
    assert len(appels["off"]) == 1                                   # la prise reste éteinte
    hass.states.async_set(PRISE, "off")
    await avancer(hass, freezer, entry, 100)                         # 23:43
    assert appels["on"] == []
    await avancer(hass, freezer, entry, 25)                          # 00:08… toujours avant 02:03
    assert appels["on"] == []
    await avancer(hass, freezer, entry, 120)                         # 02:08 : c'est l'heure
    assert len(appels["on"]) == 1
    assert any("prise allumée" in a.data["message"] for a in appels["notif"])


async def test_actions_ecrites(hass, freezer):
    entry, _ = await installer(hass, freezer, heure="2026-11-06 21:58:00+01:00")
    fiable(entry)
    await avancer(hass, freezer, entry, 1)
    p = entry.runtime_data
    txt = " | ".join(a["heure"] + " " + a["texte"] for a in p.plan.actions)
    assert "22:00" in txt and "02:03" in txt and "05:03" in txt and "06:00" in txt
    assert "mode conseil" in txt                                     # en conseil : c'est à moi de le faire
    await bascule(hass, entry)
    txt = " | ".join(a["texte"] for a in p.plan.actions)
    assert "La prise reste éteinte jusqu'à 02:03" in txt and "J'allume la prise" in txt


async def test_forcer_puis_fin_de_chauffe(hass, freezer):
    entry, appels = await installer(hass, freezer, heure="2026-11-06 18:00:00+01:00", prise="off")
    await hass.services.async_call("button", "press", {"entity_id": eid(hass, entry, "button", "forcer")}, blocking=True)
    assert len(appels["on"]) == 1 and entry.runtime_data.force
    hass.states.async_set(PRISE, "on")
    await avancer(hass, freezer, entry, 5, w=2000)
    await avancer(hass, freezer, entry, 60, w=2000)
    assert entry.runtime_data.etat == "chauffe" and entry.runtime_data.force
    await avancer(hass, freezer, entry, 10, w=0)
    assert entry.runtime_data.force is None                          # le thermostat a coupé : fin du forçage
    assert not entry.runtime_data.journal[-1]["principal"]           # un forçage ne fausse pas l'apprentissage
    assert entry.runtime_data.journal[-1]["source"] == "force"


async def test_forcer_alors_que_le_ballon_est_deja_chaud(hass, freezer):
    entry, appels = await installer(hass, freezer, heure="2026-11-06 18:00:00+01:00", prise="off")
    await hass.services.async_call("button", "press", {"entity_id": eid(hass, entry, "button", "forcer")}, blocking=True)
    hass.states.async_set(PRISE, "on")
    await avancer(hass, freezer, entry, 35, w=0)                     # la puissance ne monte pas
    assert entry.runtime_data.force is None
    assert "déjà chaud" in entry.runtime_data.derniere_action["raison"]


async def test_arreter_annule_l_allumage_de_la_nuit(hass, freezer):
    entry, appels = await installer(hass, freezer, heure="2026-11-06 23:00:00+01:00", prise="on")
    fiable(entry)
    await bascule(hass, entry)
    await avancer(hass, freezer, entry, 1)
    hass.states.async_set(PRISE, "off")
    await hass.services.async_call("button", "press", {"entity_id": eid(hass, entry, "button", "arreter")}, blocking=True)
    nb = len(appels["on"])
    await avancer(hass, freezer, entry, 240)                         # on dépasse 02:03
    assert len(appels["on"]) == nb                                   # annulé pour cette nuit


async def test_securite_duree_maximale(hass, freezer):
    entry, appels = await installer(hass, freezer, heure="2026-11-06 12:00:00+01:00", prise="on")
    await hass.services.async_call("button", "press", {"entity_id": eid(hass, entry, "button", "forcer")}, blocking=True)
    await avancer(hass, freezer, entry, 370, w=2000)
    assert len(appels["off"]) >= 1
    assert any("sécurité" in a.data["message"] for a in appels["notif"])


async def test_la_correction_avance_l_allumage_si_la_nuit_deborde(hass, freezer):
    entry, appels = await installer(hass, freezer, heure="2026-11-06 22:00:00+01:00", prise="on")
    fiable(entry)
    p = entry.runtime_data
    await avancer(hass, freezer, entry, 200, w=0)
    await avancer(hass, freezer, entry, 360, w=2000)                 # chauffe de 01:20 à 07:20 : déborde des heures creuses
    await avancer(hass, freezer, entry, 10, w=0)
    assert p.appris.ajustement == 20.0


async def test_persistance(hass, freezer):
    entry, _ = await installer(hass, freezer)
    fiable(entry)
    await bascule(hass, entry)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert len(entry.runtime_data.appris.durees) == 5 and entry.runtime_data.drapeaux["auto"]


async def test_carte_servie(hass, freezer, hass_client):
    from homeassistant.setup import async_setup_component
    assert await async_setup_component(hass, "http", {})
    entry, _ = await installer(hass, freezer)
    c = await hass_client()
    r = await c.get("/pilotage_ballon/pilotage-ballon-card.js")
    assert r.status == 200


async def test_fichiers_json_valides():
    import json, pathlib
    base = pathlib.Path(__file__).parent.parent / "custom_components" / "pilotage_ballon"
    for f in list(base.glob("translations/*.json")) + [base / "manifest.json"]:
        json.loads(f.read_text(encoding="utf-8"))
