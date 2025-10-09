# custom_components/baxi_hybridapp_home/water_heater.py
from __future__ import annotations

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import UnitOfTemperature
from .const import DOMAIN, DATA_KEY_API


class BaxiSanitaryReadOnly(WaterHeaterEntity):
    """Entità informativa (sola lettura) sull'accumulo sanitario."""

    _attr_name = "Sanitario Baxi"
    _attr_unique_id = "baxi_water_heater"
    _attr_supported_features = 0  # sola lettura
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator, api):
        self._api = api
        self._coordinator = coordinator

    @property
    def available(self) -> bool:
        # Mostra l'entità solo quando abbiamo almeno la temp sanitaria
        return self._api.dhw_storage_temp is not None

    @property
    def current_temperature(self):
        # Temperatura accumulo sanitario
        return self._api.dhw_storage_temp

    @property
    def min_temp(self):
        return 30

    @property
    def max_temp(self):
        # limite prudenziale
        return 52

    @property
    def is_on(self) -> bool:
        val = (self._api.sanitary_on or "").lower()
        return val.startswith("on")

    @property
    def icon(self) -> str:
        return "mdi:water-boiler" if self.is_on else "mdi:water-boiler-off"

    @property
    def extra_state_attributes(self):
        # Modalità attuale calcolata dall'API (Eco/Comfort) se disponibile
        mode_now = (self._api.sanitary_mode_now or "").strip().lower()

        # Setpoint corrente informativo (in base alla modalità corrente)
        if mode_now == "comfort":
            current_sp = self._api.setpoint_comfort_temp
        else:
            current_sp = self._api.setpoint_eco_temp

        return {
            "stato_sanitario": "Acceso" if self.is_on else "Spento",
            "temperatura_accumulo": self._api.dhw_storage_temp,
            "modalita": self._api.sanitary_mode_now,  # "Comfort" | "Eco"
            "setpoint_corrente": current_sp,
            "setpoint_comfort": self._api.setpoint_comfort_temp,
            "setpoint_eco": self._api.setpoint_eco_temp,
            "temperatura_mandata_caldaia": self._api.boiler_flow_temp,
            "stato_fiamma": self._api.flame_status,  # "On"/"Off" o None
        }

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "baxi_hybridapp_home")},
            "name": "Baxi HybridApp Home",
            "manufacturer": "Baxi",
            "model": "HybridApp Home",
        }


class BaxiSanitaryTest(WaterHeaterEntity):
    """
    Entità di TEST con scrittura setpoint Eco/Comfort (SOLO in memoria).
    - target_temperature modifica il setpoint della modalità corrente (Eco/Comfort)
    - operation_list: ["eco", "comfort"] con switch locale (non tocca lo scheduler Baxi)
    - evidenzia boiler_flow_temp, sanitario_on, modalita, flame_status
    """

    _attr_name = "Sanitario Baxi (Test)"
    _attr_unique_id = "baxi_water_heater_test"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )

    def __init__(self, coordinator, api):
        self._api = api
        self._coordinator = coordinator
        # override locale della modalità, opzionale
        self._mode_override: str | None = None

    # ---------------- Base ----------------
    @property
    def available(self) -> bool:
        return self._api.dhw_storage_temp is not None

    @property
    def current_temperature(self):
        # mostriamo la temperatura di accumulo come "current"
        return self._api.dhw_storage_temp

    @property
    def min_temp(self):
        return 30

    @property
    def max_temp(self):
        # richiesto: max 52°C
        return 52

    def _current_mode(self) -> str:
        """eco|comfort (usa override locale se impostato, altrimenti lo stato calcolato)."""
        if self._mode_override in ("eco", "comfort"):
            return self._mode_override
        mode = (self._api.sanitary_mode_now or "").strip().lower()
        return "comfort" if mode == "comfort" else "eco"

    # ---------------- On/Off + icone ----------------
    @property
    def is_on(self) -> bool:
        val = (self._api.sanitary_on or "").lower()
        return val.startswith("on")

    @property
    def icon(self) -> str:
        # icona diversa se fiamma ON
        flame = (self._api.flame_status or "").strip().lower()
        if flame == "on":
            return "mdi:fire"
        return "mdi:water-boiler" if self.is_on else "mdi:water-boiler-off"

    # ---------------- Operation Mode ----------------
    @property
    def operation_list(self):
        return ["eco", "comfort"]

    @property
    def current_operation(self):
        return self._current_mode()

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        # switch locale della modalità (solo per test UI)
        mode = operation_mode.strip().lower()
        if mode not in ("eco", "comfort"):
            return
        self._mode_override = mode
        self.async_write_ha_state()

    # ---------------- Target Temperature (setpoint) ----------------
    @property
    def target_temperature(self):
        # mostra il setpoint della modalità corrente
        return (
            self._api.setpoint_comfort_temp
            if self._current_mode() == "comfort"
            else self._api.setpoint_eco_temp
        )

    @property
    def target_temperature_step(self) -> float:
        # step di 1°C
        return 1.0

    async def async_set_temperature(self, **kwargs) -> None:
        """Aggiorna il setpoint della modalità corrente (solo in memoria)."""
        new_t = kwargs.get("temperature")
        if new_t is None:
            return
        # clamp 30..52
        new_t = max(self.min_temp, min(self.max_temp, float(new_t)))

        if self._current_mode() == "comfort":
            self._api.setpoint_comfort_temp = new_t
        else:
            self._api.setpoint_eco_temp = new_t

        # Aggiorna subito lo stato dell'entità
        self.async_write_ha_state()

    # ---------------- Extra ----------------
    @property
    def extra_state_attributes(self):
        mode = self._current_mode()
        return {
            "stato_sanitario": "Acceso" if self.is_on else "Spento",
            "modalita": mode,                                 # eco|comfort (override o API)
            "setpoint_comfort": self._api.setpoint_comfort_temp,
            "setpoint_eco": self._api.setpoint_eco_temp,
            "temperatura_mandata_caldaia": self._api.boiler_flow_temp,
            "stato_fiamma": self._api.flame_status,           # On/Off/None
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
    # Aggiungo sia l'entità read-only sia quella di test scrivibile
    async_add_entities(
        [
            BaxiSanitaryReadOnly(coordinator, api),
            BaxiSanitaryTest(coordinator, api),
        ]
    )
