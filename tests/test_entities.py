"""Comportamento delle entità con dati di runtime e coordinator simulati (senza HA avviato)."""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from homeassistant.exceptions import ServiceValidationError

from custom_components.baxi_hybridapp_home.coordinator import BaxiRuntimeData
from custom_components.baxi_hybridapp_home.datetime import BaxiHolidayModeEnd
from custom_components.baxi_hybridapp_home.sensor import ExternalTemperatureSensor, HolidayModeEndSensor
from custom_components.baxi_hybridapp_home.switch import BaxiHolidayModeSwitch


@pytest.fixture
def coordinator():
    return SimpleNamespace(last_update_success=True)


@pytest.fixture
def runtime(api, coordinator, monkeypatch):
    def no_write(*args):
        raise AssertionError("nessuna scrittura verso il cloud era attesa")

    monkeypatch.setattr(api, "set_configuration_parameter", no_write)
    return BaxiRuntimeData(api=api, coordinator=coordinator)


def entity(cls, *args):
    """Entità pronta all'uso fuori da HA: niente scrittura dello stato."""
    obj = cls(*args)
    obj.async_write_ha_state = lambda: None
    return obj


# --- Disponibilità --------------------------------------------------------------


def test_sensor_unavailable_when_cloud_unreachable(api, coordinator):
    api.temp_ext = 21.5
    sensor = ExternalTemperatureSensor(coordinator, api)
    assert sensor.available
    coordinator.last_update_success = False
    assert not sensor.available  # il valore c'è, ma è vecchio


def test_holiday_end_sensor_is_unknown_not_unavailable_when_off(api, coordinator):
    api.holiday_mode, api.holiday_mode_end = "Off", None
    sensor = HolidayModeEndSensor(coordinator, api)
    assert sensor.available
    assert sensor.native_value is None


# --- Modo vacanza: staging e switch ------------------------------------------------


def test_datetime_stages_without_sending_when_holiday_off(api, runtime):
    api.holiday_mode = "Off"
    end = datetime.now(timezone.utc) + timedelta(days=7)
    asyncio.run(entity(BaxiHolidayModeEnd, runtime).async_set_value(end))
    assert runtime.holiday_staged_end == end


def test_switch_rejects_activation_without_future_date(api, runtime):
    api.holiday_mode, api.holiday_mode_end = "Off", None
    switch = entity(BaxiHolidayModeSwitch, runtime)
    with pytest.raises(ServiceValidationError):
        asyncio.run(switch.async_turn_on())


def test_switch_rejects_past_staged_date(api, runtime):
    api.holiday_mode = "Off"
    runtime.holiday_staged_end = datetime.now(timezone.utc) - timedelta(hours=1)
    with pytest.raises(ServiceValidationError):
        asyncio.run(entity(BaxiHolidayModeSwitch, runtime).async_turn_on())


def test_switch_target_prefers_staged_date(api, runtime):
    staged = datetime.now(timezone.utc) + timedelta(days=3)
    api.holiday_mode_end = datetime.now(timezone.utc) + timedelta(days=1)
    runtime.holiday_staged_end = staged
    assert entity(BaxiHolidayModeSwitch, runtime)._target_end() == staged
