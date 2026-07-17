"""
Select platform for Baxi Hybrid App — Modo Impianto e Modo Stagione.

Modo Impianto: Automatico / Solo Sanitario / Standby (stato da api.system_mode).
Modo Stagione: Estate / Inverno / Estate/Inverno automatico / Estate/Inverno
remoto (stato da api.season_mode, metrica "Modo Stagione").

La scrittura usa PUT /data/commands?commandId=...&thingId=... con body vuoto.

custom_components/baxi_hybridapp_home/select.py
"""

import asyncio
import logging

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import (
    DOMAIN, DATA_KEY_API,
    WRITE_GRACE_SECONDS,
    COMMAND_ID_MODE_AUTOMATICO,
    COMMAND_ID_MODE_SOLO_SANITARIO,
    COMMAND_ID_MODE_STANDBY,
    COMMAND_ID_SEASON_ESTATE,
    COMMAND_ID_SEASON_INVERNO,
    COMMAND_ID_SEASON_AUTOMATICO,
    COMMAND_ID_SEASON_REMOTO,
)
from .device import build_device_info

_LOGGER = logging.getLogger(__name__)

# Mapping opzione leggibile → commandId Servitly
_MODE_TO_COMMAND: dict[str, str] = {
    "Automatico":     COMMAND_ID_MODE_AUTOMATICO,
    "Solo Sanitario": COMMAND_ID_MODE_SOLO_SANITARIO,
    "Standby":        COMMAND_ID_MODE_STANDBY,
}

MODE_OPTIONS: list[str] = list(_MODE_TO_COMMAND.keys())

# Le opzioni devono combaciare con le stringhe prodotte dal mapper della
# metrica "Modo Stagione" (season_mode in metrics.py: 0001-0004).
_SEASON_TO_COMMAND: dict[str, str] = {
    "Estate":                    COMMAND_ID_SEASON_ESTATE,
    "Inverno":                   COMMAND_ID_SEASON_INVERNO,
    "Estate/Inverno automatico": COMMAND_ID_SEASON_AUTOMATICO,
    "Estate/Inverno remoto":     COMMAND_ID_SEASON_REMOTO,
}

SEASON_OPTIONS: list[str] = list(_SEASON_TO_COMMAND.keys())


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
        return build_device_info(self._api)

    async def async_select_option(self, option: str) -> None:
        """Invia il comando di cambio modalità al device Baxi."""
        command_id = _MODE_TO_COMMAND.get(option)
        if command_id is None:
            _LOGGER.warning("⚠️ Opzione modo impianto '%s' non riconosciuta.", option)
            return

        _LOGGER.info("🔄 Cambio modo impianto → %s (commandId: %s)", option, command_id)
        ok = await self.hass.async_add_executor_job(
            self._api.send_command,
            command_id,
        )

        if ok:
            _LOGGER.info("✅ Modo impianto impostato a '%s'", option)
            # Optimistic: la UI mostra subito la nuova modalità. Il refresh
            # arriva dopo la grazia, quando il device ha ri-pubblicato la
            # metrica (read-back) — senza bloccare la service call.
            self._api.system_mode = option
            self.async_write_ha_state()
            self.hass.async_create_task(self._grace_refresh())
        else:
            _LOGGER.error("❌ Cambio modo impianto fallito per '%s'", option)

    async def _grace_refresh(self) -> None:
        """Attende il read-back del device e riallinea dal cloud."""
        await asyncio.sleep(WRITE_GRACE_SECONDS)
        await self.coordinator.async_request_refresh()


class BaxiSeasonModeSelect(CoordinatorEntity, SelectEntity):
    """
    SelectEntity per il modo stagione Baxi.

    Stato corrente: letto da api.season_mode (valori "Estate", "Inverno",
    "Estate/Inverno automatico", "Estate/Inverno remoto"). Scrittura:
    PUT /data/commands con il commandId corrispondente all'opzione.
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
        """Restituisce la stagione corrente se riconosciuta, altrimenti None."""
        val = getattr(self._api, "season_mode", None)
        return val if val in _SEASON_TO_COMMAND else None

    @property
    def available(self) -> bool:
        """Disponibile quando l'API ha restituito un valore per season_mode."""
        return getattr(self._api, "season_mode", None) is not None

    @property
    def device_info(self) -> dict:
        return build_device_info(self._api)

    async def async_select_option(self, option: str) -> None:
        """Invia il comando di cambio stagione al device Baxi."""
        command_id = _SEASON_TO_COMMAND.get(option)
        if command_id is None:
            _LOGGER.warning("⚠️ Opzione modo stagione '%s' non riconosciuta.", option)
            return

        _LOGGER.info("🔄 Cambio modo stagione → %s (commandId: %s)", option, command_id)
        ok = await self.hass.async_add_executor_job(
            self._api.send_command,
            command_id,
        )

        if ok:
            _LOGGER.info("✅ Modo stagione impostato a '%s'", option)
            # Optimistic + refresh differito, come per il modo impianto.
            self._api.season_mode = option
            self.async_write_ha_state()
            self.hass.async_create_task(self._grace_refresh())
        else:
            _LOGGER.error("❌ Cambio modo stagione fallito per '%s'", option)

    async def _grace_refresh(self) -> None:
        """Attende il read-back del device e riallinea dal cloud."""
        await asyncio.sleep(WRITE_GRACE_SECONDS)
        await self.coordinator.async_request_refresh()


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    api = hass.data[DOMAIN][DATA_KEY_API]
    coordinator = hass.data[DOMAIN]["coordinator"]
    async_add_entities([
        BaxiSystemModeSelect(coordinator, api),
        BaxiSeasonModeSelect(coordinator, api),
    ])
