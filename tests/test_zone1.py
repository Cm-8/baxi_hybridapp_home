"""Zona 1: programma del riscaldamento, metriche della zona e termostato in sola lettura (#27)."""

import asyncio
import json
from datetime import datetime
from types import SimpleNamespace

import pytest
from homeassistant.components.climate import ClimateEntityFeature, HVACAction, HVACMode
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from custom_components.baxi_hybridapp_home import climate
from custom_components.baxi_hybridapp_home.api import HEATING_SCHEDULE_METRIC, WIRED_METRIC_NAMES
from custom_components.baxi_hybridapp_home.climate import BaxiZone1Climate
from custom_components.baxi_hybridapp_home.metrics import SIMPLE_METRICS
from custom_components.baxi_hybridapp_home.schedule import SCHEDULE_TZ, heating_schedule_state

from .conftest import values_response

DAYS = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
# Programma di una caldaia LUNA IN PLUS (#27): stesso giorno per tutta la settimana.
LUNA = json.dumps({d: [
    {"start": "05:30", "end": "07:00", "params": {"Temperatura": 21}},
    {"start": "07:00", "end": "19:30", "params": {"Temperatura": 20.5}},
    {"start": None, "end": None, "params": {"Temperatura": 20.5}},
] for d in DAYS})
# Programma di fabbrica visto sugli ibridi.
FACTORY = json.dumps({d: [
    {"start": "07:30", "end": "08:30", "params": {"Temperatura": 22}},
    {"start": "12:00", "end": "13:30", "params": {"Temperatura": 22}},
    {"start": "18:00", "end": "22:30", "params": {"Temperatura": 22}},
    {"start": None, "end": None, "params": {"Temperatura": 16}},
] for d in DAYS})


def at(day, hh, mm=0):
    """Ora italiana; il 9/11/2026 è un lunedì."""
    return datetime(2026, 11, day, hh, mm, tzinfo=SCHEDULE_TZ)


def parser_for(attr):
    return next(spec.parser for spec in SIMPLE_METRICS if spec.attr == attr)


# --- Programma ---------------------------------------------------------------------


def test_luna_schedule_in_a_slot():
    state = heating_schedule_state(LUNA, at(9, 6))
    assert state["temperature"] == 21.0
    assert state["next_change"] == at(9, 7) and state["next_temperature"] == 20.5
    assert state["base_temperature"] == 20.5
    # La fascia 07:00-19:30 ha la stessa temperatura del resto: unita.
    assert state["today"] == [
        {"dalle": "00:00", "alle": "05:30", "temperatura": 20.5},
        {"dalle": "05:30", "alle": "07:00", "temperatura": 21.0},
        {"dalle": "07:00", "alle": "24:00", "temperatura": 20.5},
    ]


def test_next_change_can_be_tomorrow():
    state = heating_schedule_state(LUNA, at(9, 20))
    assert state["temperature"] == 20.5
    assert state["next_change"] == at(10, 5, 30) and state["next_temperature"] == 21.0


def test_factory_schedule_outside_the_slots():
    state = heating_schedule_state(FACTORY, at(9, 7))
    assert state["temperature"] == 16.0
    assert state["next_change"] == at(9, 7, 30) and state["next_temperature"] == 22.0


@pytest.mark.parametrize("end", ["24:00", "00:00"])
def test_slot_until_midnight(end):
    raw = {"Lun": [{"start": "18:00", "end": end, "params": {"Temperatura": 21}},
                   {"start": None, "end": None, "params": {"Temperatura": 17}}]}
    state = heating_schedule_state(raw, at(9, 23, 30))
    assert state["temperature"] == 21.0
    assert state["today"][-1] == {"dalle": "18:00", "alle": "24:00", "temperatura": 21.0}


@pytest.mark.parametrize("raw", ["1", "[]"])
def test_invalid_schedule_raises(raw):
    with pytest.raises(ValueError):
        heating_schedule_state(raw, at(9, 6))


# --- Lettura dal cloud ---------------------------------------------------------------


def test_schedule_metric_is_read_every_cycle():
    assert HEATING_SCHEDULE_METRIC in WIRED_METRIC_NAMES


def test_fetch_schedule(api, cloud):
    cloud[HEATING_SCHEDULE_METRIC] = values_response(LUNA)
    api.fetch_heating_schedule(at(9, 6))
    assert api.zone1_schedule_status == "ok"
    assert api.zone1_schedule_temp == 21.0 and api.zone1_schedule_next_temp == 20.5


def test_failed_request_recomputes_the_previous_schedule(api, cloud):
    cloud[HEATING_SCHEDULE_METRIC] = values_response(LUNA)
    api.fetch_heating_schedule(at(9, 6))
    del cloud[HEATING_SCHEDULE_METRIC]  # richiesta fallita
    api.fetch_heating_schedule(at(9, 8))
    assert api.zone1_schedule_status == "ok" and api.zone1_schedule_temp == 20.5


