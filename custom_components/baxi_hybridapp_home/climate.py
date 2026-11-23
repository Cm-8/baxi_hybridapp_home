"""
Climate platform for Baxi Hybrid App — termostato della zona 1, per ora in sola lettura (#27).

- Temperatura attuale: "Zona 1 - Temperatura ambiente" (api.temp_int).
- Modalità: "Modo zona 1" → Automatico = auto (segue il programma),
  Comfort e Risparmio = heat, Spento = off. Preset: comfort (Comfort),
  eco (Risparmio), none (Automatico, Spento).
- Temperatura richiesta: in Automatico la fascia in corso del programma
  "Riscaldamento - Zona 1"; in Comfort e Risparmio "Set-point comfort zona 1",
  che è la temperatura in vigore nella zona (segue anche il programma, il
  Risparmio e il Comfort, con 10-16 s di ritardo dopo un cambio di modo).
- Azione: dal riscaldamento in corso ("Riscaldamento per counter"), dove il
  modello lo pubblica; sulle caldaie (LUNA) dalla fiamma accesa senza
  prelievo di acqua calda ("Sanitario on").

Cambiare temperatura, modalità o preset solleva un errore tradotto: le
scritture (Comfort con setpoint e durata, comandi della zona) arriveranno dopo
le prove sul campo.

custom_components/baxi_hybridapp_home/climate.py
"""

import logging

from homeassistant.components.climate import (
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import PRECISION_HALVES, PRECISION_TENTHS, UnitOfTemperature
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN
from .device import async_add_provided_entities, build_device_info

_LOGGER = logging.getLogger(__name__)

# Per ora sola lettura (nessuna scrittura sul device).
PARALLEL_UPDATES = 0

# Modo zona 1 (stringhe del mapper in metrics.py) → modalità e preset HA.
_HVAC_MODE_OF_ZONE_MODE = {
    "Automatico": HVACMode.AUTO,
    "Comfort": HVACMode.HEAT,
    "Risparmio": HVACMode.HEAT,
    "Spento": HVACMode.OFF,
}
_PRESET_OF_ZONE_MODE = {
    "Automatico": PRESET_NONE,
    "Comfort": PRESET_COMFORT,
    "Risparmio": PRESET_ECO,
    "Spento": PRESET_NONE,
}


def _read_only_error() -> ServiceValidationError:
    return ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="climate_read_only",
    )


class BaxiZone1Climate(CoordinatorEntity, ClimateEntity):
    """Termostato della zona 1 in sola lettura."""

    _attr_has_entity_name = True
    _attr_translation_key = "zone_1"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = PRECISION_TENTHS
    _attr_target_temperature_step = PRECISION_HALVES
    # Range del setpoint Comfort della zona (parametro 5-30 °C, passo 0,5).
    _attr_min_temp = 5.0
    _attr_max_temp = 30.0
    _attr_hvac_modes = [HVACMode.AUTO, HVACMode.HEAT, HVACMode.OFF]
    _attr_preset_modes = [PRESET_NONE, PRESET_COMFORT, PRESET_ECO]
    # TARGET_TEMPERATURE serve a mostrare la temperatura richiesta, PRESET_MODE
    # a distinguere Comfort e Risparmio (entrambi heat).
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    # L'entità esiste solo se il modello ha il programma della zona 1.
    _source_attr = "zone1_schedule_temp"

    def __init__(self, coordinator, api) -> None:
        super().__init__(coordinator)
        self._api = api
        self._attr_unique_id = "baxi_climate_zone_1"
        serial_slug = slugify(str(getattr(api, "serialNumber", None) or "unknown"))
        self._attr_suggested_object_id = f"baxi_{serial_slug}_zone_1"

    @property
    def device_info(self) -> dict:
        return build_device_info(self._api)

    @property
    def available(self) -> bool:
        return super().available and (
            self._api.zone1_mode is not None or self._api.zone1_schedule_temp is not None
        )

    @property
    def current_temperature(self) -> float | None:
        return self._api.temp_int

    @property
    def hvac_mode(self) -> HVACMode | None:
        return _HVAC_MODE_OF_ZONE_MODE.get(self._api.zone1_mode)

    @property
    def preset_mode(self) -> str | None:
        return _PRESET_OF_ZONE_MODE.get(self._api.zone1_mode)

    @property
    def target_temperature(self) -> float | None:
        mode = self._api.zone1_mode
        if mode == "Automatico":
            # Il programma, non il setpoint: subito giusto anche nei secondi
            # dopo un cambio di modo, quando il setpoint è ancora il vecchio.
            schedule = self._api.zone1_schedule_temp
            return schedule if schedule is not None else self._api.zone1_comfort_setpoint
        if mode in ("Comfort", "Risparmio"):
            return self._api.zone1_comfort_setpoint
        return None  # Spento: nessuna richiesta

    @property
    def hvac_action(self) -> HVACAction | None:
        if self._api.zone1_mode == "Spento":
            return HVACAction.OFF
        active = getattr(self._api, "heating_active", None)
        if active == "On":
            return HVACAction.HEATING
        if active == "Off":
            return HVACAction.IDLE
        # Caldaie senza "Riscaldamento per counter": la fiamma si accende anche
        # per l'acqua calda, che si riconosce da "Sanitario on".
        flame = getattr(self._api, "flame_status", None)
        if flame == "On":
            if getattr(self._api, "sanitary_on", None) == "On":
                return HVACAction.IDLE
            return HVACAction.HEATING
        if flame == "Off":
            return HVACAction.IDLE
        return None

    @property
    def extra_state_attributes(self) -> dict:
        # L'API azzera la fine del Comfort fuori dal Comfort.
        comfort_end = self._api.zone1_comfort_end
        return {
            "modo_zona": self._api.zone1_mode,
            "temperatura_programmata": self._api.zone1_schedule_temp,
            "setpoint_zona": self._api.zone1_comfort_setpoint,
            "comfort_fino_alle": comfort_end.isoformat() if comfort_end else None,
        }

    async def async_set_temperature(self, **kwargs) -> None:
        raise _read_only_error()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        raise _read_only_error()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        raise _read_only_error()


async def async_setup_entry(hass, entry, async_add_entities):
    api = entry.runtime_data.api
    coordinator = entry.runtime_data.coordinator
    async_add_provided_entities(
        hass, api, "climate", [BaxiZone1Climate(coordinator, api)], async_add_entities,
    )
