# custom_components/baxi_hybridapp_home/water_heater.py
from homeassistant.components.water_heater import WaterHeaterEntity
from homeassistant.const import UnitOfTemperature
from .const import DOMAIN, DATA_KEY_API


SCHEDULER_ENTITY_ID = "sensor.baxi_sanitary_schedule_state"  # <-- cambia se diverso

class BaxiSanitaryReadOnly(WaterHeaterEntity):
    _attr_name = "Sanitario Baxi"
    _attr_unique_id = "baxi_water_heater"
    _attr_supported_features = set()                 # sola lettura
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator, api):
        self._api = api
        self._coordinator = coordinator

    # Disponibilità: compare solo se abbiamo almeno la temperatura d'accumulo
    @property
    def available(self) -> bool:
        return self._api.dhw_storage_temp is not None

    # Temperatura attuale (accumulo sanitario)
    @property
    def current_temperature(self):
        return self._api.dhw_storage_temp

    @property
    def min_temp(self):
        return 30

    @property
    def max_temp(self):
        return 60

    # Acceso/Spento -> derivato da sanitary_on ("Off", "On 0_1", "On 1")
    @property
    def is_on(self) -> bool:
        val = (self._api.sanitary_on or "").lower()
        return val.startswith("on")

    # Icona che cambia
    @property
    def icon(self) -> str:
        return "mdi:water-boiler" if self.is_on else "mdi:water-boiler-off"

    # Attributi extra informativi (solo lettura)
    @property
    def extra_state_attributes(self):
        # 1) Stato schedulatore (letto da un altro sensore HA)
        sched_state = None
        if self.hass:
            s = self.hass.states.get(SCHEDULER_ENTITY_ID)
            sched_state = s.state if s else None

        # 2) Determina preset "attivo" in base allo schedulatore
        #    (adatta gli alias se il tuo sensore usa testi diversi)
        mode = None
        if sched_state:
            low = sched_state.strip().lower()
            if "comfort" in low:
                mode = "comfort"
            elif "eco" in low:
                mode = "eco"

        # 3) Setpoint corrente informativo (non modificabile)
        current_setpoint = None
        if mode == "comfort":
            current_setpoint = self._api.setpoint_comfort_temp
        elif mode == "eco":
            current_setpoint = self._api.setpoint_eco_temp

        return {
            "stato_sanitario": "Acceso" if self.is_on else "Spento",
            "temperatura_accumulo": self._api.dhw_storage_temp,
            "schedulatore": sched_state,                 # es: "Comfort" / "Eco" / altro
            "setpoint_corrente": current_setpoint,       # solo se determinabile
            "setpoint_comfort": self._api.setpoint_comfort_temp,
            "setpoint_eco": self._api.setpoint_eco_temp,
        }

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "baxi_hybridapp_home")},
            "name": "Baxi HybridApp Home",
            "manufacturer": "Baxi",
            "model": "HybridApp Home",
        }


async def async_setup_entry(hass, entry, async_add_entities):
    api = hass.data[DOMAIN][DATA_KEY_API]
    coordinator = hass.data[DOMAIN]["coordinator"]
    async_add_entities([BaxiSanitaryReadOnly(coordinator, api)])
