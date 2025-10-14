# custom_components/baxi_hybridapp_home/water_heater.py
from __future__ import annotations

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import UnitOfTemperature
from .const import DOMAIN, DATA_KEY_API


# COMFORT
class BaxiSanitaryComfort(WaterHeaterEntity):
    """
    Entità Comfort
    """

    _attr_name = "Sanitario Comfort"
    _attr_unique_id = "baxi_water_heater_comfort"
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
        return "Attivo" if mode == "comfort" else "Non attivo"

    # ---------------- On/Off + icone ----------------
    @property
    def is_on(self) -> bool:
        val = (self._api.sanitary_on or "").lower()
        return val.startswith("on")

    @property
    def icon(self) -> str:
        if self._mode_override in ("eco", "comfort"):
            return self._mode_override
        mode = (self._api.sanitary_mode_now or "").strip().lower()
        return "mdi:water-boiler" if mode == "comfort" else "mdi:water-boiler-off"

    # ---------------- Operation Mode ----------------
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
        }

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "baxi_hybridapp_home")},
            "name": "Baxi HybridApp Home",
            "manufacturer": "Baxi",
            "model": "HybridApp Home",
        }


# ECO
class BaxiSanitaryEco(WaterHeaterEntity):
    """
    Entità Eco
    """

    _attr_name = "Sanitario Eco"
    _attr_unique_id = "baxi_water_heater_eco"
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
        return "Non attivo" if mode == "comfort" else "Attivo"

    # ---------------- On/Off + icone ----------------
    @property
    def is_on(self) -> bool:
        val = (self._api.sanitary_on or "").lower()
        return val.startswith("on")

    @property
    def icon(self) -> str:
        if self._mode_override in ("eco", "comfort"):
            return self._mode_override
        mode = (self._api.sanitary_mode_now or "").strip().lower()
        return "mdi:water-boiler-off" if mode == "comfort" else "mdi:water-boiler"

    # ---------------- Operation Mode ----------------
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
            self._api.setpoint_eco_temp
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
            # BaxiSanitaryReadOnly(coordinator, api),
            BaxiSanitaryComfort(coordinator, api),
            BaxiSanitaryEco(coordinator, api),
        ]
    )
