"""
Button platform for Baxi Hybrid App custom integration.

"""

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.helpers.entity import EntityCategory
from .const import DOMAIN, DATA_KEY_API
import logging

_LOGGER = logging.getLogger(__name__)

UPDATE_DATA_DESCRIPTION = ButtonEntityDescription(
    key="update_data",
    name="Aggiorna dati Baxi",
    icon="mdi:update",
    entity_category=EntityCategory.DIAGNOSTIC,
)

class BaxiUpdateButton(ButtonEntity):
    """Pulsante diagnostico per aggiornare manualmente i dati Baxi."""

    def __init__(self, coordinator, api):
        self.entity_description = UPDATE_DATA_DESCRIPTION
        self._attr_name = "Aggiorna dati Baxi"
        self._attr_unique_id = "baxi_update_data_button"
        self._coordinator = coordinator
        self._api = api
        self._attr_icon = "mdi:update"

    async def async_press(self):
        """Richiamato quando l’utente preme il pulsante."""
        _LOGGER.info("🔄 Pulsante 'Aggiorna dati Baxi' premuto, forzo aggiornamento...")
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

async def async_setup_entry(hass, entry, async_add_entities):
    """Configura l'entità pulsante."""
    api = hass.data[DOMAIN][DATA_KEY_API]
    coordinator = hass.data[DOMAIN]["coordinator"]

    async_add_entities([BaxiUpdateButton(coordinator, api)], True)
