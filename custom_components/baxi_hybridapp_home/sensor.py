"""
Sensor platform for Baxi Hybrid App custom integration for Home Assistant.

custom_components/baxi_hybridapp_home/sensor.py
"""

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    PERCENTAGE, SIGNAL_STRENGTH_DECIBELS_MILLIWATT, UnitOfPressure, UnitOfTemperature, UnitOfTime,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify
from datetime import datetime, timezone
from .device import async_add_provided_entities, build_device_info
from .metrics import DAILY_MODE_TIME_METRICS, ENERGY_SENSOR_TYPES

# Sola lettura, aggiornata dal coordinator: nessun limite al parallelismo.
PARALLEL_UPDATES = 0

class BaxiBaseSensor(CoordinatorEntity, SensorEntity):
    # Nome = nome del device + nome tradotto (translations/<lingua>.json,
    # sezione entity.sensor.<translation_key>); icone statiche in icons.json.
    _attr_has_entity_name = True

    def __init__(self, coordinator, api, translation_key, unique_id, value_key, unit, device_class):
        super().__init__(coordinator)
        self._api = api
        self._attr_unique_id = unique_id
        self._attr_translation_key = translation_key
        self._value_key = value_key
        # Attributo letto: l'entità esiste solo se il modello ha la metrica
        # (vedi async_add_provided_entities).
        self._source_attr = value_key
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = SensorStateClass.MEASUREMENT
        
        #sensorName
        prefix = "baxi"
        serial_number = getattr(self._api, "serialNumber", None) or "unknown"
        serial_slug = slugify(str(serial_number))
        key_slug = slugify(str(value_key))

        self._attr_suggested_object_id = f"{prefix}_{serial_slug}_{key_slug}"

    @property
    def available(self) -> bool:
        # Non disponibile se il cloud è irraggiungibile (ultimo aggiornamento
        # del coordinator fallito) o se il device non espone la metrica.
        return super().available and getattr(self._api, self._value_key, None) is not None

    @property
    def device_info(self):
        return build_device_info(self._api)

    @property
    def native_value(self):
        return getattr(self._api, self._value_key, None)

class ExternalTemperatureSensor(BaxiBaseSensor):
    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            translation_key="external_temperature",
            unique_id="baxi_external_temperature",
            value_key="temp_ext",
            unit=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
        )

class InternalTemperatureSensor(BaxiBaseSensor):
    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            translation_key="internal_temperature",
            unique_id="baxi_internal_temperature",
            value_key="temp_int",
            unit=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
        )

class BoilerFlowTempSensor(BaxiBaseSensor):
    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            translation_key="boiler_flow_temperature",
            unique_id="baxi_boiler_flow_temperature",
            value_key="boiler_flow_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
        )

class DHWStorageTempSensor(BaxiBaseSensor):
    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            translation_key="dhw_storage_temperature",
            unique_id="baxi_dhw_storage_temperature",
            value_key="dhw_storage_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
        )
        
class DHWAuxStorageTempSensor(BaxiBaseSensor):
    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            translation_key="dhw_aux_storage_temperature",
            unique_id="baxi_dhw_aux_storage_temperature",
            value_key="dhw_aux_storage_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
        )

class PDCExitTempSensor(BaxiBaseSensor):
    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            translation_key="pdc_exit_temperature",
            unique_id="baxi_pdc_exit_temperature",
            value_key="pdc_exit_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
        )

class PDCReturnTempSensor(BaxiBaseSensor):
    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            translation_key="pdc_return_temperature",
            unique_id="baxi_pdc_return_temperature",
            value_key="pdc_return_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
        )

class SetpointInstantTempSensor(BaxiBaseSensor):
    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            translation_key="setpoint_instant",
            unique_id="baxi_setpoint_instant_temperature",
            value_key="setpoint_instant_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
        )

class SetpointComfortTempSensor(BaxiBaseSensor):
    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            translation_key="setpoint_comfort",
            unique_id="baxi_setpoint_comfort_temperature",
            value_key="setpoint_comfort_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
        )

class SetpointEcoTempSensor(BaxiBaseSensor):
    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            translation_key="setpoint_eco",
            unique_id="baxi_setpoint_eco_temperature",
            value_key="setpoint_eco_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
        )

