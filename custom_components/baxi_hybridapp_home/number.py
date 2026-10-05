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
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from .const import (
    DOMAIN,
    PARAM_ID_BOOST_MAX_DURATION,
    PARAM_ID_SETPOINT_RAFFRESCAMENTO,
    BOOST_MIN_MINUTES, BOOST_MAX_MINUTES,
    COOLING_MIN_TEMP, COOLING_MAX_TEMP,
    WRITE_GRACE_SECONDS,
)
from .device import async_add_provided_entities, build_device_info

_LOGGER = logging.getLogger(__name__)

# Scritture verso il device: una alla volta.
PARALLEL_UPDATES = 1


class BaxiCoolingSetpointNumber(CoordinatorEntity, NumberEntity):
    """
    NumberEntity per il set-point di raffrescamento Baxi.

    Stato corrente: api.setpoint_raffrescamento_temp. Scrittura:
    PUT /data/configurationParameters con PARAM_ID_SETPOINT_RAFFRESCAMENTO.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "cooling_setpoint"
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = COOLING_MIN_TEMP
    _attr_native_max_value = COOLING_MAX_TEMP
    _attr_native_step = 1.0
    # Disabilitata di default (come i sensori energia): scrive un parametro
    # reale dell'impianto — chi la vuole la abilita consapevolmente dalla UI.
    _attr_entity_registry_enabled_default = False
    _source_attr = "setpoint_raffrescamento_temp"

    def __init__(self, coordinator, api) -> None:
        super().__init__(coordinator)
        self._api = api
        self._attr_unique_id = "baxi_cooling_setpoint_number"

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
        """Disponibile se il cloud risponde e il device espone la metrica (issue #6)."""
        return super().available and getattr(self._api, "setpoint_raffrescamento_temp", None) is not None

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
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cooling_setpoint_failed",
                translation_placeholders={"value": f"{new_t:.0f}"},
            )

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


class BaxiBoostDurationNumber(CoordinatorEntity, NumberEntity):
    """Durata massima del boost sanitario (10-120 min), parametro "Sanitario - Tempo max boost"."""

    _attr_has_entity_name = True
    _attr_translation_key = "boost_duration"
    _attr_device_class = NumberDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_native_min_value = BOOST_MIN_MINUTES
    _attr_native_max_value = BOOST_MAX_MINUTES
    _attr_native_step = 1.0
    _attr_entity_category = EntityCategory.CONFIG
    _attr_unique_id = "baxi_boost_duration_number"
    _source_attr = "boost_max_duration"

    def __init__(self, coordinator, api) -> None:
        super().__init__(coordinator)
        self._api = api

    @property
    def native_value(self) -> float | None:
        return getattr(self._api, "boost_max_duration", None)

    @property
    def available(self) -> bool:
        return super().available and getattr(self._api, "boost_max_duration", None) is not None

    @property
    def device_info(self) -> dict:
        return build_device_info(self._api)

    async def async_set_native_value(self, value: float) -> None:
        """Scrive la durata del boost (PUT) con lo stesso flusso del setpoint raffrescamento."""
        minutes = int(max(BOOST_MIN_MINUTES, min(BOOST_MAX_MINUTES, float(value))))

        _LOGGER.info("🔄 Cambio durata boost sanitario → %s min", minutes)
        ok = await self.hass.async_add_executor_job(
            self._api.set_configuration_parameter, PARAM_ID_BOOST_MAX_DURATION, minutes,
        )
        if not ok:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="boost_duration_failed",
                translation_placeholders={"value": str(minutes)},
            )

        self._api.boost_max_duration = float(minutes)
        self.async_write_ha_state()
        await self.hass.services.async_call(
            "logbook", "log",
            {"name": "Durata boost sanitario", "message": f"impostata a {minutes} min", "entity_id": self.entity_id},
            blocking=False,
        )
        _LOGGER.info("✅ Durata boost sanitario impostata a %s min", minutes)
        self.hass.async_create_task(self._grace_refresh())

    async def _grace_refresh(self) -> None:
        """Attende il read-back del device e riallinea dal cloud."""
        await asyncio.sleep(WRITE_GRACE_SECONDS)
        await self.coordinator.async_request_refresh()


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator, api = entry.runtime_data.coordinator, entry.runtime_data.api
    async_add_provided_entities(hass, api, "number", [
        BaxiCoolingSetpointNumber(coordinator, api),
        BaxiBoostDurationNumber(coordinator, api),
    ], async_add_entities)
