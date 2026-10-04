"""Tutte le metriche del ciclo con una sola richiesta GET /data/lastValues (fetch_all_metrics)."""

import json
from datetime import timedelta

from homeassistant.util import dt as dt_util

from custom_components.baxi_hybridapp_home.api import SANITARY_SCHEDULER_METRIC, WIRED_METRIC_NAMES
from custom_components.baxi_hybridapp_home.metrics import ENERGY_SENSOR_TYPES

from .conftest import values_response

DAYS = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
SCHEDULE = json.dumps({
    d: [{"start": "08:00", "end": "22:30", "params": {}},
        {"start": None, "end": None, "params": {"Set-point sanitario eco": "40"}}]
    for d in DAYS
})
DAY = next(d for d in ENERGY_SENSOR_TYPES if d.key == "energia_totale_globale_day")


def now_ms(days_ago=0):
    return int((dt_util.now() - timedelta(days=days_ago)).timestamp() * 1000)


def fill_bulk(cloud):
    """Lettura multipla con un valore valido per ogni metrica del ciclo."""
    ts = now_ms()
    cloud.last_values = {n: ("1", ts) for n in WIRED_METRIC_NAMES}
    cloud.last_values[SANITARY_SCHEDULER_METRIC] = (SCHEDULE, ts)
    for desc in ENERGY_SENSOR_TYPES:
        cloud.last_values[desc.metric_name] = ("12,5", ts)


def single_calls(cloud):
    return [name for kind, name in cloud.calls if kind == "values"]


def test_whole_cycle_in_one_request(api, cloud):
    fill_bulk(cloud)
    api.fetch_all_metrics()
    assert cloud.calls == [("lastValues", list(WIRED_METRIC_NAMES))]
    assert api.request_stats() == (1, [])
    assert api.temp_ext == 1.0
    assert api.sanitary_scheduler_status == "ok"
    assert all(getattr(api, d.key) == 12.5 for d in ENERGY_SENSOR_TYPES)


def test_null_plant_mode_in_bulk_is_automatico(api, cloud):
    fill_bulk(cloud)
    cloud.last_values["Modo Impianto"] = (None, now_ms())
    api.fetch_all_metrics()
    assert api.system_mode == "Automatico"


def test_no_data_sentinel_in_bulk(api, cloud):
    fill_bulk(cloud)
    cloud.last_values["Pressione impianto"] = ("---", now_ms())
    api.fetch_all_metrics()
    assert api.water_pressure is None


def test_holiday_end_from_bulk_ignored_when_off(api, cloud):
    fill_bulk(cloud)
    cloud.last_values["Modo vacanza"] = ("0000", now_ms())
    cloud.last_values["Data/Ora fine modo vacanza"] = ("1784797954954.0", now_ms())
    api.fetch_all_metrics()
    assert api.holiday_mode == "Off" and api.holiday_mode_end is None


def test_unexpected_schedule_value_does_not_raise(api, cloud):
    # JSON valido ma non un oggetto: errore gestito, il ciclo continua.
    fill_bulk(cloud)
    cloud.last_values[SANITARY_SCHEDULER_METRIC] = ("1", now_ms())
    api.fetch_all_metrics()
    assert api.sanitary_scheduler_status == "error"
    assert all(getattr(api, d.key) == 12.5 for d in ENERGY_SENSOR_TYPES)


def test_metric_missing_from_bulk_is_read_singly(api, cloud):
    # Es. Flame status su un impianto solo elettrico: lettura singola come oggi.
    fill_bulk(cloud)
    del cloud.last_values["Flame status"]
    cloud["Flame status"] = {"data": []}
    api.fetch_all_metrics()
    assert single_calls(cloud) == ["Flame status"]
    assert api.flame_status is None


def test_energy_missing_from_bulk_is_read_singly(api, cloud):
    fill_bulk(cloud)
    missing = ENERGY_SENSOR_TYPES[1]
    del cloud.last_values[missing.metric_name]
    cloud[missing.metric_name] = values_response("7.5", timestamp=now_ms())
    api.fetch_all_metrics()
    assert single_calls(cloud) == [missing.metric_name]
    assert getattr(api, missing.key) == 7.5


def test_daily_energy_reset_with_bulk_timestamp(api, cloud):
    fill_bulk(cloud)
    cloud.last_values[DAY.metric_name] = ("3.2", now_ms(days_ago=1))
    api.fetch_all_metrics()
    assert getattr(api, DAY.key) == 0.0


def test_bulk_failure_falls_back_to_single_reads(api, cloud):
    # cloud.last_values = None: la lettura multipla fallisce, tutto come prima.
    cloud["Temperatura esterna"] = values_response("21.5")
    api.fetch_all_metrics()
    assert set(single_calls(cloud)) == set(WIRED_METRIC_NAMES)
    assert api.temp_ext == 21.5


def test_cloud_down_keeps_previous_values(api, cloud):
    api.temp_ext = 20.0
    api.fetch_all_metrics()
    assert api.temp_ext == 20.0


def test_bulk_disabled_after_repeated_failures(api, cloud):
    cloud["Temperatura esterna"] = values_response("21.5")  # le singole riescono
    for _ in range(api.LAST_VALUES_MAX_FAILURES):
        api.fetch_all_metrics()
    cloud.calls.clear()
    api.fetch_all_metrics()
    assert not [c for c in cloud.calls if c[0] == "lastValues"]


def test_bulk_not_disabled_when_cloud_is_down(api, cloud):
    for _ in range(api.LAST_VALUES_MAX_FAILURES + 1):
        api.fetch_all_metrics()
    assert api._last_values_enabled


def test_request_split_over_fifty_metrics(api, cloud):
    names = [f"Metrica {i}" for i in range(60)]
    cloud.last_values = {n: ("1", now_ms()) for n in names}
    samples = api._fetch_last_values(names)
    assert [len(n) for _, n in cloud.calls] == [50, 10]
    assert len(samples) == 60
