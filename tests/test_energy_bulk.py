"""Sensori energia letti con una sola richiesta GET /data/lastValues."""

from datetime import timedelta

from homeassistant.util import dt as dt_util

from custom_components.baxi_hybridapp_home.metrics import ENERGY_SENSOR_TYPES

from .conftest import values_response

NAMES = [d.metric_name for d in ENERGY_SENSOR_TYPES]
DAY = next(d for d in ENERGY_SENSOR_TYPES if d.key == "energia_totale_globale_day")


def now_ms(days_ago=0):
    return int((dt_util.now() - timedelta(days=days_ago)).timestamp() * 1000)


def single_calls(cloud):
    return [name for kind, name in cloud.calls if kind == "values"]


def test_all_energy_metrics_in_one_request(api, cloud):
    cloud.last_values = {n: ("12,5", now_ms()) for n in NAMES}
    api.fetch_energy_metrics()
    assert cloud.calls == [("lastValues", NAMES)]
    assert all(getattr(api, d.key) == 12.5 for d in ENERGY_SENSOR_TYPES)
    assert api.request_stats() == (1, [])


def test_daily_energy_reset_works_with_bulk_timestamp(api, cloud):
    cloud.last_values = {n: ("3.2", now_ms()) for n in NAMES}
    cloud.last_values[DAY.metric_name] = ("3.2", now_ms(days_ago=1))
    api.fetch_energy_metrics()
    assert getattr(api, DAY.key) == 0.0


def test_metric_missing_from_bulk_is_read_singly(api, cloud):
    # Come oggi per le metriche non restituite: lettura singola, solo per loro.
    missing = NAMES[1]
    cloud.last_values = {n: ("1.0", now_ms()) for n in NAMES if n != missing}
    cloud[missing] = values_response("7.5", timestamp=now_ms())
    api.fetch_energy_metrics()
    assert single_calls(cloud) == [missing]
    assert getattr(api, ENERGY_SENSOR_TYPES[1].key) == 7.5


def test_bulk_failure_falls_back_to_single_reads(api, cloud):
    # cloud.last_values = None: la lettura multipla fallisce.
    for n in NAMES:
        cloud[n] = values_response("2.0", timestamp=now_ms())
    api.fetch_energy_metrics()
    assert single_calls(cloud) == NAMES
    assert all(getattr(api, d.key) == 2.0 for d in ENERGY_SENSOR_TYPES)


def test_bulk_disabled_after_repeated_failures(api, cloud):
    for n in NAMES:
        cloud[n] = values_response("2.0", timestamp=now_ms())
    for _ in range(api.LAST_VALUES_MAX_FAILURES):
        api.fetch_energy_metrics()
    cloud.calls.clear()
    api.fetch_energy_metrics()
    assert not [c for c in cloud.calls if c[0] == "lastValues"]


def test_bulk_not_disabled_when_cloud_is_down(api, cloud):
    # Fallisce tutto (cloud giù): non è colpa dell'endpoint, non va disattivato.
    for _ in range(api.LAST_VALUES_MAX_FAILURES + 1):
        api.fetch_energy_metrics()
    assert api._last_values_enabled


def test_request_split_over_fifty_metrics(api, cloud):
    names = [f"Metrica {i}" for i in range(60)]
    cloud.last_values = {n: ("1", now_ms()) for n in names}
    samples = api._fetch_last_values(names)
    assert [len(n) for _, n in cloud.calls] == [50, 10]
    assert len(samples) == 60
