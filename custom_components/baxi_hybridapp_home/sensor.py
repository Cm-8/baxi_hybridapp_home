from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature, UnitOfPressure
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, DATA_KEY_API

import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Setup dei sensori da config_entry."""
    api = hass.data[DOMAIN][DATA_KEY_API]

    # Creazione dei sensori
    async_add_entities([
        BaxiExternalTemperatureSensor(api),
        BaxiInternalTemperatureSensor(api),
        BaxiWaterPressureSensor(api),
        BaxiBoilerFlowTempSensor(api),
        BaxiDHWStorageTempSensor(api)
    ], True)


class BaxiTemperatureSensor(SensorEntity):
    """Classe base per sensori di temperatura Baxi."""

    def __init__(self, api, name, unique_id, fetch_method, value_attr):
        self._api = api
        self._name = name
        self._unique_id = unique_id
        self._fetch_method = fetch_method
        self._value_attr = value_attr
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_icon = "mdi:thermometer"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_value = None

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def available(self) -> bool:
        return getattr(self._api, self._value_attr) is not None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "baxi_hybridapp_home")},
            "name": "Baxi HybridApp Home",
            "manufacturer": "Baxi",
            "model": "HybridApp Home",
        }

    async def async_update(self):
        """Aggiorna lo stato del sensore."""
        _LOGGER.debug(f"🔄 Aggiornamento {self._name}")
        await self.hass.async_add_executor_job(self._fetch_method)

        value = getattr(self._api, self._value_attr)
        if value is not None:
            self._attr_native_value = value
        else:
            _LOGGER.warning(f"⚠️ Nessun valore ricevuto per {self._name}")


class BaxiExternalTemperatureSensor(BaxiTemperatureSensor):
    def __init__(self, api):
        super().__init__(
            api,
            "Temperatura Esterna Baxi",
            "baxi_external_temperature",
            api.fetch_temperature_ext,
            "temp_ext"
        )


class BaxiInternalTemperatureSensor(BaxiTemperatureSensor):
    def __init__(self, api):
        super().__init__(
            api,
            "Temperatura Interna Baxi",
            "baxi_internal_temperature",
            api.fetch_temperature_int,
            "temp_int"
        )


class BaxiBoilerFlowTempSensor(BaxiTemperatureSensor):
    def __init__(self, api):
        super().__init__(
            api,
            "Temperatura Mandata Caldaia Baxi",
            "baxi_boiler_flow_temperature",
            api.fetch_boiler_flow_temp,
            "boiler_flow_temp"
        )


class BaxiDHWStorageTempSensor(BaxiTemperatureSensor):
    def __init__(self, api):
        super().__init__(
            api,
            "Temperatura Accumulo Sanitario Baxi",
            "baxi_dhw_storage_temperature",
            api.fetch_dhw_storage_temp,
            "dhw_storage_temp"
        )

        
class BaxiWaterPressureSensor(SensorEntity):
    """Sensore che mostra la pressione dell'acqua da Baxi."""

    def __init__(self, api):
        self._api = api
        self._attr_name = "Pressione Impianto Baxi"
        self._attr_native_unit_of_measurement = UnitOfPressure.BAR
        self._attr_icon = "mdi:gauge"
        self._attr_unique_id = "baxi_water_pressure"
        self._attr_device_class = SensorDeviceClass.PRESSURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_value = None

    @property
    def available(self) -> bool:
        return self._api.water_pressure is not None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "baxi_hybridapp_home")},
            "name": "Baxi HybridApp Home",
            "manufacturer": "Baxi",
            "model": "HybridApp Home",
        }

    async def async_update(self):
        _LOGGER.debug("🔄 Richiesta aggiornamento pressione acqua da Baxi")
        await self.hass.async_add_executor_job(self._api.fetch_water_pressure)
        if self._api.water_pressure is not None:
            self._attr_native_value = self._api.water_pressure
        else:
            _LOGGER.warning("⚠️ Nessun valore di pressione ricevuto")        
        
        
        