class SetpointRaffrescamentoTempSensor(BaxiBaseSensor):
    # Disabilitato di default, come il number gemello: interessa solo chi
    # usa il raffrescamento.
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            translation_key="cooling_setpoint",
            unique_id="baxi_setpoint_raffrescamento_temperature",
            value_key="setpoint_raffrescamento_temp",
            unit=UnitOfTemperature.CELSIUS,
            device_class=SensorDeviceClass.TEMPERATURE,
        )

    @property
    def extra_state_attributes(self):
        return {"description": "Set-point di raffrescamento impianto (range 7–30 °C)"}

class WaterPressureSensor(BaxiBaseSensor):
    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            translation_key="water_pressure",
            unique_id="baxi_water_pressure",
            value_key="water_pressure",
            unit=UnitOfPressure.BAR,
            device_class=SensorDeviceClass.PRESSURE,
        )
        
class SanitaryOnSensor(BaxiBaseSensor):
    # Non è un sensore numerico: niente state_class
    _attr_state_class = None

    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            translation_key="sanitary_on",
            unique_id="baxi_sanitary_on",
            value_key="sanitary_on",
            unit=None,
            device_class=None,
        )
        # Assicuriamoci di non ereditare unità o device_class numerica
        self._attr_native_unit_of_measurement = None
        self._attr_device_class = None

    @property
    def native_value(self):
        # Restituisce la stringa "On" o "Off" già mappata dall’API
        return getattr(self._api, self._value_key, None)

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
            translation_key="system_mode",
            unique_id="baxi_system_mode",
            value_key="system_mode",
            unit=None,
            device_class=None,
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
            translation_key="season_mode",
            unique_id="baxi_season_mode",
            value_key="season_mode",
            unit=None,
            device_class=None,
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
    _attr_entity_registry_enabled_default = False  # disabilitata di default

    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            translation_key="flame_status",
            unique_id="baxi_flame_status",
            value_key="flame_status",
            unit=None,
            device_class=None,
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
    
class SystemOperationIcon(BaxiBaseSensor):
    _attr_state_class = None  # non è una misura
    _attr_entity_registry_enabled_default = False  # disabilitata di default

    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            translation_key="system_operation_icon",
            unique_id="baxi_system_operation_icon",
            value_key="system_operation_icon",
            unit=None,
            device_class=None,
        )
        self._attr_native_unit_of_measurement = None
        self._attr_device_class = None

    @property
    def native_value(self):
        return getattr(self._api, self._value_key)

    @property
    def state_class(self):
        return None

# Modo vacanza (issue #12): stato On/Off + data/ora di fine
class HolidayModeSensor(BaxiBaseSensor):
    _attr_state_class = None  # non è una misura

    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            translation_key="holiday_mode",
            unique_id="baxi_holiday_mode",
            value_key="holiday_mode",
            unit=None,
            device_class=None,
        )
        self._attr_native_unit_of_measurement = None
        self._attr_device_class = None

    @property
    def native_value(self):
        return getattr(self._api, self._value_key)

    @property
    def icon(self):
        val = (getattr(self._api, self._value_key) or "").lower()
        return "mdi:palm-tree" if val == "on" else "mdi:home"

    @property
    def state_class(self):
        return None

class HolidayModeEndSensor(BaxiBaseSensor):
    _attr_state_class = None  # non è una misura

    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            translation_key="holiday_mode_end",
            unique_id="baxi_holiday_mode_end",
            value_key="holiday_mode_end",
            unit=None,
            # La metrica è epoch ms convertito in datetime (vedi _parse_epoch_ms):
            # con device_class TIMESTAMP la UI mostra data/ora localizzata e il
            # valore è confrontabile nelle automazioni.
            device_class=SensorDeviceClass.TIMESTAMP,
        )
        self._attr_native_unit_of_measurement = None

    @property
    def available(self) -> bool:
        # A vacanza spenta la data di fine non esiste: l'entità resta
        # disponibile con stato "sconosciuto", invece di risultare guasta.
        # Dipende dallo stato vacanza, non dalla presenza della data.
        return self.coordinator.last_update_success and getattr(self._api, "holiday_mode", None) is not None

    @property
    def native_value(self):
        return getattr(self._api, self._value_key)

    @property
    def state_class(self):
        return None

# Inizio nuovi sensori caldaia
class StatusBoiler(BaxiBaseSensor):
    _attr_state_class = None  # non è una misura

    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            translation_key="boiler_status",
            unique_id="baxi_status_boiler",
            value_key="status_boiler",
            unit=None,
            device_class=None,
        )
        self._attr_native_unit_of_measurement = None
        self._attr_device_class = None

    @property
    def native_value(self):
        return getattr(self._api, self._value_key)

    @property
    def icon(self):
        val = (getattr(self._api, self._value_key) or "").lower()
        return "mdi:water-boiler" if val == "on" else "mdi:water-boiler-off"

    @property
    def state_class(self):
        return None

