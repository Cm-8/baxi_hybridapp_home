"""
Number platform for Baxi Hybrid App — Setpoint Raffrescamento (scrivibile).

Espone il set-point di raffrescamento come entità number (7-30 °C, step 1):
lettura da api.setpoint_raffrescamento_temp (metrica "Set-point raffrescamento",
già popolata dal coordinator), scrittura via PUT /data/configurationParameters
con lo stesso flusso dei setpoint sanitari (optimistic update + grazia 8s +
refresh). Automazioni: servizio nativo number.set_value (issue #9).

custom_components/baxi_hybridapp_home/number.py
"""

from __future__ import annotations

import asyncio
import logging

from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from .const import (
    DOMAIN, DATA_KEY_API,
    PARAM_ID_SETPOINT_RAFFRESCAMENTO,
    COOLING_MIN_TEMP, COOLING_MAX_TEMP,
    WRITE_GRACE_SECONDS,
)
from .device import build_device_info

_LOGGER = logging.getLogger(__name__)


class BaxiCoolingSetpointNumber(CoordinatorEntity, NumberEntity):
    """
    NumberEntity per il set-point di raffrescamento Baxi.

    Stato corrente: api.setpoint_raffrescamento_temp. Scrittura:
    PUT /data/configurationParameters con PARAM_ID_SETPOINT_RAFFRESCAMENTO.
    """

    _attr_icon = "mdi:snowflake-thermometer"
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = COOLING_MIN_TEMP
    _attr_native_max_value = COOLING_MAX_TEMP
    _attr_native_step = 1.0
    # Disabilitata di default (come i sensori energia): scrive un parametro
    # reale dell'impianto — chi la vuole la abilita consapevolmente dalla UI.
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, api) -> None:
        super().__init__(coordinator)
        self._api = api
        self._attr_unique_id = "baxi_cooling_setpoint_number"
        self._attr_name = "Setpoint Raffrescamento"

        prefix = "baxi"
        serial_number = getattr(self._api, "serialNumber", None) or "unknown"
        serial_slug = slugify(str(serial_number))
        self._attr_suggested_object_id = f"{prefix}_{serial_slug}_cooling_setpoint"

    @property
    def native_value(self) -> float | None:
        """Setpoint corrente dal cloud (None se metrica non disponibile)."""
        return getattr(self._api, "setpoint_raffrescamento_temp", None)

    @property
    def available(self) -> bool:
        """Disponibile solo se il device espone la metrica (issue #6)."""
        return getattr(self._api, "setpoint_raffrescamento_temp", None) is not None

    @property
    def device_info(self) -> dict:
        return build_device_info(self._api)

    async def async_set_native_value(self, value: float) -> None:
        """Scrive il setpoint raffrescamento su Baxi (PUT) e aggiorna l'entità."""
        # clamp 7..30 (difesa in profondità: la UI rispetta già min/max)
        new_t = max(COOLING_MIN_TEMP, min(COOLING_MAX_TEMP, float(value)))

        _LOGGER.info("🔄 Cambio setpoint raffrescamento → %s °C", new_t)
        ok = await self.hass.async_add_executor_job(
            self._api.set_configuration_parameter,
            PARAM_ID_SETPOINT_RAFFRESCAMENTO,
            int(new_t),
        )

        if not ok:
            _LOGGER.error("❌ SET setpoint raffrescamento fallita per %s °C", new_t)
            return

        # 1) Aggiorna subito in locale (optimistic UI)
        self._api.setpoint_raffrescamento_temp = new_t
        self.async_write_ha_state()

        # Logbook + evento bus per le automazioni (stesso schema dei sanitari)
        await self.hass.services.async_call(
            "logbook", "log",
            {
                "name": "Setpoint Raffrescamento",
                "message": f"impostato a {new_t:.0f}°C",
                "entity_id": self.entity_id,
            },
            blocking=False,
        )
        self.hass.bus.async_fire(
            "baxi_hybridapp_put",
            {
                "entity_id": self.entity_id,
                "mode": "raffrescamento",
                "value": new_t,
                "when": dt_util.utcnow().isoformat(),
            },
        )
        _LOGGER.info("✅ Setpoint raffrescamento impostato a %s °C", new_t)

        # 2) Refresh differito in background: questo parametro ha un ciclo di
        # read-back lento (PUT su M64P0808, la metrica letta è M64A0808
        # ri-pubblicata dal device) — la service call non resta bloccata.
        self.hass.async_create_task(self._grace_refresh())

    async def _grace_refresh(self) -> None:
        """Attende il read-back del device e riallinea dal cloud."""
        await asyncio.sleep(WRITE_GRACE_SECONDS)
        await self.coordinator.async_request_refresh()


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    api = hass.data[DOMAIN][DATA_KEY_API]
    coordinator = hass.data[DOMAIN]["coordinator"]
    async_add_entities([BaxiCoolingSetpointNumber(coordinator, api)])
