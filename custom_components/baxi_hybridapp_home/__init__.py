from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN, DATA_KEY_API
from .baxi_hybridapp_api import BaxiHybridAppAPI  # aggiornato se hai rinominato il file
import logging

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor"]

async def async_setup(hass: HomeAssistant, config: dict):
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    api = BaxiHybridAppAPI(entry.data["username"], entry.data["password"])

    # Autenticazione e prima acquisizione dati
    await hass.async_add_executor_job(api.authenticate)

    await hass.async_add_executor_job(api.fetch_temperature_ext)
    await hass.async_add_executor_job(api.fetch_temperature_int)
    await hass.async_add_executor_job(api.fetch_water_pressure)
    await hass.async_add_executor_job(api.fetch_boiler_flow_temp)
    await hass.async_add_executor_job(api.fetch_dhw_storage_temp)

    hass.data.setdefault(DOMAIN, {})[DATA_KEY_API] = api

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    hass.data[DOMAIN].pop(DATA_KEY_API, None)
    return True
