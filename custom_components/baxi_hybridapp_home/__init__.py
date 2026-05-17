"""
Custom integration for Baxi Hybrid App devices with Home Assistant.
For more details about this integration, please refer to
https://github.com/Cm-8/baxi_hybridapp_home

custom_components/baxi_hybridapp_home/__init__.py
"""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from .const import (
    DOMAIN, DATA_KEY_API,
    PARAM_ID_SETPOINT_COMFORT, PARAM_ID_SETPOINT_ECO,
    SANITARY_MIN_TEMP, SANITARY_MAX_TEMP,
)
from .api import BaxiHybridAppAPI
from .coordinator import BaxiDataUpdateCoordinator
import voluptuous as vol
import logging

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor", "water_heater", "button", "binary_sensor"]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict):
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    api = BaxiHybridAppAPI(entry.data["username"], entry.data["password"])
    coordinator = BaxiDataUpdateCoordinator(hass, api)

    # First refresh to populate data
    await coordinator.async_refresh()

    # Store API and coordinator
    hass.data.setdefault(DOMAIN, {})[DATA_KEY_API] = api
    hass.data[DOMAIN]["coordinator"] = coordinator

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # -------------------------------------------------------------
    # Servizi: set_comfort / set_eco (aggiornamento setpoint sanitario)
    # -------------------------------------------------------------
    set_schema = vol.Schema({
        vol.Required("value"): vol.All(
            vol.Coerce(int),
            vol.Range(min=SANITARY_MIN_TEMP, max=SANITARY_MAX_TEMP)
        )
    })

    async def handle_set_comfort(call):
        """Aggiorna il setpoint sanitario Comfort via SET (SOLO temperatura)."""
        value = int(call.data.get("value"))

        if value < SANITARY_MIN_TEMP or value > SANITARY_MAX_TEMP:
            _LOGGER.warning(
                "❌ Valore %s fuori range (%s–%s). SET non eseguita.",
                value, SANITARY_MIN_TEMP, SANITARY_MAX_TEMP,
            )
            await hass.services.async_call(
                "logbook", "log",
                {
                    "name": "Sanitario Comfort",
                    "message": f"valore {value}°C fuori range ({SANITARY_MIN_TEMP}-{SANITARY_MAX_TEMP}) — SET annullata",
                    "entity_id": "water_heater.sanitario_comfort",
                },
                blocking=False,
            )
            return

        ok = await hass.async_add_executor_job(
            api.set_configuration_parameter,
            PARAM_ID_SETPOINT_COMFORT,
            value,
        )

        if ok:
            await hass.services.async_call(
                "logbook", "log",
                {
                    "name": "Sanitario Comfort",
                    "message": f"impostato a {value}°C",
                    "entity_id": "water_heater.sanitario_comfort",
                },
                blocking=False,
            )
            _LOGGER.info("✅ SET Comfort impostato a %s °C", value)
            await coordinator.async_request_refresh()
        else:
            _LOGGER.error("❌ SET Comfort fallita per %s °C", value)

    async def handle_set_eco(call):
        """Aggiorna il setpoint sanitario Eco via SET (SOLO temperatura)."""
        value = int(call.data.get("value"))

        if value < SANITARY_MIN_TEMP or value > SANITARY_MAX_TEMP:
            _LOGGER.warning(
                "❌ Valore %s fuori range (%s–%s). SET non eseguita.",
                value, SANITARY_MIN_TEMP, SANITARY_MAX_TEMP,
            )
            await hass.services.async_call(
                "logbook", "log",
                {
                    "name": "Sanitario Eco",
                    "message": f"valore {value}°C fuori range ({SANITARY_MIN_TEMP}-{SANITARY_MAX_TEMP}) — SET annullata",
                    "entity_id": "water_heater.sanitario_eco",
                },
                blocking=False,
            )
            return

        ok = await hass.async_add_executor_job(
            api.set_configuration_parameter,
            PARAM_ID_SETPOINT_ECO,
            value,
        )

        if ok:
            await hass.services.async_call(
                "logbook", "log",
                {
                    "name": "Sanitario Eco",
                    "message": f"impostato a {value}°C",
                    "entity_id": "water_heater.sanitario_eco",
                },
                blocking=False,
            )
            _LOGGER.info("✅ SET Eco impostato a %s °C", value)
            await coordinator.async_request_refresh()
        else:
            _LOGGER.error("❌ SET Eco fallita per %s °C", value)

    hass.services.async_register(DOMAIN, "set_comfort", handle_set_comfort, schema=set_schema)
    hass.services.async_register(DOMAIN, "set_eco", handle_set_eco, schema=set_schema)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(DATA_KEY_API)
        hass.data[DOMAIN].pop("coordinator")
    return unload_ok
