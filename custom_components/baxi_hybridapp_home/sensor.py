from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature, UnitOfPressure
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN, DATA_KEY_API

class BaxiBaseSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, api, name, unique_id, value_key, unit, device_class, icon):
        super().__init__(coordinator)
        self._api = api
        self._attr_unique_id = unique_id
        self._name = name
        self._value_key = value_key
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = icon

    @property
    def name(self):
        return self._name

    @property
    def available(self) -> bool:
        return getattr(self._api, self._value_key) is not None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "baxi_hybridapp_home")},
            "name": "Baxi HybridApp Home",
            "manufacturer": "Baxi",
            "model": "HybridApp Home",
        }

    @property
    def native_value(self):
        return getattr(self._api, self._value_key)

class ExternalTemperatureSensor(BaxiBaseSensor):
    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            name="Temperatura Esterna Baxi",
            unique_id="baxi_external_temperature",
            value_key="temp_ext",
            unit=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            icon="mdi:thermometer"
        )

class InternalTemperatureSensor(BaxiBaseSensor):
    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            name="Temperatura Interna Baxi",
            unique_id="baxi_internal_temperature",
            value_key="temp_int",
            unit=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            icon="mdi:thermometer"
        )

class BoilerFlowTempSensor(BaxiBaseSensor):
    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            name="Temperatura Mandata Caldaia Baxi",
            unique_id="baxi_boiler_flow_temperature",
            value_key="boiler_flow_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            icon="mdi:thermometer"
        )

class DHWStorageTempSensor(BaxiBaseSensor):
    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            name="Temperatura Accumulo Sanitario Baxi",
            unique_id="baxi_dhw_storage_temperature",
            value_key="dhw_storage_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            icon="mdi:thermometer"
        )

class WaterPressureSensor(BaxiBaseSensor):
    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            name="Pressione Impianto Baxi",
            unique_id="baxi_water_pressure",
            value_key="water_pressure",
            unit=UnitOfPressure.BAR,
            device_class=SensorDeviceClass.PRESSURE,
            icon="mdi:gauge"
        )

async def async_setup_entry(hass, entry, async_add_entities):
    api = hass.data[DOMAIN][DATA_KEY_API]
    coordinator = hass.data[DOMAIN]["coordinator"]

    sensors = [
        ExternalTemperatureSensor(coordinator, api),
        InternalTemperatureSensor(coordinator, api),
        BoilerFlowTempSensor(coordinator, api),
        DHWStorageTempSensor(coordinator, api),
        WaterPressureSensor(coordinator, api),
    ]
    async_add_entities(sensors)