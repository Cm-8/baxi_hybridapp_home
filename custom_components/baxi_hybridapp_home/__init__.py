from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from datetime import timedelta
from .const import DOMAIN, DATA_KEY_API
from .baxi_hybridapp_api import BaxiHybridAppAPI
import logging

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor"]

async def async_setup(hass: HomeAssistant, config: dict):
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    api = BaxiHybridAppAPI(entry.data["username"], entry.data["password"])

    async def async_update_data():
        """Fetch all metrics from Baxi API."""
        # Authentication and fetching all values
        await hass.async_add_executor_job(api.authenticate)
        await hass.async_add_executor_job(api.get_thingid)
        await hass.async_add_executor_job(api.fetch_temperature_ext)
        await hass.async_add_executor_job(api.fetch_temperature_int)
        await hass.async_add_executor_job(api.fetch_water_pressure)
        await hass.async_add_executor_job(api.fetch_boiler_flow_temp)
        await hass.async_add_executor_job(api.fetch_dhw_storage_temp)
        await hass.async_add_executor_job(api.fetch_system_mode)
        await hass.async_add_executor_job(api.fetch_season_mode)
        return True

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="baxi_hybridapp_home",
        update_method=async_update_data,
        update_interval=timedelta(minutes=5),
    )

    # First refresh to populate data
    await coordinator.async_refresh()

    # Store API and coordinator
    hass.data.setdefault(DOMAIN, {})[DATA_KEY_API] = api
    hass.data[DOMAIN]["coordinator"] = coordinator

    # Forward setup to sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(DATA_KEY_API)
        hass.data[DOMAIN].pop("coordinator")
    return unload_ok
    
    
    
    