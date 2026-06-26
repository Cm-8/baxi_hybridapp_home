"""
Tabelle delle metriche Servitly per Baxi Hybrid App.

Questo modulo concentra:
- SimpleMetricSpec + SIMPLE_METRICS  → metriche "semplici" (un valore per
  metricName), lette dal dispatcher in api.fetch_simple_metrics
- BaxiEnergySensorEntityDescription + ENERGY_SENSOR_TYPES → sensori energia,
  letti da fetch_energy_metrics ed esposti come entità HA in sensor.py

Aggiungere una metrica = una sola riga in una di queste tabelle. Il file
const.py resta dedicato alle costanti pure (DOMAIN, credenziali statiche,
parameter ID, limiti); l'API client (api.py) resta dedicato al
trasporto HTTP.

custom_components/baxi_hybridapp_home/metrics.py
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy

__all__ = [
    "SimpleMetricSpec",
    "SIMPLE_METRICS",
    "BaxiEnergySensorEntityDescription",
    "ENERGY_SENSOR_TYPES",
]


# ---------------------------------------------------------------------------
# Metriche "semplici" — un singolo valore per metricName Servitly.
# Lette in sequenza dal dispatcher fetch_simple_metrics in api.py.
# ---------------------------------------------------------------------------

def _parse_float(raw: Any) -> float:
    """Parser per metriche numeriche float."""
    return float(raw)


def _parse_passthrough(raw: Any) -> Any:
    """Parser identità: memorizza il raw così com'è (interpretazione lato sensore)."""
    return raw


def _make_mapper(mapping: dict, *, normalize: bool = False) -> Callable[[Any], str]:
    """
    Costruisce un parser che mappa il raw value tramite un dizionario.

    - normalize=True applica str(raw).strip().lower() prima del lookup
      (utile per valori misti "0"/"1"/"true"/"false").
    - Chiave non trovata → "Sconosciuto ({raw})".
    """
    def _parse(raw: Any) -> str:
        key = str(raw).strip().lower() if normalize else raw
        if key in mapping:
            return mapping[key]
        return f"Sconosciuto ({raw})"
    return _parse


@dataclass(frozen=True)
class SimpleMetricSpec:
    """Descrittore di una metrica letta come singolo valore da /data/values."""
    attr: str                            # attributo sull'istanza API (anche per `<attr>_timestamp`)
    metric_name: str                     # metricName esatto Servitly (italiano)
    parser: Callable[[Any], Any]         # raw → valore memorizzato
    log_emoji: str = "📥"                # emoji nel log info (override per famiglia di metriche)


