"""Test del client API: dispatcher metriche, energia, scheduler sanitario, log."""

import json
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from homeassistant.util import dt as dt_util

from custom_components.baxi_hybridapp_home.api import _mask_serial
from custom_components.baxi_hybridapp_home.metrics import ENERGY_SENSOR_TYPES

from .conftest import values_response

API_LOGGER = "custom_components.baxi_hybridapp_home.api"
ROME = ZoneInfo("Europe/Rome")


# --- Metriche semplici (fetch_simple_metrics / _fetch_one) -----------------------


def test_valid_value_is_parsed_with_timestamp(api, cloud):
    cloud["Temperatura esterna"] = values_response("21.5", timestamp=123)
    api.fetch_simple_metrics()
    assert api.temp_ext == 21.5
    assert api.temp_ext_timestamp == 123


def test_empty_data_means_metric_not_available(api, cloud, caplog):
    # Issue #6: device privo della metrica → None, senza warning.
    cloud["Flame status"] = {"data": []}
    with caplog.at_level(logging.WARNING, logger=API_LOGGER):
        api.fetch_simple_metrics()
    assert api.flame_status is None
    assert not [r for r in caplog.records if "Flame status" in r.getMessage()]


@pytest.mark.parametrize("sentinel", ["---", ""])
def test_no_data_sentinels(api, cloud, sentinel):
    cloud["Pressione impianto"] = values_response(sentinel)
    api.fetch_simple_metrics()
    assert api.water_pressure is None


def test_parse_failure_resets_value_and_warns(api, cloud, caplog):
    api.temp_ext = 20.0
    cloud["Temperatura esterna"] = values_response("abc")
    with caplog.at_level(logging.WARNING, logger=API_LOGGER):
        api.fetch_simple_metrics()
    assert api.temp_ext is None
    assert any("Temperatura esterna" in r.getMessage() for r in caplog.records)


def test_failed_request_keeps_previous_value(api, cloud):
    # Nessuna risposta = richiesta fallita: l'ultimo valore resta valido.
    # Da preservare anche quando arriverà il fetch bulk (PR #14).
    api.temp_ext = 20.0
    api.fetch_simple_metrics()
    assert api.temp_ext == 20.0


def test_null_plant_mode_is_automatico(api, cloud):
    cloud["Modo Impianto"] = values_response(None)
    api.fetch_simple_metrics()
    assert api.system_mode == "Automatico"


def test_holiday_end_float_epoch(api, cloud):
    cloud["Data/Ora fine modo vacanza"] = values_response(1784797954954.0)
    api.fetch_simple_metrics()
    assert api.holiday_mode_end == datetime(2026, 7, 23, 9, 12, 34, 954000, tzinfo=timezone.utc)


# --- Energia (fetch_energy_metrics) ------------------------------------------------

DAY_KEY = "energia_totale_globale_day"


def energy_desc(key):
    return next(desc for desc in ENERGY_SENSOR_TYPES if desc.key == key)


def epoch_ms(dt):
    return int(dt.timestamp() * 1000)


def test_energy_accepts_comma_decimal(api, cloud):
    desc = next(d for d in ENERGY_SENSOR_TYPES if d.key != DAY_KEY)
    cloud[desc.metric_name] = values_response("12,5")
    api.fetch_energy_metrics()
    assert getattr(api, desc.key) == 12.5


def test_daily_energy_from_today_is_kept(api, cloud):
    cloud[energy_desc(DAY_KEY).metric_name] = values_response("3.2", timestamp=epoch_ms(dt_util.now()))
    api.fetch_energy_metrics()
    assert getattr(api, DAY_KEY) == 3.2


def test_daily_energy_from_yesterday_is_zero(api, cloud):
    # Finché il device non pubblica il campione del nuovo giorno, il valore
    # di ieri non deve comparire come consumo di oggi.
    yesterday = dt_util.now() - timedelta(days=1)
    cloud[energy_desc(DAY_KEY).metric_name] = values_response("3.2", timestamp=epoch_ms(yesterday))
    api.fetch_energy_metrics()
    assert getattr(api, DAY_KEY) == 0.0


# --- Scheduler sanitario (_compute_sanitary_schedule_state) --------------------------

DAYS = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]


def schedule(comfort_windows):
    """Programma settimanale: stesse fasce Comfort ogni giorno, Eco a 39 °C."""
    day = [{"start": None, "end": None, "params": {"Set-point sanitario eco": "39.0"}}]
    day += [{"start": s, "end": e, "params": {}} for s, e in comfort_windows]
    return json.dumps({d: day for d in DAYS})


def monday_at(hour, minute=0):
    now = datetime(2026, 10, 5, hour, minute, tzinfo=ROME)
    assert now.weekday() == 0  # lunedì → chiave "Lun"
    return now


def test_inside_comfort_window(api):
    api._compute_sanitary_schedule_state(schedule([("08:00", "22:30")]), monday_at(10))
    assert api.sanitary_mode_now == "Comfort"
    assert api.sanitary_next_change == monday_at(22, 30)
    assert api.sanitary_today_summary == "Comfort fino alle 22:30"
    assert api.sanitary_eco_setpoint == "39.0"


def test_eco_before_comfort_window(api):
    api._compute_sanitary_schedule_state(schedule([("08:00", "22:30")]), monday_at(7))
    assert api.sanitary_mode_now == "Eco"
    assert api.sanitary_today_summary == "Eco fino alle 08:00"


def test_now_is_converted_to_rome_time(api):
    # 06:30 UTC = 08:30 a Roma (ora legale): già dentro la fascia Comfort.
    now_utc = datetime(2026, 10, 5, 6, 30, tzinfo=timezone.utc)
    api._compute_sanitary_schedule_state(schedule([("08:00", "22:30")]), now_utc)
    assert api.sanitary_mode_now == "Comfort"


def test_unordered_comfort_windows(api):
    api._compute_sanitary_schedule_state(schedule([("14:00", "16:00"), ("06:00", "07:00")]), monday_at(10))
    assert api.sanitary_mode_now == "Eco"
    assert api.sanitary_today_summary == "Eco fino alle 14:00"


# --- Log ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("serial", "expected"),
    [(None, "n.d."), ("", "n.d."), ("1234", "***"), ("ABC123456789", "***6789"), (12345678, "***5678")],
)
def test_mask_serial(serial, expected):
    assert _mask_serial(serial) == expected
