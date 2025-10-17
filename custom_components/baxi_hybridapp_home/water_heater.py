# custom_components/baxi_hybridapp_home/water_heater.py
from __future__ import annotations

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import UnitOfTemperature
import asyncio
from .const import (
    DOMAIN, DATA_KEY_API,
    PARAM_ID_SETPOINT_COMFORT, PARAM_ID_SETPOINT_ECO,
)


# COMFORT
class BaxiSanitaryComfort(WaterHeaterEntity):
    """
    Entità Comfort
    """

    _attr_name = "Sanitario Comfort"
    _attr_unique_id = "baxi_water_heater_comfort"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = WaterHeaterEntityFeature.TARGET_TEMPERATURE

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
        mode = self._mode_override or (self._api.sanitary_mode_now or "").strip().lower()
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
        return self._api.setpoint_comfort_temp

    @property
    def target_temperature_step(self) -> float:
        return 1.0  # step a 1°C

    async def async_set_temperature(self, **kwargs) -> None:
        """Scrive il setpoint Comfort o Eco su Baxi (PUT) e aggiorna l'entità."""
        new_t = kwargs.get("temperature")
        if new_t is None:
            return
        # clamp 30..52
        new_t = max(self.min_temp, min(self.max_temp, float(new_t)))
    
        param_id = PARAM_ID_SETPOINT_COMFORT
    
        # fallback sicurezza
        if not param_id:
            # Se non hai ancora messo gli ID, aggiorna solo localmente per test UI
            self._api.setpoint_comfort_temp = new_t
            self.async_write_ha_state()
            return
    
        ok = await self.hass.async_add_executor_job(
            self._api.set_configuration_parameter, param_id, int(new_t)
        )
    
        if ok:
            # 1) Aggiorna subito in locale (optimistic UI)
            self._api.setpoint_comfort_temp = new_t
            self.async_write_ha_state()

            # 2) Grace period per dare tempo al backend Baxi di persistere
            await asyncio.sleep(1.5)

            # 3) Poi rinfresca dal cloud (ora coerente)
            await self._coordinator.async_request_refresh()

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
    _attr_supported_features = WaterHeaterEntityFeature.TARGET_TEMPERATURE

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
        mode = self._mode_override or (self._api.sanitary_mode_now or "").strip().lower()
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
        return self._api.setpoint_eco_temp

    @property
    def target_temperature_step(self) -> float:
        return 1.0  # step a 1°C

    async def async_set_temperature(self, **kwargs) -> None:
        """Scrive il setpoint Eco su Baxi (PUT) e aggiorna l'entità."""
        new_t = kwargs.get("temperature")
        if new_t is None:
            return
        # clamp 30..52
        new_t = max(self.min_temp, min(self.max_temp, float(new_t)))
    
        param_id = PARAM_ID_SETPOINT_ECO
    
        if not param_id:
            # Se non hai ancora messo gli ID, aggiorna solo localmente per test UI
            self._api.setpoint_eco_temp = new_t
            self.async_write_ha_state()
            return
    
        ok = await self.hass.async_add_executor_job(
            self._api.set_configuration_parameter, param_id, int(new_t)
        )
    
        if ok:
            # 1) Aggiorna subito in locale (optimistic UI)
            self._api.setpoint_eco_temp = new_t
            self.async_write_ha_state()

            # 2) Grace period per dare tempo al backend Baxi di persistere
            await asyncio.sleep(1.5)

            # 3) Poi rinfresca dal cloud (ora coerente)
            await self._coordinator.async_request_refresh()

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
