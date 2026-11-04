"""Temperature dei water heater: nomi "native_*" di HA 2026.11 e compatibilità con le versioni precedenti."""

from types import SimpleNamespace

import pytest
from homeassistant.components.water_heater import WaterHeaterEntity
from homeassistant.const import UnitOfTemperature
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM

from custom_components.baxi_hybridapp_home.water_heater import BaxiSanitaryComfort, BaxiSanitaryEco


def attributes(cls, api, units=METRIC_SYSTEM):
    """Attributi dello stato di un'entità, per i nomi come li scrive Home Assistant."""
    entity = cls(SimpleNamespace(last_update_success=True), api)
    entity.hass = SimpleNamespace(config=SimpleNamespace(units=units))
    merged = {**entity.capability_attributes, **entity.state_attributes}
    return {getattr(key, "value", key): value for key, value in merged.items()}


@pytest.fixture
def temperatures(api):
    api.dhw_storage_temp = 47.0
    api.setpoint_comfort_temp = 50.0
    api.setpoint_eco_temp = 40.0
    return api


@pytest.mark.parametrize(
    ("cls", "target"),
    [(BaxiSanitaryComfort, 50.0), (BaxiSanitaryEco, 40.0)],
)
def test_state_reports_storage_and_setpoint(temperatures, cls, target):
    attrs = attributes(cls, temperatures)
    assert attrs["current_temperature"] == 47.0
    assert attrs["temperature"] == target
    assert attrs["min_temp"] == 30
    assert attrs["max_temp"] == 52


def test_temperatures_are_converted_to_the_user_unit(temperatures):
    # La temperatura nativa resta in °C: la converte Home Assistant.
    attrs = attributes(BaxiSanitaryComfort, temperatures, US_CUSTOMARY_SYSTEM)
    assert attrs["current_temperature"] == 117
    assert attrs["temperature"] == 122


@pytest.mark.parametrize("cls", [BaxiSanitaryComfort, BaxiSanitaryEco])
def test_native_names_are_the_source(temperatures, cls):
    entity = cls(SimpleNamespace(last_update_success=True), temperatures)
    assert entity.native_current_temperature == 47.0
    assert entity._attr_native_temperature_unit == UnitOfTemperature.CELSIUS


@pytest.mark.parametrize("cls", [BaxiSanitaryComfort, BaxiSanitaryEco])
@pytest.mark.parametrize(
    "old_name", ["current_temperature", "target_temperature", "_attr_temperature_unit"],
)
def test_old_names_only_without_the_native_api(cls, old_name):
    # Da HA 2026.11 fornire i nomi vecchi scrive un avviso nel log.
    has_native_api = hasattr(WaterHeaterEntity, "native_current_temperature")
    assert (old_name in vars(cls)) is not has_native_api
