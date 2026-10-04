"""
Custom integration for Baxi Hybrid App devices with Home Assistant.
For more details about this integration, please refer to
https://github.com/Cm-8/baxi_hybridapp_home

custom_components/baxi_hybridapp_home/__init__.py
"""

import asyncio
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .api import BaxiHybridAppAPI
from .const import (
    DOMAIN,
    PARAM_ID_SETPOINT_COMFORT, PARAM_ID_SETPOINT_ECO,
    SANITARY_MIN_TEMP, SANITARY_MAX_TEMP,
    WRITE_GRACE_SECONDS,
)
from .coordinator import BaxiConfigEntry, BaxiDataUpdateCoordinator, BaxiRuntimeData, polling_interval

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor", "water_heater", "button", "binary_sensor", "select", "number", "datetime", "switch"]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# Servizi setpoint sanitario: nome → (parameter ID, attributo api, nome nel
# Logbook, entità del Logbook, chiave dell'errore tradotto).
_SANITARY_SERVICES = {
    "set_comfort": (PARAM_ID_SETPOINT_COMFORT, "setpoint_comfort_temp", "Sanitario Comfort",
                    "water_heater.sanitario_comfort", "comfort_setpoint_failed"),
    "set_eco": (PARAM_ID_SETPOINT_ECO, "setpoint_eco_temp", "Sanitario Eco",
                "water_heater.sanitario_eco", "eco_setpoint_failed"),
}

_SET_SCHEMA = vol.Schema({
    vol.Required("value"): vol.All(
        vol.Coerce(int),
        vol.Range(min=SANITARY_MIN_TEMP, max=SANITARY_MAX_TEMP),
    )
})


def _loaded_runtime(hass: HomeAssistant) -> BaxiRuntimeData:
    """Runtime data dell'unica config entry caricata (single_config_entry)."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            return entry.runtime_data
    raise ServiceValidationError(translation_domain=DOMAIN, translation_key="entry_not_loaded")


async def _grace_refresh(coordinator: BaxiDataUpdateCoordinator) -> None:
    """Attende il read-back del device e riallinea dal cloud."""
    await asyncio.sleep(WRITE_GRACE_SECONDS)
    await coordinator.async_request_refresh()


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Registra i servizi una sola volta (regola action-setup).

    Restano registrati anche se la config entry non è caricata: in quel caso
    rispondono con un errore chiaro invece di sparire.
    """

    async def handle_set_sanitary(call: ServiceCall) -> None:
        """Imposta il setpoint sanitario Comfort o Eco (solo temperatura)."""
        param_id, attr, label, entity_id, error_key = _SANITARY_SERVICES[call.service]
        runtime = _loaded_runtime(hass)
        value = call.data["value"]  # range già validato dallo schema

        ok = await hass.async_add_executor_job(
            runtime.api.set_configuration_parameter, param_id, value,
        )
        if not ok:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=error_key,
                translation_placeholders={"value": str(value)},
            )

        _LOGGER.info("✅ %s impostato a %s °C", label, value)
        # Optimistic + refresh differito: un refresh immediato riporterebbe in
        # UI il valore vecchio (il device ri-pubblica la misura con ritardo).
        setattr(runtime.api, attr, float(value))
        runtime.coordinator.async_update_listeners()
        await hass.services.async_call(
            "logbook", "log",
            {"name": label, "message": f"impostato a {value}°C", "entity_id": entity_id},
            blocking=False,
        )
        hass.async_create_task(_grace_refresh(runtime.coordinator))

    for service in _SANITARY_SERVICES:
        hass.services.async_register(DOMAIN, service, handle_set_sanitary, schema=_SET_SCHEMA)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: BaxiConfigEntry) -> bool:
    api = BaxiHybridAppAPI(entry.data["username"], entry.data["password"])
    coordinator = BaxiDataUpdateCoordinator(hass, entry, api)

    # Primo refresh con semantica config-entry:
    # - credenziali non valide → ConfigEntryAuthFailed → HA avvia il re-auth flow
    # - cloud irraggiungibile  → ConfigEntryNotReady   → HA ritenta il setup con backoff
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = BaxiRuntimeData(api=api, coordinator=coordinator)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_options_updated(hass: HomeAssistant, entry: BaxiConfigEntry) -> None:
    """Nuovo intervallo dal pulsante Configura: applicato subito, senza ricaricare."""
    coordinator = entry.runtime_data.coordinator
    interval = polling_interval(entry)
    if coordinator.update_interval == interval:
        return  # aggiornamento della entry che non tocca le opzioni (es. ri-autenticazione)
    coordinator.update_interval = interval
    _LOGGER.info("⏱️ Intervallo di aggiornamento impostato a %s", interval)
    # Il timer in corso usa ancora il vecchio intervallo: un ciclo subito lo riprogramma.
    await coordinator.async_request_refresh()


async def async_unload_entry(hass: HomeAssistant, entry: BaxiConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # Logout dal cloud (invalida il refreshToken) e chiusura della sessione
        # HTTP, best-effort. Il resto di entry.runtime_data viene scartato con la entry.
        await hass.async_add_executor_job(entry.runtime_data.api.close)
    return unload_ok
