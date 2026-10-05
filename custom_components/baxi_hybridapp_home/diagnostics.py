"""
Diagnostics per Baxi Hybrid App custom integration.

Scaricabile da: Impostazioni → Dispositivi e servizi → Baxi HybridApp Home
→ ⋮ → Scarica la diagnostica.

Contiene lo snapshot dei valori correnti (già in RAM, nessuna chiamata extra),
i cataloghi statici del modello (comandi, parametri, metriche), l'ultimo
valore di ogni metrica del catalogo e gli ultimi 10 cambi di ogni metrica
letta dall'integrazione, scaricati on-demand al momento del download. Credenziali, seriale, thingId e valori personali (rete WiFi,
seriale del gateway, nomi delle zone) sono redatti.

custom_components/baxi_hybridapp_home/diagnostics.py
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import __version__ as ha_version
from homeassistant.core import HomeAssistant

from .api import WIRED_METRIC_NAMES
from .const import INTEGRATION_VERSION
from .metrics import ENERGY_SENSOR_TYPES, SIMPLE_METRICS

# thingId: identificativo del device sul cloud, non serve per le segnalazioni
# (il modello è già in thing_definition_*).
TO_REDACT = {"username", "password", "serialNumber", "thingId"}
# Metriche del catalogo con valori personali: nome della rete WiFi, seriale
# del gateway, nomi delle zone scelti dall'utente.
CATALOG_REDACT = {"WiFi ssid", "Serial Number Gateway", *(f"Nome zona {n}" for n in range(1, 9))}


def _catalog_values(api, metrics: list) -> dict[str, Any]:
    """Ultimo valore di ogni metrica del catalogo (lettura multipla, a blocchi da 50).

    Serve a vedere i valori reali delle metriche che l'integrazione non legge
    (unità, codici, metriche ferme) senza attivare il log di debug. Bloccante:
    va chiamata nell'executor. Non solleva.
    """
    names = [m.get("name") for m in metrics if m.get("name")]
    if not names:
        return {"values": "catalogo non disponibile"}
    try:
        samples = api._fetch_last_values(names)
    except Exception as err:  # diagnostica best-effort: mai un errore al download
        return {"values": f"lettura non riuscita: {err}"}
    if samples is None:
        return {"values": "lettura non riuscita"}
    return {
        "values": async_redact_data({n: samples[n] for n in names if n in samples}, CATALOG_REDACT),
        # Metriche del modello per cui il cloud non ha nessun valore su questo impianto.
        "without_data": [n for n in names if n not in samples],
    }


# Cambi recenti mostrati per ogni metrica letta dall'integrazione.
HISTORY_SIZE = 10


def _recent_changes(api) -> dict[str, Any]:
    """Ultimi HISTORY_SIZE cambi di ogni metrica letta dall'integrazione.

    Mostra sequenze e codici che un solo valore non rivela (es. Stato PDC
    0002 → 0001 → 0000). Una richiesta /data/values per metrica, solo al
    download. Bloccante: va chiamata nell'executor. Non solleva.
    """
    changes: dict[str, Any] = {}
    for name in WIRED_METRIC_NAMES:
        if not api.has_metric(name):
            continue
        try:
            history = api.fetch_metric_history(name, HISTORY_SIZE)
        except Exception as err:  # diagnostica best-effort: mai un errore al download
            history = f"lettura non riuscita: {err}"
        changes[name] = history if history is not None else "lettura non riuscita"
    return changes


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
    api = entry.runtime_data.api

    # Cataloghi statici del modello: fetch on-demand (3 GET), sempre freschi.
    capabilities = await hass.async_add_executor_job(api.fetch_capabilities)
    # Ultimo valore di tutte le metriche del catalogo (~7 richieste multiple).
    catalog_values = await hass.async_add_executor_job(
        _catalog_values, api, capabilities.get("metrics") or []
    )
    # Ultimi 10 cambi delle metriche lette (~48 richieste singole).
    recent_changes = await hass.async_add_executor_job(_recent_changes, api)

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
        "options": dict(entry.options),
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
        # Metriche lette dall'integrazione ma assenti dal catalogo del modello:
        # non vengono richieste e le entità relative non sono create.
        "metrics_not_on_model": (
            [n for n in WIRED_METRIC_NAMES if not api.has_metric(n)]
            if api.model_metrics is not None else "catalogo non letto"
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
        # Ultimo valore + timestamp di ogni metrica del catalogo (anche quelle
        # che l'integrazione non legge); i valori personali sono redatti.
        "catalog_values": catalog_values,
        # Ultimi 10 cambi (dal più recente) di ogni metrica letta dall'integrazione.
        "recent_changes": recent_changes,
    }