class StatusPDC(BaxiBaseSensor):
    _attr_state_class = None  # non è una misura

    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            translation_key="heat_pump_status",
            unique_id="baxi_status_pdc",
            value_key="status_pdc",
            unit=None,
            device_class=None,
        )
        self._attr_native_unit_of_measurement = None
        self._attr_device_class = None

    @property
    def native_value(self):
        return getattr(self._api, self._value_key)

    @property
    def icon(self):
        val = (getattr(self._api, self._value_key) or "").lower()
        return "mdi:heat-pump" if val in ("on", "avvio") else "mdi:heat-pump-outline"

    @property
    def state_class(self):
        return None
    
class PowerBoiler(BaxiBaseSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT # percentuale
    # Disabilitato di default: alcuni impianti non pubblicano la potenza
    # istantanea (resta a 0 % senza mai cambiare).
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            translation_key="boiler_power",
            unique_id="baxi_power_boiler",
            value_key="power_boiler",
            unit=PERCENTAGE,
            device_class=SensorDeviceClass.POWER_FACTOR,  # usa %
        )

    @property
    def native_value(self):
        raw = getattr(self._api, self._value_key, None)
        if raw is None:
            return None

        if isinstance(raw, (int, float)):
            val = float(raw)
        else:
            s = str(raw).strip().lower().replace("%", "").replace(",", ".")
            # se ti arrivano on/off
            if s in {"on", "true"}:
                return 100
            if s in {"off", "false"}:
                return 0
            try:
                val = float(s)
            except ValueError:
                return None

        # clamp 0..100
        val = max(0.0, min(100.0, val))
        return int(val) if val.is_integer() else round(val, 1)

    @property
    def icon(self):
        val = self.native_value
        if val is None:
            return "mdi:fire-off"
        return "mdi:fire" if val > 0 else "mdi:heat-pump-outline"

class PowerPDC(BaxiBaseSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT # percentuale
    # Come PowerBoiler: disabilitato di default (valore spesso fermo a 0 %).
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            translation_key="heat_pump_power",
            unique_id="baxi_power_pdc",
            value_key="power_pdc",
            unit=PERCENTAGE,
            device_class=SensorDeviceClass.POWER_FACTOR,  # usa %
        )

    @property
    def native_value(self):
        raw = getattr(self._api, self._value_key, None)
        if raw is None:
            return None

        if isinstance(raw, (int, float)):
            val = float(raw)
        else:
            s = str(raw).strip().lower().replace("%", "").replace(",", ".")
            # se ti arrivano on/off
            if s in {"on", "true"}:
                return 100
            if s in {"off", "false"}:
                return 0
            try:
                val = float(s)
            except ValueError:
                return None

        # clamp 0..100
        val = max(0.0, min(100.0, val))
        return int(val) if val.is_integer() else round(val, 1)

    @property
    def icon(self):
        val = self.native_value
        if val is None:
            return "mdi:heat-pump-outline"
        return "mdi:percent" if val > 0 else "mdi:percent-box-outline"

class SystemOperationMode(BaxiBaseSensor):
    _attr_state_class = None  # non è una misura numerica

    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            translation_key="system_operation_mode",
            unique_id="baxi_system_operation_mode",
            value_key="system_operation_mode",
            unit=None,
            device_class=None,
        )
        self._attr_native_unit_of_measurement = None
        self._attr_device_class = None

    @property
    def native_value(self):
        return getattr(self._api, self._value_key)

    @property
    def state_class(self):
        return None

