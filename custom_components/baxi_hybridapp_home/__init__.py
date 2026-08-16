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
    HOLIDAY_STAGED_KEY, PARAM_ID_HOLIDAY_MODE_END,
    HOLIDAY_MODE_DISABLE_VALUE,
)
from .api import BaxiHybridAppAPI
from .coordinator import BaxiDataUpdateCoordinator
from datetime import datetime, timezone
import voluptuous as vol
import logging

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor", "water_heater", "button", "binary_sensor", "select", "number", "datetime", "switch"]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict):
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    api = BaxiHybridAppAPI(entry.data["username"], entry.data["password"])
    coordinator = BaxiDataUpdateCoordinator(hass, entry, api)

    # Primo refresh con semantica config-entry:
    # - credenziali non valide → ConfigEntryAuthFailed → HA avvia il re-auth flow
    # - cloud irraggiungibile  → ConfigEntryNotReady   → HA ritenta il setup con backoff
    await coordinator.async_config_entry_first_refresh()

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

    # -------------------------------------------------------------
    # Servizio: set_holiday_mode (attiva la vacanza con data di fine
    # richiesta come parametro, senza passare dallo staging via
    # entità datetime + switch)
    # -------------------------------------------------------------
    holiday_schema = vol.Schema({
        vol.Required("end_date"): cv.datetime,
    })

    async def handle_set_holiday_mode(call):
        """Attiva il modo vacanza inviando direttamente la data di fine."""
        end_date = call.data.get("end_date")

        # cv.datetime restituisce un datetime naive se l'utente non
        # specifica il fuso: lo assumiamo in orario locale HA.
        if end_date.tzinfo is None:
            end_date = end_date.astimezone() if hasattr(end_date, "astimezone") else end_date.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        if end_date <= now:
            _LOGGER.warning(
                "❌ set_holiday_mode: la data di fine (%s) non è futura. Azione annullata.",
                end_date.isoformat(),
            )
            await hass.services.async_call(
                "logbook", "log",
                {
                    "name": "Modo Vacanza",
                    "message": f"data fine {end_date.isoformat()} non futura — attivazione annullata",
                },
                blocking=False,
            )
            return

        epoch_ms = int(end_date.timestamp() * 1000)
        _LOGGER.info(
            "🏖️ set_holiday_mode: attivazione fino a %s (epoch_ms: %d)",
            end_date.isoformat(), epoch_ms,
        )

        ok = await hass.async_add_executor_job(
            api.set_configuration_parameter,
            PARAM_ID_HOLIDAY_MODE_END,
            epoch_ms,
        )

        if ok:
            api.holiday_mode = "On"
            api.holiday_mode_end = end_date
            hass.data[DOMAIN][HOLIDAY_STAGED_KEY] = None
            await hass.services.async_call(
                "logbook", "log",
                {
                    "name": "Modo Vacanza",
                    "message": f"attivato fino a {end_date.isoformat()}",
                },
                blocking=False,
            )
            _LOGGER.info("✅ Modo vacanza attivato fino a %s", end_date.isoformat())
            await coordinator.async_request_refresh()
        else:
            _LOGGER.error("❌ Attivazione modo vacanza fallita")

    hass.services.async_register(
        DOMAIN, "set_holiday_mode", handle_set_holiday_mode, schema=holiday_schema
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(DATA_KEY_API)
        hass.data[DOMAIN].pop("coordinator")
        hass.data[DOMAIN].pop(HOLIDAY_STAGED_KEY, None)
    return unload_ok
