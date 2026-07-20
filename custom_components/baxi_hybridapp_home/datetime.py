"""
Datetime platform for Baxi Hybrid App custom integration for Home Assistant.

custom_components/baxi_hybridapp_home/datetime.py
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from homeassistant.components.datetime import DateTimeEntity

from .const import (
    DOMAIN, DATA_KEY_API,
    PARAM_ID_HOLIDAY_MODE_END,
    WRITE_GRACE_SECONDS,
)
from .device import build_device_info

_LOGGER = logging.getLogger(__name__)


class BaxiHolidayModeEnd(DateTimeEntity):
    """Data/ora fine modo vacanza: scrivibile per attivare/disattivare la vacanza."""

    _attr_name = "Modo Vacanza Fine"
    _attr_unique_id = "baxi_holiday_mode_end"

    def __init__(self, coordinator, api):
        self._api = api
        self._coordinator = coordinator

    @property
    def native_value(self) -> datetime | None:
        """Legge la data di fine dal sensore (epoch ms convertito a datetime)."""
        val = getattr(self._api, "holiday_mode_end", None)
        if isinstance(val, datetime):
            return val
        return None

    async def async_set_value(self, value: datetime) -> None:
        """Imposta la data di fine modo vacanza (o disattiva se nel passato)."""
        if value is None:
            return

        # Converte il datetime in epoch millisecondi
        epoch_ms = int(value.timestamp() * 1000)

        _LOGGER.info(
            "🏖️ Modo vacanza fine → %s (epoch_ms: %d)",
            value.isoformat(),
            epoch_ms,
        )

        ok = await self.hass.async_add_executor_job(
            self._api.set_configuration_parameter,
            PARAM_ID_HOLIDAY_MODE_END,
            epoch_ms,
        )

        if ok:
            _LOGGER.info("✅ Modo vacanza fine impostato a '%s'", value.isoformat())

            # Optimistic: aggiorna subito in locale
            self._api.holiday_mode_end = value
            self.async_write_ha_state()

            # Logbook entry
            await self.hass.services.async_call(
                "logbook",
                "log",
                {
                    "name": "Modo Vacanza",
                    "message": f"fine impostata a {value.isoformat()}",
                    "entity_id": self.entity_id,
                },
                blocking=False,
            )

            # Refresh differito in background
            self.hass.async_create_task(self._grace_refresh())
        else:
            _LOGGER.error("❌ Impostazione modo vacanza fine fallita")

    async def _grace_refresh(self) -> None:
        """Attende il read-back del device e riallinea dal cloud."""
        await asyncio.sleep(WRITE_GRACE_SECONDS)
        await self._coordinator.async_request_refresh()

    @property
    def device_info(self):
        return build_device_info(self._api)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Setup datetime entities."""
    api = hass.data[DOMAIN][DATA_KEY_API]
    coordinator = hass.data[DOMAIN]["coordinator"]

    async_add_entities([BaxiHolidayModeEnd(coordinator, api)])