# Sensor per la schedulazione del Schedulatore Sanitario
class SanitaryScheduleStateSensor(BaxiBaseSensor):
    def __init__(self, coordinator, api):
        super().__init__(
            coordinator,
            api,
            translation_key="sanitary_schedule",
            unique_id="baxi_sanitary_schedule_state",
            value_key="sanitary_mode_now",  # stringa: "Comfort" | "Eco"
            unit=None,
            device_class=None,
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
        # disponibile solo se il cloud risponde e il parsing è ok
        return (
            self.coordinator.last_update_success
            and getattr(self._api, "sanitary_scheduler_status", None) == "ok"
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

class BaxiOnOffSensor(BaxiBaseSensor):
    """Stato On/Off già mappato dall'API: testo, non una misura; icona per stato (on, off)."""

    _icons = ("mdi:toggle-switch", "mdi:toggle-switch-off-outline")

    def __init__(self, coordinator, api, translation_key, unique_id, value_key):
        super().__init__(coordinator, api, translation_key, unique_id, value_key, unit=None, device_class=None)
        self._attr_state_class = None

    @property
    def icon(self):
        val = (getattr(self._api, self._value_key) or "").lower()
        return self._icons[0] if val == "on" else self._icons[1]


class BoostStatusSensor(BaxiOnOffSensor):
    _icons = ("mdi:rocket-launch", "mdi:rocket-launch-outline")

    def __init__(self, coordinator, api):
        super().__init__(
            coordinator, api,
            translation_key="boost_status",
            unique_id="baxi_boost_status",
            value_key="boost_status",
        )


class HeatingRequestSensor(BaxiOnOffSensor):
    """Richiesta di calore dal termostato ambiente (contatto TA 31/31).

    Disabilitato di default: con il pannello Wi-Fi da esterno il contatto è
    ponticellato e il valore resta On dalla messa in servizio. La richiesta
    reale è in "Riscaldamento in corso" (HeatingActiveSensor).
    """

    _icons = ("mdi:home-thermometer", "mdi:home-thermometer-outline")
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator, api):
        super().__init__(
            coordinator, api,
            translation_key="heating_request",
            unique_id="baxi_heating_request",
            value_key="heating_request",
        )


class ResistancesOnSensor(BaxiOnOffSensor):
    _icons = ("mdi:flash", "mdi:flash-off")

    def __init__(self, coordinator, api):
        super().__init__(
            coordinator, api,
            translation_key="resistances",
            unique_id="baxi_resistances_on",
            value_key="resistances_on",
        )


class HeatingActiveSensor(BaxiOnOffSensor):
    """Riscaldamento in corso adesso (metrica "Riscaldamento per counter")."""

    _icons = ("mdi:radiator", "mdi:radiator-off")

    def __init__(self, coordinator, api):
        super().__init__(
            coordinator, api,
            translation_key="heating_active",
            unique_id="baxi_heating_active",
            value_key="heating_active",
        )


class DhwActiveSensor(BaxiOnOffSensor):
    """Produzione di acqua calda sanitaria in corso (metrica "Sanitario per counter")."""

    _icons = ("mdi:water-boiler", "mdi:water-boiler-off")

    def __init__(self, coordinator, api):
        super().__init__(
            coordinator, api,
            translation_key="dhw_active",
            unique_id="baxi_dhw_active",
            value_key="dhw_active",
        )


class WifiSignalSensor(BaxiBaseSensor):
    """Segnale WiFi del gateway dell'impianto (dBm)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, api):
        super().__init__(
            coordinator, api,
            translation_key="wifi_signal",
            unique_id="baxi_wifi_signal",
            value_key="wifi_signal",
            unit=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
            device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        )


class PDCFlowRateSensor(BaxiBaseSensor):
    # L/h come nell'app Baxi. Nessuna device_class: L/h non è tra le unità di
    # portata della versione minima di HA supportata (2025.1).
    def __init__(self, coordinator, api):
        super().__init__(
            coordinator, api,
            translation_key="pdc_flow_rate",
            unique_id="baxi_pdc_flow_rate",
            value_key="pdc_flow_rate",
            unit="L/h",
            device_class=None,
        )


class DailyModeTimeSensor(BaxiBaseSensor):
    """Tempo trascorso oggi in una modalità.

    Il cloud manda i millisecondi dall'inizio del giorno (timestamp =
    mezzanotte) e riparte da zero il giorno dopo: TOTAL_INCREASING gestisce
    l'azzeramento come un nuovo ciclo. Mostrato in minuti (valori tipici
    sotto l'ora).
    """

    _attr_entity_registry_enabled_default = False
    _attr_suggested_unit_of_measurement = UnitOfTime.MINUTES
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator, api, attr):
        super().__init__(
            coordinator, api,
            translation_key=attr,
            unique_id=f"baxi_{attr}",
            value_key=attr,
            unit=UnitOfTime.MILLISECONDS,
            device_class=SensorDeviceClass.DURATION,
        )
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self):
        # Ultimo valore di un giorno precedente (il cloud non l'ha ancora
        # aggiornato oggi): oggi il tempo è zero, come per l'energia giornaliera.
        value = getattr(self._api, self._value_key, None)
        ts = getattr(self._api, f"{self._value_key}_timestamp", None)
        if value is not None and ts:
            sample_day = datetime.fromtimestamp(ts / 1000, tz=dt_util.DEFAULT_TIME_ZONE).date()
            if sample_day != dt_util.now().date():
                return 0.0
        return value

    @property
    def extra_state_attributes(self):
        # Il giorno a cui si riferisce il valore (un solo calcolo al giorno).
        ts = getattr(self._api, f"{self._value_key}_timestamp", None)
        if not ts:
            return {}
        return {"metric_timestamp_utc": datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat()}


# 🚨 Contatori alert FAILURE (per dashboard).
# Letti da BaxiHybridAppAPI.fetch_historical_alerts. I binary_sensor con
# device_class=PROBLEM vivono in binary_sensor.py — questi sono solo
# aggregati storici utili per pannelli "Salute impianto".
class FailureCount24hSensor(BaxiBaseSensor):
    # Diagnostica: appare con button + binary_sensor alert, non tra i sensori principali.
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, api):
        super().__init__(
            coordinator, api,
            translation_key="failure_count_24h",
            unique_id="baxi_failure_count_24h",
            value_key="failure_count_24h",
            unit=None,
            device_class=None,
        )


class FailureCount7dSensor(BaxiBaseSensor):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, api):
        super().__init__(
            coordinator, api,
            translation_key="failure_count_7d",
            unique_id="baxi_failure_count_7d",
            value_key="failure_count_7d",
            unit=None,
            device_class=None,
        )


# 🔒 Classe sensori energia
class BaxiEnergySensor(BaxiBaseSensor):
    def __init__(self, coordinator, api, description):
        super().__init__(
            coordinator,
            api,
            translation_key=description.translation_key,
            unique_id=f"baxi_{description.key}",
            value_key=description.key,
            unit=getattr(description, "native_unit_of_measurement", None),
            device_class=getattr(description, "device_class", None),
        )
        self.entity_description = description
        
        sc = getattr(description, "state_class", None)
        if sc is not None:
            self._attr_state_class = sc

    @property
    def native_value(self):
        return getattr(self._api, self.entity_description.key, None)

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and (
            getattr(self._api, self.entity_description.key, None) is not None
        )
    
    @property
    def extra_state_attributes(self):
        ts = getattr(self._api, "energy_timestamp", {}).get(self.entity_description.key)
        if ts is None:
            return {}

        dt_utc = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
        return {
            "metric_timestamp_ms": ts,
            "metric_timestamp_utc": dt_utc.isoformat(),
        }


async def async_setup_entry(hass, entry, async_add_entities):
    api = entry.runtime_data.api
    coordinator = entry.runtime_data.coordinator

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
        SetpointRaffrescamentoTempSensor(coordinator, api),
        FlameStatusSensor(coordinator, api),
        SystemOperationIcon(coordinator, api),
        HolidayModeSensor(coordinator, api),
        HolidayModeEndSensor(coordinator, api),
        # Inizio nuovi sensori caldaia
        StatusBoiler(coordinator, api),
        StatusPDC(coordinator, api),
        PowerBoiler(coordinator, api),
        PowerPDC(coordinator, api),
        SystemOperationMode(coordinator, api),
        # fine nuovi sensori caldaia
        SanitaryScheduleStateSensor(coordinator, api),
        # contatori alert per dashboard
        FailureCount24hSensor(coordinator, api),
        FailureCount7dSensor(coordinator, api),
        # boost sanitario, portata PDC, stati on/off
        BoostStatusSensor(coordinator, api),
        PDCFlowRateSensor(coordinator, api),
        HeatingRequestSensor(coordinator, api),
        ResistancesOnSensor(coordinator, api),
        HeatingActiveSensor(coordinator, api),
        DhwActiveSensor(coordinator, api),
        WifiSignalSensor(coordinator, api),
    ]
    # affianco i nuovi sensori energia
    sensors.extend(
        BaxiEnergySensor(coordinator, api, d)
        for d in ENERGY_SENSOR_TYPES
    )
    sensors.extend(DailyModeTimeSensor(coordinator, api, attr) for attr, _ in DAILY_MODE_TIME_METRICS)
    async_add_provided_entities(hass, api, "sensor", sensors, async_add_entities)
    
    
    
    
    
    
    
    