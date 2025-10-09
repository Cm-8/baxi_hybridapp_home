from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature, UnitOfPressure
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
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
            name="Temperatura Esterna",
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
            name="Temperatura Interna",
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
            name="Temperatura Mandata Caldaia",
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
            name="Temperatura Accumulo Sanitario",
            unique_id="baxi_dhw_storage_temperature",
            value_key="dhw_storage_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            icon="mdi:thermometer"
        )
        
class DHWAuxStorageTempSensor(BaxiBaseSensor):
    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            name="Temperatura Accumulo Ausiliario",
            unique_id="baxi_dhw_aux_storage_temperature",
            value_key="dhw_aux_storage_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            icon="mdi:thermometer"
        )

class PDCExitTempSensor(BaxiBaseSensor):
    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            name="Temperatura Uscita PDC",
            unique_id="baxi_pdc_exit_temperature",
            value_key="pdc_exit_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            icon="mdi:thermometer"
        )

class PDCReturnTempSensor(BaxiBaseSensor):
    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            name="Temperatura Ritorno PDC",
            unique_id="baxi_pdc_return_temperature",
            value_key="pdc_return_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            icon="mdi:thermometer"
        )

class SetpointInstantTempSensor(BaxiBaseSensor):
    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            name="Setpoint Sanitario Istantaneo",
            unique_id="baxi_setpoint_instant_temperature",
            value_key="setpoint_instant_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            icon="mdi:target"
        )

class SetpointComfortTempSensor(BaxiBaseSensor):
    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            name="Setpoint Sanitario Comfort",
            unique_id="baxi_setpoint_comfort_temperature",
            value_key="setpoint_comfort_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            icon="mdi:target"
        )

class SetpointEcoTempSensor(BaxiBaseSensor):
    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            name="Setpoint Sanitario Eco",
            unique_id="baxi_setpoint_eco_temperature",
            value_key="setpoint_eco_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
            icon="mdi:target"
        )

class WaterPressureSensor(BaxiBaseSensor):
    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            name="Pressione Impianto",
            unique_id="baxi_water_pressure",
            value_key="water_pressure",
            unit=UnitOfPressure.BAR,
            device_class=SensorDeviceClass.PRESSURE,
            icon="mdi:gauge"
        )
        
class SanitaryOnSensor(BaxiBaseSensor):
    # Non è un sensore numerico: niente state_class
    _attr_state_class = None

    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            name="Sanitario On",
            unique_id="baxi_sanitary_on",
            value_key="sanitary_on",
            unit=None,
            device_class=None,
            icon="mdi:water-boiler"
        )
        # Assicuriamoci di non ereditare unità o device_class numerica
        self._attr_native_unit_of_measurement = None
        self._attr_device_class = None

    @property
    def native_value(self):
        # Restituisce la stringa "On" o "Off" già mappata dall’API
        return getattr(self._api, self._value_key)

    @property
    def icon(self):
        raw = getattr(self._api, self._value_key)
        val = (raw or "").strip().lower()
        if val.startswith("on"):
            return "mdi:water-boiler"
        if val == "off":
            return "mdi:water-boiler-off"
        # Fallback per valori sconosciuti: icona neutra
        return "mdi:water-boiler"

    @property
    def state_class(self):
        return None

class SystemModeSensor(BaxiBaseSensor):
    # indichiamo subito che non è un sensore numerico
    _attr_state_class = None

    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            name="Modalità Impianto",
            unique_id="baxi_system_mode",
            value_key="system_mode",
            unit=None,
            device_class=None,
            icon="mdi:engine"
        )
        # assicuriamoci che non sia preso come misura
        self._attr_native_unit_of_measurement = None
        self._attr_device_class = None

    @property
    def native_value(self):
        # ritorna la stringa mappata ("Standby" o "Solo Sanitario")
        return getattr(self._api, self._value_key)

    @property
    def state_class(self):
        # override per non ereditare Measurement
        return None
        
        
