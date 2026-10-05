"""Catalogo metriche del modello, entità create solo per i dati presenti, boost e nuovi sensori."""

import asyncio
from types import SimpleNamespace

import pytest
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from custom_components.baxi_hybridapp_home import sensor
from custom_components.baxi_hybridapp_home.api import WIRED_METRIC_NAMES, _mask_url
from custom_components.baxi_hybridapp_home.button import BaxiBoostButton
from custom_components.baxi_hybridapp_home.const import COMMAND_ID_BOOST_SANITARIO, PARAM_ID_BOOST_MAX_DURATION
from custom_components.baxi_hybridapp_home.number import BaxiBoostDurationNumber
from custom_components.baxi_hybridapp_home.sensor import DailyModeTimeSensor

from .conftest import values_response

NO_FLAME = [n for n in WIRED_METRIC_NAMES if n != "Flame status"]


@pytest.fixture
def coordinator():
    return SimpleNamespace(last_update_success=True)


class FakeHass:
    """Quanto serve alle entità per una scrittura: executor, logbook, task in background."""

    def __init__(self):
        self.logbook = []
        self.tasks = 0
        self.services = SimpleNamespace(async_call=self._call)

    async def async_add_executor_job(self, func, *args):
        return func(*args)

    async def _call(self, domain, service, data, blocking=False):
        self.logbook.append(data)

    def async_create_task(self, coro):
        coro.close()  # il refresh differito non serve nei test
        self.tasks += 1


def entity(cls, *args):
    obj = cls(*args)
    obj.hass, obj.entity_id = FakeHass(), "x.test"
    obj.async_write_ha_state = lambda: None
    return obj


# --- Catalogo del modello -------------------------------------------------------


def test_catalog_marks_missing_metrics(api, cloud):
    api.thingDefinitionId = "def-1"
    cloud.catalog = [{"name": n} for n in NO_FLAME]
    assert api.fetch_model_metrics()
    assert not api.has_metric("Flame status") and api.has_metric("Temperatura esterna")
    assert not api.provides("flame_status") and api.provides("temp_ext")
    assert api.provides("failure_count_24h")  # non dipende da una metrica


def test_catalog_failure_keeps_reading_everything(api, cloud):
    api.thingDefinitionId = "def-1"
    assert not api.fetch_model_metrics()
    assert api.model_metrics is None and api.has_metric("Flame status")
    assert api.request_stats() == (0, [])  # non conta tra gli esiti del ciclo


def test_metric_not_on_model_is_never_requested(api, cloud):
    api.model_metrics = frozenset(NO_FLAME)
    cloud.last_values = {n: ("1", 1_700_000_000_000) for n in NO_FLAME}
    api.flame_status = "On"
    api.fetch_all_metrics()
    assert cloud.calls[0] == ("lastValues", NO_FLAME)
    assert not [c for c in cloud.calls if c[0] == "values"]  # nessuna lettura singola
    assert api.flame_status is None


def test_without_catalog_missing_metric_is_read_singly(api, cloud):
    cloud.last_values = {n: ("1", 1_700_000_000_000) for n in NO_FLAME}
    cloud["Flame status"] = values_response("1")
    api.fetch_all_metrics()
    assert ("values", "Flame status") in cloud.calls
    assert api.flame_status == "On"


# --- Entità create solo per i dati presenti ----------------------------------------


class FakeRegistry:
    def __init__(self, existing):
        self.existing, self.removed = existing, []

    def async_get_entity_id(self, platform, domain, unique_id):
        return self.existing.get((platform, unique_id))

    def async_remove(self, entity_id):
        self.removed.append(entity_id)


def setup_sensors(api, coordinator, monkeypatch, existing=None):
    registry = FakeRegistry(existing or {})
    monkeypatch.setattr(er, "async_get", lambda hass: registry)
    added = []
    entry = SimpleNamespace(runtime_data=SimpleNamespace(api=api, coordinator=coordinator))
    asyncio.run(sensor.async_setup_entry(None, entry, lambda entities, *a: added.extend(entities)))
    return {e.unique_id for e in added}, registry


def test_sensor_for_missing_metric_is_not_created_and_removed(api, coordinator, monkeypatch):
    api.model_metrics = frozenset(NO_FLAME)
    existing = {("sensor", "baxi_flame_status"): "sensor.stato_fiamma"}
    created, registry = setup_sensors(api, coordinator, monkeypatch, existing)
    assert "baxi_flame_status" not in created and "baxi_external_temperature" in created
    assert "baxi_failure_count_24h" in created  # alert: non dipende dal catalogo
    assert registry.removed == ["sensor.stato_fiamma"]


def test_all_sensors_created_without_catalog(api, coordinator, monkeypatch):
    created, registry = setup_sensors(api, coordinator, monkeypatch)
    assert "baxi_flame_status" in created and not registry.removed


# --- Boost sanitario -----------------------------------------------------------------


def test_boost_button_sends_command(api, coordinator, monkeypatch):
    sent = []
    monkeypatch.setattr(api, "send_command", lambda cid: sent.append(cid) or True)
    button = entity(BaxiBoostButton, coordinator, api)
    asyncio.run(button.async_press())
    assert sent == [COMMAND_ID_BOOST_SANITARIO]
    assert button.hass.tasks == 1  # refresh differito per leggere lo stato


def test_boost_button_rejected_raises(api, coordinator, monkeypatch):
    monkeypatch.setattr(api, "send_command", lambda cid: False)
    with pytest.raises(HomeAssistantError) as err:
        asyncio.run(entity(BaxiBoostButton, coordinator, api).async_press())
    assert err.value.translation_key == "boost_failed"


def test_boost_duration_is_clamped_and_written(api, coordinator, monkeypatch):
    written = []
    monkeypatch.setattr(api, "set_configuration_parameter", lambda pid, v: written.append((pid, v)) or True)
    asyncio.run(entity(BaxiBoostDurationNumber, coordinator, api).async_set_native_value(500))
    assert written == [(PARAM_ID_BOOST_MAX_DURATION, 120)]
    assert api.boost_max_duration == 120.0


# --- Tempi giornalieri -------------------------------------------------------------


def test_daily_time_sensor_has_no_statistics_until_unit_is_confirmed(api, coordinator):
    api.daily_time_heat_pump, api.daily_time_heat_pump_timestamp = 3_600_000.0, 1_700_000_000_000
    s = DailyModeTimeSensor(coordinator, api, "daily_time_heat_pump")
    assert s.device_class == SensorDeviceClass.DURATION and s.state_class is None
    assert not s.entity_registry_enabled_default
    assert s.native_value == 3_600_000.0
    assert s.extra_state_attributes["metric_timestamp_utc"].startswith("2023-11-14")


# --- Identificativi mascherati ------------------------------------------------------


def test_thing_id_masked_in_logged_urls():
    url = "https://x/api/data/values?thingId=655f0852c9683d184890e7dd&metricName=A"
    assert _mask_url(url) == "https://x/api/data/values?thingId=***e7dd&metricName=A"
