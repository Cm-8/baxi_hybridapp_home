"""
Device action for Baxi Hybrid App custom integration for Home Assistant.

custom_components/baxi_hybridapp_home/device_action.py
"""

from __future__ import annotations

from typing import Any
import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import (
    DOMAIN,
    SANITARY_MIN_TEMP,
    SANITARY_MAX_TEMP,
)

# Tipi di azione supportati
ACTION_TYPES = {"set_comfort", "set_eco"}

# Schema di validazione per l’azione
ACTION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): str,
        vol.Required("domain"): vol.In([DOMAIN]),   # <— AGGIUNGI QUESTA RIGA
        vol.Required("type"): vol.In(ACTION_TYPES),
        vol.Required("value"): vol.All(
            vol.Coerce(int),
            vol.Range(min=SANITARY_MIN_TEMP, max=SANITARY_MAX_TEMP),
        ),
    }
)

async def async_get_actions(hass: HomeAssistant, device_id: str) -> list[dict[str, Any]]:
    """Ritorna l’elenco delle azioni disponibili per questo device."""
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get(device_id)
    if not device:
        return []

    # Espone due azioni: SET Comfort/Eco
    return [
        {ATTR_DEVICE_ID: device_id, "domain": DOMAIN, "type": "set_comfort", "value": SANITARY_MIN_TEMP},
        {ATTR_DEVICE_ID: device_id, "domain": DOMAIN, "type": "set_eco", "value": SANITARY_MIN_TEMP},
    ]

async def async_call_action_from_config(
    hass: HomeAssistant, config: ConfigType, variables: dict[str, Any], context=None
) -> None:
    """Esegue l’azione selezionata nel flow Automazioni."""
    config = ACTION_SCHEMA(config)
    action_type = config["type"]
    value = config["value"]

    if action_type == "set_comfort":
        await hass.services.async_call(
            DOMAIN,
            "set_comfort",
            {"value": value},
            blocking=True,
            context=context,
        )
    elif action_type == "set_eco":
        await hass.services.async_call(
            DOMAIN,
            "set_eco",
            {"value": value},
            blocking=True,
            context=context,
        )

async def async_validate_action_config(hass: HomeAssistant, config: ConfigType) -> ConfigType:
    """Valida lo schema dell’azione quando la salvi in UI/YAML."""
    return ACTION_SCHEMA(config)
