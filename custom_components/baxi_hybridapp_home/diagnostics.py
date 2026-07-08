"""
Diagnostics per Baxi Hybrid App custom integration.

Scaricabile da: Impostazioni → Dispositivi e servizi → Baxi HybridApp Home
→ ⋮ → Scarica la diagnostica.

Contiene lo snapshot dei valori correnti (già in RAM, nessuna chiamata extra)
e i cataloghi statici del modello (comandi, parametri, metriche) scaricati
on-demand al momento del download. Credenziali e seriale sono redatti.

custom_components/baxi_hybridapp_home/diagnostics.py
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import __version__ as ha_version
from homeassistant.core import HomeAssistant

from .const import DATA_KEY_API, DOMAIN, INTEGRATION_VERSION
from .metrics import ENERGY_SENSOR_TYPES, SIMPLE_METRICS

TO_REDACT = {"username", "password", "serialNumber"}


def _compact_commands(items: list) -> list[dict]:
    """Riduce i comandi ai soli campi utili (id, nome, condizione di visibilità)."""
    out = []
    for c in items or []:
        oc = c.get("onCondition") or {}
        out.append({
            "id": c.get("id"),
            "name": c.get("name"),
            "on_condition": {
                "metric": (oc.get("metric") or {}).get("name"),
                "predicate": oc.get("predicate"),
                "value": oc.get("value"),
            } if oc else None,
        })
    return out


def _compact_parameters(items: list) -> list[dict]:
    """Riduce i parametri di configurazione a id, nome, tipo e range."""
    return [
        {
            "id": p.get("id"),
            "name": p.get("name"),
            "type": p.get("type"),
            "min": p.get("minValue"),
            "max": p.get("maxValue"),
            "step": p.get("stepValue"),
        }
        for p in items or []
    ]


def _compact_metrics(items: list) -> list[dict]:
    """Riduce il catalogo metriche a id, nome, unità e tipo valore."""
    return [
        {
            "id": m.get("id"),
            "name": m.get("name"),
            "unit": m.get("unit"),
            "value_type": m.get("valueType"),
        }
        for m in items or []
    ]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Ritorna la diagnostica per la config entry."""
    api = hass.data[DOMAIN][DATA_KEY_API]

    # Cataloghi statici del modello: fetch on-demand (3 GET), sempre freschi.
    capabilities = await hass.async_add_executor_job(api.fetch_capabilities)

    # Snapshot dei valori correnti: tutto già in RAM, nessuna chiamata.
    simple_values = {
        spec.attr: {
            "metric_name": spec.metric_name,
            "value": getattr(api, spec.attr, None),
            "timestamp": getattr(api, f"{spec.attr}_timestamp", None),
        }
        for spec in SIMPLE_METRICS
    }
    energy_values = {
        desc.key: {
            "metric_name": desc.metric_name,
            "value": getattr(api, desc.key, None),
            "timestamp": (api.energy_timestamp or {}).get(desc.key),
        }
        for desc in ENERGY_SENSOR_TYPES
    }

    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "versions": {
            "home_assistant": ha_version,
            "integration": INTEGRATION_VERSION,
        },
        "device": async_redact_data(
            {
                "thingId": api.thingId,
                "model": api.thingModel,
                "thing_definition_name": api.thingDefinitionName,
                "thing_definition_id": api.thingDefinitionId,
                "firmware": api.thingFirmware,
                "sw_version": api.thingSwVersion,
                "serialNumber": api.serialNumber,
            },
            TO_REDACT,
        ),
        "current_values": {
            "simple_metrics": simple_values,
            "energy": energy_values,
            "sanitary_scheduler": {
                "status": api.sanitary_scheduler_status,
                "mode_now": api.sanitary_mode_now,
                "next_change": api.sanitary_next_change,
                "today_summary": api.sanitary_today_summary,
            },
            "alerts": {
                "active_failure": api.active_failure_alert is not None,
                "active_warning": api.active_warning_alert is not None,
                "failure_count_24h": api.failure_count_24h,
                "failure_count_7d": api.failure_count_7d,
                "warning_count_24h": api.warning_count_24h,
                "warning_count_7d": api.warning_count_7d,
            },
        },
        "capabilities": {
            "commands": _compact_commands(capabilities.get("commands")),
            "configuration_parameters": _compact_parameters(
                capabilities.get("configuration_parameters")
            ),
            "metrics": _compact_metrics(capabilities.get("metrics")),
        },
    }
