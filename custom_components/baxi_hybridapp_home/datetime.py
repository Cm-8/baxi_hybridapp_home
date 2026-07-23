"""
Datetime platform for Baxi Hybrid App custom integration for Home Assistant.

Entità "Modo Vacanza Fine": data/ora di fine vacanza in SOLO staging locale.
Impostare un valore qui NON invia nulla al cloud — memorizza soltanto la data
desiderata (in hass.data[DOMAIN]). L'invio effettivo avviene quando si attiva
lo switch "Modo Vacanza" (switch.py), esattamente come il flag on/off dell'app
Baxi: prima imposti la data, poi confermi con l'interruttore.

custom_components/baxi_hybridapp_home/datetime.py
"""

from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.components.datetime import DateTimeEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DATA_KEY_API, HOLIDAY_STAGED_KEY
from .device import build_device_info

_LOGGER = logging.getLogger(__name__)


class BaxiHolidayModeEnd(CoordinatorEntity, DateTimeEntity):
    """Data/ora fine modo vacanza — solo staging locale (no invio diretto)."""

    _attr_name = "Modo Vacanza Fine"
    _attr_unique_id = "baxi_holiday_mode_end"
    _attr_icon = "mdi:calendar-end"

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
        """Memorizza la data in locale (staging) — nessun invio al cloud."""
        self.hass.data[DOMAIN][HOLIDAY_STAGED_KEY] = value
        _LOGGER.info(
            "🏖️ Data fine vacanza in staging: %s — attiva lo switch "
            "'Modo Vacanza' per applicare",
            value.isoformat() if value else None,
        )
        self.async_write_ha_state()

    @property
    def device_info(self):
        return build_device_info(self._api)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Setup datetime entities."""
    api = hass.data[DOMAIN][DATA_KEY_API]
    coordinator = hass.data[DOMAIN]["coordinator"]

    async_add_entities([BaxiHolidayModeEnd(coordinator, api)])
