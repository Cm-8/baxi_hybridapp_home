"""
Datetime platform for Baxi Hybrid App custom integration for Home Assistant.

Entità "Modo Vacanza Fine": data/ora di fine vacanza.

Comportamento in base allo stato della vacanza (come nell'app Baxi):
- vacanza SPENTA → impostare la data la mette in SOLO staging locale
  (hass.data[DOMAIN][HOLIDAY_STAGED_KEY]); l'invio effettivo avviene quando si
  attiva lo switch "Modo Vacanza". Evita attivazioni accidentali.
- vacanza ATTIVA → impostare la data la invia SUBITO (estendi/accorcia il
  periodo), perché a vacanza in corso cambiare la fine è un'azione voluta.

custom_components/baxi_hybridapp_home/datetime.py
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from homeassistant.components.datetime import DateTimeEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN, DATA_KEY_API,
    PARAM_ID_HOLIDAY_MODE_END,
    HOLIDAY_STAGED_KEY,
    WRITE_GRACE_SECONDS,
)
from .device import build_device_info

_LOGGER = logging.getLogger(__name__)


class BaxiHolidayModeEnd(CoordinatorEntity, DateTimeEntity):
    """Data/ora fine modo vacanza — staging se spenta, invio diretto se attiva."""

    _attr_name = "Modo Vacanza Fine"
    _attr_unique_id = "baxi_holiday_mode_end"
    _attr_icon = "mdi:calendar-end"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, api) -> None:
        super().__init__(coordinator)
        self._api = api

    @property
    def native_value(self) -> datetime | None:
        """Mostra la data in staging se presente, altrimenti quella dal cloud."""
        staged = self.hass.data[DOMAIN].get(HOLIDAY_STAGED_KEY)
        if isinstance(staged, datetime):
            return staged
        val = getattr(self._api, "holiday_mode_end", None)
        return val if isinstance(val, datetime) else None

    async def async_set_value(self, value: datetime) -> None:
        """Staging se la vacanza è spenta, invio diretto se è già attiva."""
        if value is None:
            return

        active = (getattr(self._api, "holiday_mode", None) or "").lower() == "on"

        if not active:
            # Vacanza spenta: memorizza in locale, nessun invio al cloud.
            self.hass.data[DOMAIN][HOLIDAY_STAGED_KEY] = value
            _LOGGER.info(
                "🏖️ Data fine vacanza in staging: %s — attiva lo switch "
                "'Modo Vacanza' per applicare",
                value.isoformat(),
            )
            self.async_write_ha_state()
            return

        # Vacanza già attiva: applica subito la nuova data (estendi/accorcia).
        epoch_ms = int(value.timestamp() * 1000)
        _LOGGER.info(
            "🏖️ Aggiorno fine vacanza (attiva) → %s (epoch_ms: %d)",
            value.isoformat(), epoch_ms,
        )

        ok = await self.hass.async_add_executor_job(
            self._api.set_configuration_parameter,
            PARAM_ID_HOLIDAY_MODE_END,
            epoch_ms,
        )

        if ok:
            _LOGGER.info("✅ Fine vacanza aggiornata a %s", value.isoformat())
            # Optimistic + pulizia di un eventuale staging residuo.
            self._api.holiday_mode_end = value
            self.hass.data[DOMAIN][HOLIDAY_STAGED_KEY] = None
            self.async_write_ha_state()
            await self._log(f"fine aggiornata a {value.isoformat()}")
            self.hass.async_create_task(self._grace_refresh())
        else:
            _LOGGER.error("❌ Aggiornamento fine vacanza fallito")

    async def _log(self, message: str) -> None:
        """Scrive una entry nel Logbook."""
        await self.hass.services.async_call(
            "logbook",
            "log",
            {
                "name": "Modo Vacanza",
                "message": message,
                "entity_id": self.entity_id,
            },
            blocking=False,
        )

    async def _grace_refresh(self) -> None:
        """Attende il read-back del device e riallinea dal cloud."""
        await asyncio.sleep(WRITE_GRACE_SECONDS)
        await self.coordinator.async_request_refresh()

    @property
    def device_info(self):
        return build_device_info(self._api)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Setup datetime entities."""
    api = hass.data[DOMAIN][DATA_KEY_API]
    coordinator = hass.data[DOMAIN]["coordinator"]

    async_add_entities([BaxiHolidayModeEnd(coordinator, api)])
