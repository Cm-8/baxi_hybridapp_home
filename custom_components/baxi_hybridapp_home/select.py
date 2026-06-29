"""
Select platform for Baxi Hybrid App — Modo Impianto e Modo Stagione.

BaxiSystemModeSelect: Automatico / Solo Sanitario / Standby
BaxiSeasonModeSelect: Estate / Inverno / E-I Automatico / E-I Remoto

La lettura avviene tramite api.system_mode / api.season_mode (populate
dal coordinator). La scrittura usa PUT /data/commands con il commandId.

custom_components/baxi_hybridapp_home/select.py
"""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import (
    DOMAIN, DATA_KEY_API,
    COMMAND_ID_MODE_AUTOMATICO,
    COMMAND_ID_MODE_SOLO_SANITARIO,
    COMMAND_ID_MODE_STANDBY,
    COMMAND_ID_SEASON_ESTATE,
    COMMAND_ID_SEASON_INVERNO,
    COMMAND_ID_SEASON_AUTOMATICO,
    COMMAND_ID_SEASON_REMOTO,
)

_LOGGER = logging.getLogger(__name__)

# Mapping opzione leggibile → commandId Servitly
_MODE_TO_COMMAND: dict[str, str] = {
    "Automatico":     COMMAND_ID_MODE_AUTOMATICO,
    "Solo Sanitario": COMMAND_ID_MODE_SOLO_SANITARIO,
    "Standby":        COMMAND_ID_MODE_STANDBY,
}

MODE_OPTIONS: list[str] = list(_MODE_TO_COMMAND.keys())


class BaxiSystemModeSelect(CoordinatorEntity, SelectEntity):
    """
    SelectEntity per il modo impianto Baxi.

    Stato corrente: letto da api.system_mode (valori "Automatico",
    "Solo Sanitario", "Standby"). Scrittura: PUT /data/commands con il
    commandId corrispondente all'opzione selezionata.
    """

    _attr_icon = "mdi:tune"
    _attr_options = MODE_OPTIONS

    def __init__(self, coordinator, api) -> None:
        super().__init__(coordinator)
        self._api = api
        self._attr_unique_id = "baxi_system_mode_select"
        self._attr_name = "Modo Impianto"

        prefix = "baxi"
        serial_number = getattr(self._api, "serialNumber", None) or "unknown"
        serial_slug = slugify(str(serial_number))
        self._attr_suggested_object_id = f"{prefix}_{serial_slug}_system_mode_select"

    @property
    def current_option(self) -> str | None:
        """Restituisce la modalità corrente se riconosciuta, altrimenti None."""
        val = getattr(self._api, "system_mode", None)
        return val if val in _MODE_TO_COMMAND else None

    @property
    def available(self) -> bool:
        """Disponibile quando l'API ha restituito un valore per system_mode."""
        return getattr(self._api, "system_mode", None) is not None

    @property
    def device_info(self) -> dict:
        return {
            "identifiers": {(DOMAIN, "baxi_hybridapp_home")},
            "name": "Baxi HybridApp Home",
            "manufacturer": "Baxi",
            "model": getattr(self._api, "thingModel", None) or "HybridApp",
            "model_id": getattr(self._api, "thingModel", None),
            "serial_number": getattr(self._api, "serialNumber", None),
            "hw_version": "n.d.",
            "sw_version": getattr(self._api, "thingFirmware", None),
            "configuration_url": "https://altuofianco.baxi.it/login",
        }

    async def async_select_option(self, option: str) -> None:
        """Invia il comando di cambio modalità al device Baxi."""
        command_id = _MODE_TO_COMMAND.get(option)
        if command_id is None:
            _LOGGER.warning(
                "⚠️ Opzione modo impianto '%s' non riconosciuta.", option)
            return

        _LOGGER.info("🔄 Cambio modo impianto → %s (commandId: %s)",
                     option, command_id)
        ok = await self.hass.async_add_executor_job(
            self._api.send_command,
            command_id,
        )

        if ok:
            _LOGGER.info("✅ Modo impianto impostato a '%s'", option)
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("❌ Cambio modo impianto fallito per '%s'", option)


# ---------------------------------------------------------------------------
# Modo Stagione
# ---------------------------------------------------------------------------

_SEASON_TO_COMMAND: dict[str, str] = {
    "Estate":                COMMAND_ID_SEASON_ESTATE,
    "Inverno":               COMMAND_ID_SEASON_INVERNO,
    "Estate/Inverno automatico": COMMAND_ID_SEASON_AUTOMATICO,
    "Estate/Inverno remoto": COMMAND_ID_SEASON_REMOTO,
}

SEASON_OPTIONS: list[str] = list(_SEASON_TO_COMMAND.keys())


class BaxiSeasonModeSelect(CoordinatorEntity, SelectEntity):
    """
    SelectEntity per il modo stagione Baxi.

    Stato corrente: letto da api.season_mode (valori "Inverno", "Estate",
    "Estate/Inverno automatico", "Estate/Inverno remoto").
    Scrittura: PUT /data/commands con il commandId corrispondente.
    """

    _attr_icon = "mdi:sun-snowflake"
    _attr_options = SEASON_OPTIONS

    def __init__(self, coordinator, api) -> None:
        super().__init__(coordinator)
        self._api = api
        self._attr_unique_id = "baxi_season_mode_select"
        self._attr_name = "Modo Stagione"

        prefix = "baxi"
        serial_number = getattr(self._api, "serialNumber", None) or "unknown"
        serial_slug = slugify(str(serial_number))
        self._attr_suggested_object_id = f"{prefix}_{serial_slug}_season_mode_select"

    @property
    def current_option(self) -> str | None:
        val = getattr(self._api, "season_mode", None)
        return val if val in _SEASON_TO_COMMAND else None

    @property
    def available(self) -> bool:
        return getattr(self._api, "season_mode", None) is not None

    @property
    def device_info(self) -> dict:
        return {
            "identifiers": {(DOMAIN, "baxi_hybridapp_home")},
            "name": "Baxi HybridApp Home",
            "manufacturer": "Baxi",
            "model": getattr(self._api, "thingModel", None) or "HybridApp",
            "model_id": getattr(self._api, "thingModel", None),
            "serial_number": getattr(self._api, "serialNumber", None),
            "hw_version": "n.d.",
            "sw_version": getattr(self._api, "thingFirmware", None),
            "configuration_url": "https://altuofianco.baxi.it/login",
        }

    async def async_select_option(self, option: str) -> None:
        command_id = _SEASON_TO_COMMAND.get(option)
        if command_id is None:
            _LOGGER.warning(
                "⚠️ Opzione modo stagione '%s' non riconosciuta.", option)
            return

        _LOGGER.info("🔄 Cambio modo stagione → %s (commandId: %s)",
                     option, command_id)
        ok = await self.hass.async_add_executor_job(
            self._api.send_command,
            command_id,
        )

        if ok:
            _LOGGER.info("✅ Modo stagione impostato a '%s'", option)
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("❌ Cambio modo stagione fallito per '%s'", option)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    api = hass.data[DOMAIN][DATA_KEY_API]
    coordinator = hass.data[DOMAIN]["coordinator"]
    async_add_entities([
        BaxiSystemModeSelect(coordinator, api),
        BaxiSeasonModeSelect(coordinator, api),
    ])
