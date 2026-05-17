"""
Button platform for Baxi Hybrid App custom integration.

"""

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from .const import DOMAIN, DATA_KEY_API
import logging

_LOGGER = logging.getLogger(__name__)

UPDATE_DATA_DESCRIPTION = ButtonEntityDescription(
    key="update_data",
    name="Aggiorna",
    icon="mdi:update",
    entity_category=EntityCategory.DIAGNOSTIC,
)

class BaxiUpdateButton(ButtonEntity):
    """Pulsante diagnostico per aggiornare manualmente i dati Baxi."""

    def __init__(self, coordinator, api):
        self.entity_description = UPDATE_DATA_DESCRIPTION
        self._attr_name = "Aggiorna"
        self._attr_unique_id = "baxi_update_data_button"
        self._coordinator = coordinator
        self._api = api
        self._attr_icon = "mdi:update"

    async def async_press(self):
        """Richiamato quando l’utente preme il pulsante."""
        _LOGGER.info("🔄 Pulsante 'Aggiorna' premuto, forzo aggiornamento...")
        await self._coordinator.async_request_refresh()
        _LOGGER.info("✅ Aggiornamento Baxi completato")

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "baxi_hybridapp_home")},
            "name": "Baxi HybridApp Home",
            "manufacturer": "Baxi",
            "model": "HybridApp Home",
        }

class BaxiTestFailureButton(ButtonEntity):
    """
    Pulsante diagnostico che inietta alert simulati (FAILURE + WARNING) sui due
    binary_sensor. NON contatta la cloud Baxi. Utile per testare automazioni
    legate a baxi_hybridapp_alert e per verificare le icone/stato in dashboard.

    Gli alert simulati sopravvivono fino al prossimo polling reale (~10 min)
    o finché non vengono sovrascritti.
    """

    _attr_name = "Test Failure"
    _attr_unique_id = "baxi_test_failure_button"
    _attr_icon = "mdi:test-tube"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, api):
        self._coordinator = coordinator
        self._api = api

    async def async_press(self):
        now_ms = int(dt_util.utcnow().timestamp() * 1000)
        fakes = [
            {
                "id": f"sim-failure-{now_ms}",
                "severity": "FAILURE",
                "title": "BAXI AVVISA (simulato)",
                "description": "TEST FAILURE",
                "code": "E60",
                "start_ts": now_ms,
                "end_ts": 0,  # 0 = ancora aperto → is_active=True
            },
            {
                "id": f"sim-warning-{now_ms}",
                "severity": "WARNING",
                "title": "BAXI AVVISA (simulato)",
                "description": "TEST WARNING",
                "code": "E60",
                "start_ts": now_ms,
                "end_ts": 0,
            },
        ]

        # 1) Inietta sull'istanza API
        self._api.active_failure_alert = fakes[0]
        self._api.last_failure_alert = fakes[0]
        self._api.active_warning_alert = fakes[1]
        self._api.last_warning_alert = fakes[1]
        # Aggiunge gli id alla dedup per non rispamare al prossimo fetch.
        self._api._seen_alert_ids.add(fakes[0]["id"])
        self._api._seen_alert_ids.add(fakes[1]["id"])

        # 2) Fire event sul bus + Logbook per entrambi.
        # NOTA: l'entity_id reale viene risolto dall'entity registry tramite
        # unique_id. Non possiamo hardcodare "binary_sensor.baxi_failure_alert_active"
        # perché HA genera l'entity_id dal PRIMO `name` dell'entità, e i rename
        # successivi non lo cambiano → tipicamente "binary_sensor.avviso_failure_attivo"
        # per chi ha installato prima dei rinomi.
        ent_reg = er.async_get(self.hass)
        for fake in fakes:
            self.hass.bus.async_fire("baxi_hybridapp_alert", fake)
            unique_id = (
                "baxi_failure_alert_active" if fake["severity"] == "FAILURE"
                else "baxi_warning_alert_active"
            )
            entity_id = (
                ent_reg.async_get_entity_id("binary_sensor", DOMAIN, unique_id)
                or f"binary_sensor.{unique_id}"
            )
            code = fake.get("code")
            msg = f"{code} — {fake['description']}" if code else fake["description"]
            await self.hass.services.async_call(
                "logbook", "log",
                {
                    "name": f"Baxi {fake['severity']} (simulato)",
                    "message": msg,
                    "entity_id": entity_id,
                },
                blocking=False,
            )

        # 3) Notifica listener → binary_sensor passano a "Problema" subito
        self._coordinator.async_update_listeners()
        _LOGGER.info("🧪 Test Failure: iniettati FAILURE + WARNING simulati")

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "baxi_hybridapp_home")},
            "name": "Baxi HybridApp Home",
            "manufacturer": "Baxi",
            "model": "HybridApp Home",
        }


async def async_setup_entry(hass, entry, async_add_entities):
    """Configura le entità pulsante.

    Il pulsante 'Test Failure' è esposto SOLO se il logging DEBUG è attivo
    per il componente. Per abilitarlo, aggiungi in configuration.yaml:

        logger:
          logs:
            custom_components.baxi_hybridapp_home: debug

    poi ricarica l'integrazione (Impostazioni → Dispositivi e servizi →
    Baxi HybridApp → ⋮ → Ricarica) e il pulsante apparirà nella sezione
    Diagnostica. Disattivando il debug e ricaricando, il pulsante scompare.
    """
    api = hass.data[DOMAIN][DATA_KEY_API]
    coordinator = hass.data[DOMAIN]["coordinator"]

    buttons = [BaxiUpdateButton(coordinator, api)]
    if _LOGGER.isEnabledFor(logging.DEBUG):
        buttons.append(BaxiTestFailureButton(coordinator, api))
        _LOGGER.debug("🧪 DEBUG attivo: esposto pulsante Test Failure")

    async_add_entities(buttons, True)
