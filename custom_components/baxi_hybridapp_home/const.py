"""
Constants for Baxi Hybrid App custom integration for Home Assistant.

custom_components/baxi_hybridapp_home/const.py
"""

DOMAIN = "baxi_hybridapp_home"
DATA_KEY_API = "api"

APIKEY = "%2FY0ZcwoKJDmtRjXZzsOUmSJUoVQgT5Pka3F38EoD8ng0"
TENANT = 'baxi'

DEV_BROWSER = "Mozilla/5.0"
DEV_MODEL = "sdk_gphone64_x86_64"
DEV_ID = "d26611220fb0ca70"
PLATFORM = "Android"

# Parameter IDs
PARAM_ID_SETPOINT_COMFORT = "5bec6274dbdf4f0008a6e012"
PARAM_ID_SETPOINT_ECO     = "5bec6275dbdf4f0008a6e013"

# Sanitary temperature limits
SANITARY_MIN_TEMP = 30
SANITARY_MAX_TEMP = 52


# SENSOR LIST
from homeassistant.components.sensor import (
    SensorEntityDescription,
    SensorDeviceClass,
    SensorStateClass,
)

from dataclasses import dataclass
from homeassistant.const import UnitOfEnergy, UnitOfTemperature, UnitOfPressure

@dataclass(frozen=True, kw_only=True)
class BaxiEnergySensorEntityDescription(SensorEntityDescription):
    metric_name: str        # metricName esatto per Servitly

APPLIANCE_SENSOR_TYPES: tuple[BaxiEnergySensorEntityDescription, ...] = (
    BaxiEnergySensorEntityDescription(
        key="energia_totale_pdc",
        name="Energia totale PDC",
        metric_name="Energia totale pdc",   # metricName esatto per Servitly
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    BaxiEnergySensorEntityDescription(
        key="energia_totale_caldaia",
        name="Energia totale caldaia",
        metric_name="Energia totale caldaia",   # metricName esatto per Servitly
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    BaxiEnergySensorEntityDescription(
        key="energia_totale_resistenze",
        name="Energia totale resistenze",
        metric_name="Energia totale delle resistenze",   # metricName esatto per Servitly
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    BaxiEnergySensorEntityDescription(
        key="energia_totale_globale",
        name="Energia totale globale",
        metric_name="Energia totale globale",   # metricName esatto per Servitly
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    BaxiEnergySensorEntityDescription(
        key="energia_totale_globale_day",
        name="Energia totale globale per day",
        metric_name="Energia totale globale per day",   # metricName esatto per Servitly
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    BaxiEnergySensorEntityDescription(
        key="energia_parziale_caldaia",
        name="Energia parziale caldaia",
        metric_name="Energia parziale caldaia",   # metricName esatto per Servitly
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    BaxiEnergySensorEntityDescription(
        key="energia_parziale_pdc",
        name="Energia parziale PDC",
        metric_name="Energia parziale pdc",   # metricName esatto per Servitly
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    BaxiEnergySensorEntityDescription(
        key="energia_parziale_resistenze",
        name="Energia parziale resistenze",
        metric_name="Energia parziale delle resistenze",   # metricName esatto per Servitly
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)