class SeasonModeSensor(BaxiBaseSensor):
    # override a livello di classe: niente state_class
    _attr_state_class = None

    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            name="Modalità Stagione",
            unique_id="baxi_season_mode",
            value_key="season_mode",
            unit=None,
            device_class=None,
            icon="mdi:sun-snowflake-variant"
        )
        # Assicuriamoci anche che non venga ereditato nulla di numerico
        self._attr_native_unit_of_measurement = None
        self._attr_device_class = None

    @property
    def native_value(self):
        # ritorna la stringa mappata: "Inverno", "Estate", etc.
        return getattr(self._api, self._value_key)

    @property
    def state_class(self):
        # nessuna state_class: Home Assistant non lo vede come "measurement"
        return None
   
class FlameStatusSensor(BaxiBaseSensor):
    _attr_state_class = None  # non è una misura

    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            name="Stato Fiamma",
            unique_id="baxi_flame_status",
            value_key="flame_status",
            unit=None,
            device_class=None,
            icon="mdi:fire"
        )
        self._attr_native_unit_of_measurement = None
        self._attr_device_class = None

    @property
    def native_value(self):
        return getattr(self._api, self._value_key)

    @property
    def icon(self):
        val = (getattr(self._api, self._value_key) or "").lower()
        return "mdi:fire" if val == "on" else "mdi:fire-off"

    @property
    def state_class(self):
        return None

class SanitaryScheduleStateSensor(BaxiBaseSensor, SensorEntity):
    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            name="Schedulatore Sanitario (stato)",
            unique_id="baxi_sanitary_schedule_state",
            value_key="sanitary_mode_now",  # stringa: "Comfort" | "Eco"
            unit=None,
            device_class=None,
            icon="mdi:calendar-clock",
        )
        # 🔒 forza NON numerico (sovrascrivi eventuali default del base)
        self._attr_native_unit_of_measurement = None
        self._attr_device_class = None
        self._attr_state_class = None
        # Evita che HA lo tratti come numerico
        if hasattr(self, "_attr_suggested_display_precision"):
            self._attr_suggested_display_precision = None

    @property
    def native_value(self):
        # stringa, non numero
        return getattr(self._api, "sanitary_mode_now", None)

    @property
    def state_class(self):
        # sovrascrivi eventuali default del base
        return None

    @property
    def available(self):
        # opzionale: disponibile solo se parsing ok
        return (
            getattr(self._api, "sanitary_scheduler_status", None) == "ok"
            and getattr(self._api, "sanitary_mode_now", None) is not None
        )

    @property
    def extra_state_attributes(self):
        nxt = getattr(self._api, "sanitary_next_change", None)
        if nxt:
            # formatta “oggi alle HH:MM” / “domani alle HH:MM”
            from homeassistant.util import dt as dt_util
            hhmm = nxt.astimezone(dt_util.DEFAULT_TIME_ZONE).strftime("%H:%M")
            label = "oggi alle " + hhmm if nxt.date() == dt_util.now().date() else "domani alle " + hhmm
        else:
            label = None
        return {
            "prossimo_cambio": label,
            "prossimo_cambio_iso": nxt.isoformat() if nxt else None,
            "oggi_riepilogo": getattr(self._api, "sanitary_today_summary", None),
            "eco_setpoint": getattr(self._api, "sanitary_eco_setpoint", None),
            "scheduler_status": getattr(self._api, "sanitary_scheduler_status", None),
        }





async def async_setup_entry(hass, entry, async_add_entities):
    api = hass.data[DOMAIN][DATA_KEY_API]
    coordinator = hass.data[DOMAIN]["coordinator"]

    sensors = [
        ExternalTemperatureSensor(coordinator, api),
        InternalTemperatureSensor(coordinator, api),
        BoilerFlowTempSensor(coordinator, api),
        DHWStorageTempSensor(coordinator, api),
        WaterPressureSensor(coordinator, api),
        SanitaryOnSensor(coordinator, api),
        SeasonModeSensor(coordinator, api),
        SystemModeSensor(coordinator, api),
        DHWAuxStorageTempSensor(coordinator, api),
        PDCExitTempSensor(coordinator, api),
        PDCReturnTempSensor(coordinator, api),
        SetpointInstantTempSensor(coordinator, api),
        SetpointComfortTempSensor(coordinator, api),
        SetpointEcoTempSensor(coordinator, api),
        FlameStatusSensor(coordinator, api),
        SanitaryScheduleStateSensor(coordinator, api)
    ]
    async_add_entities(sensors)
    
    
    
    
    
    
    
    