SIMPLE_METRICS: tuple[SimpleMetricSpec, ...] = (
    # --- Float / numerici | temperatura ---------------------------------------------------
    SimpleMetricSpec("temp_ext", "Temperatura esterna", _parse_float, log_emoji="🌡️"),
    SimpleMetricSpec("temp_int", "Zona 1 - Temperatura ambiente", _parse_float, log_emoji="🌡️"),
    SimpleMetricSpec("boiler_flow_temp", "Temperatura di mandata", _parse_float, log_emoji="🌡️"),
    SimpleMetricSpec("dhw_storage_temp", "Temperatura accumulo sanitario", _parse_float, log_emoji="🌡️"),
    SimpleMetricSpec("dhw_aux_storage_temp", "Sonda accumulo ausiliario", _parse_float, log_emoji="🌡️"),
    SimpleMetricSpec("pdc_exit_temp", "Temperatura uscita pdc", _parse_float, log_emoji="🌡️"),
    SimpleMetricSpec("pdc_return_temp", "Temperatura ritorno pdc", _parse_float, log_emoji="🌡️"),
    SimpleMetricSpec("setpoint_instant_temp", "Set-point sanitario istantaneo", _parse_float, log_emoji="🌡️"),
    SimpleMetricSpec("setpoint_comfort_temp", "Set-point sanitario comfort", _parse_float, log_emoji="🌡️"),
    SimpleMetricSpec("setpoint_eco_temp", "Set-point sanitario eco", _parse_float, log_emoji="🌡️"),
    SimpleMetricSpec("setpoint_raffrescamento_temp", "Set-point raffrescamento", _parse_float, log_emoji="🌡️"),

    # --- Float / numerici | pressione ---------------------------------------------------
    SimpleMetricSpec("water_pressure", "Pressione impianto", _parse_float),

    # --- Float / numerici | stato e potenza ---------------------------------------------------
    SimpleMetricSpec("power_boiler", "Potenza caldaia - istantanea", _parse_float),
    SimpleMetricSpec("power_pdc", "Potenza PDC - istantanea", _parse_float),
    SimpleMetricSpec("sanitary_request_status", "Stato richiesta sanitario", _parse_float),

    # --- Stringhe mappate (codici Servitly → testo leggibile) ---------------
    SimpleMetricSpec(
        "sanitary_on", "Sanitario on",
        _make_mapper({"0": "Off", "0_1": "On", "1": "On"}),
    ),
    SimpleMetricSpec(
        "system_mode", "Modo Impianto",
        _make_mapper({None: "Automatico", "0000": "Standby", "0005": "Solo Sanitario"}),
    ),
    SimpleMetricSpec(
        "season_mode", "Modo Stagione",
        _make_mapper({
            "0001": "Inverno",
            "0002": "Estate",
            "0003": "Estate/Inverno automatico",
            "0004": "Estate/Inverno remoto",
        }),
    ),
    SimpleMetricSpec(
        "system_operation_mode", "Modo funzionamento sistema",
        # L'API manda valori con zeri iniziali ("0001", "0007").
        # Aggiunte anche le forme senza zeri ("1", "7") per robustezza.
        _make_mapper({
            "0001": "Automatico", "1": "Automatico",
            "0007": "Standby",    "7": "Standby",
        }, normalize=True),
    ),
    SimpleMetricSpec(
        "flame_status", "Flame status",
        _make_mapper(
            {"0": "Off", "1": "On", "false": "Off", "true": "On"},
            normalize=True,
        ),
    ),

    # --- Passthrough: il sensore HA decide come interpretare il raw ---------
    SimpleMetricSpec("system_operation_icon", "Icona funzionamento sistema", _parse_passthrough),
    SimpleMetricSpec("status_boiler", "Stato caldaia", _parse_passthrough),
    SimpleMetricSpec("status_pdc", "Stato PDC", _parse_passthrough),
)


# ---------------------------------------------------------------------------
# Sensori energia — letti da fetch_energy_metrics ed esposti come entità HA
# in sensor.BaxiEnergySensor (entity_description-based).
# ---------------------------------------------------------------------------

@dataclass(frozen=True, kw_only=True)
class BaxiEnergySensorEntityDescription(SensorEntityDescription):
    """SensorEntityDescription + metric_name esatto per Servitly."""
    metric_name: str


ENERGY_SENSOR_TYPES: tuple[BaxiEnergySensorEntityDescription, ...] = (
    BaxiEnergySensorEntityDescription(
        key="energia_totale_pdc",
        name="Energia totale PDC",
        metric_name="Energia totale pdc",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    BaxiEnergySensorEntityDescription(
        key="energia_totale_caldaia",
        name="Energia totale caldaia",
        metric_name="Energia totale caldaia",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    BaxiEnergySensorEntityDescription(
        key="energia_totale_resistenze",
        name="Energia totale resistenze",
        metric_name="Energia totale delle resistenze",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    BaxiEnergySensorEntityDescription(
        key="energia_totale_globale",
        name="Energia totale globale",
        metric_name="Energia totale globale",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    BaxiEnergySensorEntityDescription(
        key="energia_totale_globale_day",
        name="Energia totale globale per day",
        metric_name="Energia totale globale per day",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    BaxiEnergySensorEntityDescription(
        key="energia_parziale_caldaia",
        name="Energia parziale caldaia",
        metric_name="Energia parziale caldaia",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    BaxiEnergySensorEntityDescription(
        key="energia_parziale_pdc",
        name="Energia parziale PDC",
        metric_name="Energia parziale pdc",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    BaxiEnergySensorEntityDescription(
        key="energia_parziale_resistenze",
        name="Energia parziale resistenze",
        metric_name="Energia parziale delle resistenze",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)
