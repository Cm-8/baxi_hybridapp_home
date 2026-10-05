"""Coordinator e servizi con un Home Assistant simulato: ri-autenticazione e Logbook."""

import asyncio
from datetime import timedelta
from types import SimpleNamespace

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import entity_registry as er

from custom_components.baxi_hybridapp_home import async_setup
from custom_components.baxi_hybridapp_home.coordinator import BaxiDataUpdateCoordinator, BaxiRuntimeData


class FakeHass:
    def __init__(self, entries=()):
        self.services = SimpleNamespace(
            async_register=self._register, async_call=self._call,
        )
        self.config_entries = SimpleNamespace(async_entries=lambda domain: list(entries))
        self.handlers, self.logbook = {}, []

    async def async_add_executor_job(self, func, *args):
        return func(*args)

    def _register(self, domain, service, handler, schema=None):
        self.handlers[service] = handler

    async def _call(self, domain, service, data, blocking=False):
        self.logbook.append(data)

    def async_create_task(self, coro):
        coro.close()


def bare_coordinator(api, hass):
    """Coordinator senza l'init di HA: basta per eseguire _async_update_data."""
    coordinator = BaxiDataUpdateCoordinator.__new__(BaxiDataUpdateCoordinator)
    coordinator.api, coordinator.hass = api, hass
    coordinator._capabilities_logged = True
    coordinator._update_interval = timedelta(minutes=5)
    return coordinator


def test_rejected_password_during_cycle_starts_reauth_at_once(api, monkeypatch):
    api.token, api.model_metrics = "expired", frozenset()

    def fetch_all_metrics():
        api.token, api.auth_rejected = None, True  # come authenticate() dopo un 401

    monkeypatch.setattr(api, "fetch_all_metrics", fetch_all_metrics)
    monkeypatch.setattr(api, "fetch_historical_alerts", lambda: None)
    with pytest.raises(ConfigEntryAuthFailed):
        asyncio.run(bare_coordinator(api, FakeHass())._async_update_data())


def test_sanitary_service_logs_on_the_real_entity(api, monkeypatch):
    monkeypatch.setattr(api, "set_configuration_parameter", lambda pid, value: True)
    registry = SimpleNamespace(
        async_get_entity_id=lambda platform, domain, uid:
            "water_heater.baxi_hybridapp_home_sanitario_comfort" if uid == "baxi_water_heater_comfort" else None,
    )
    monkeypatch.setattr(er, "async_get", lambda hass: registry)
    runtime = BaxiRuntimeData(api=api, coordinator=SimpleNamespace(async_update_listeners=lambda: None))
    entry = SimpleNamespace(state=ConfigEntryState.LOADED, runtime_data=runtime)
    hass = FakeHass([entry])

    asyncio.run(async_setup(hass, {}))
    asyncio.run(hass.handlers["set_comfort"](SimpleNamespace(service="set_comfort", data={"value": 45})))

    assert hass.logbook[0]["entity_id"] == "water_heater.baxi_hybridapp_home_sanitario_comfort"
    assert api.setpoint_comfort_temp == 45.0