def test_no_data_schedule_is_empty(api, cloud):
    cloud[HEATING_SCHEDULE_METRIC] = values_response("---")
    api.fetch_heating_schedule(at(9, 6))
    assert api.zone1_schedule_status == "empty" and api.zone1_schedule_temp is None


def test_invalid_schedule_does_not_raise(api, cloud, caplog):
    cloud[HEATING_SCHEDULE_METRIC] = values_response("1")
    with caplog.at_level("WARNING"):
        api.fetch_heating_schedule(at(9, 6))
    assert api.zone1_schedule_status == "error" and api.zone1_schedule_temp is None
    assert any("Programma riscaldamento" in r.getMessage() for r in caplog.records)


def test_schedule_missing_from_model_is_not_requested(api, cloud):
    api.model_metrics = frozenset(n for n in WIRED_METRIC_NAMES if n != HEATING_SCHEDULE_METRIC)
    api.fetch_heating_schedule(at(9, 6))
    assert api.zone1_schedule_status == "empty" and not cloud.calls
    assert not api.provides("zone1_schedule_temp")


# --- Metriche della zona ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("0000", "Spento"), ("0001", "Automatico"), ("0002", "Risparmio"), ("0003", "Comfort"),
     ("0004", "Sconosciuto (0004)")],
)
def test_zone_mode(raw, expected):
    assert parser_for("zone1_mode")(raw) == expected


def test_comfort_end_is_local_time():
    assert parser_for("zone1_comfort_end")("2026-11-07 19:41") == at(7, 19, 41)
    with pytest.raises(ValueError):
        parser_for("zone1_comfort_end")("1794089470755")


# --- Termostato ----------------------------------------------------------------------------


@pytest.fixture
def coordinator():
    return SimpleNamespace(last_update_success=True)


@pytest.fixture
def thermostat(api, coordinator):
    api.temp_int = 21.9
    api.zone1_schedule_temp = 20.5
    api.zone1_comfort_setpoint = 23.0
    api.zone1_comfort_end = at(7, 19, 41)
    return BaxiZone1Climate(coordinator, api)


def test_thermostat_follows_the_schedule_in_automatico(api, thermostat):
    api.zone1_mode = "Automatico"
    assert thermostat.available
    assert thermostat.hvac_mode == HVACMode.AUTO
    assert thermostat.current_temperature == 21.9 and thermostat.target_temperature == 20.5
    assert thermostat.extra_state_attributes["comfort_fino_alle"] is None
    assert thermostat.supported_features == ClimateEntityFeature.TARGET_TEMPERATURE


def test_thermostat_in_comfort(api, thermostat):
    api.zone1_mode = "Comfort"
    assert thermostat.hvac_mode == HVACMode.HEAT and thermostat.target_temperature == 23.0
    assert thermostat.extra_state_attributes["comfort_fino_alle"] == at(7, 19, 41).isoformat()


def test_thermostat_in_risparmio_and_off(api, thermostat):
    api.zone1_mode = "Risparmio"
    assert thermostat.hvac_mode == HVACMode.HEAT and thermostat.target_temperature is None
    api.zone1_mode = "Spento"
    assert thermostat.hvac_mode == HVACMode.OFF and thermostat.target_temperature is None
    assert thermostat.hvac_action == HVACAction.OFF


def test_thermostat_action_from_heating_running(api, thermostat):
    api.zone1_mode = "Automatico"
    assert thermostat.hvac_action is None  # modello senza "Riscaldamento per counter"
    api.heating_active = "On"
    assert thermostat.hvac_action == HVACAction.HEATING
    api.heating_active = "Off"
    assert thermostat.hvac_action == HVACAction.IDLE


def test_thermostat_without_values_is_unavailable(api, coordinator):
    assert not BaxiZone1Climate(coordinator, api).available


def test_thermostat_is_read_only(thermostat):
    for call in (thermostat.async_set_temperature(temperature=22),
                 thermostat.async_set_hvac_mode(HVACMode.OFF)):
        with pytest.raises(ServiceValidationError) as err:
            asyncio.run(call)
        assert err.value.translation_key == "climate_read_only"


class FakeRegistry:
    def async_get_entity_id(self, platform, domain, unique_id):
        return None


def setup_climate(api, coordinator, monkeypatch):
    monkeypatch.setattr(er, "async_get", lambda hass: FakeRegistry())
    added = []
    entry = SimpleNamespace(runtime_data=SimpleNamespace(api=api, coordinator=coordinator))
    asyncio.run(climate.async_setup_entry(None, entry, lambda entities, *a: added.extend(entities)))
    return [e.unique_id for e in added]


def test_thermostat_created_only_with_the_schedule(api, coordinator, monkeypatch):
    assert setup_climate(api, coordinator, monkeypatch) == ["baxi_climate_zone_1"]
    api.model_metrics = frozenset(n for n in WIRED_METRIC_NAMES if n != HEATING_SCHEDULE_METRIC)
    assert setup_climate(api, coordinator, monkeypatch) == []
