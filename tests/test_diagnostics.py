"""Diagnostica: valori di tutte le metriche del catalogo, con i dati personali oscurati."""

import asyncio
import json
from types import SimpleNamespace

from custom_components.baxi_hybridapp_home.diagnostics import async_get_config_entry_diagnostics

CATALOG = ["Temperatura esterna", "WiFi ssid", "Nome zona 1", "Pompa di calore giornaliero", "Solare on"]


class FakeHass:
    async def async_add_executor_job(self, func, *args):
        return func(*args)


def diagnostics(api):
    entry = SimpleNamespace(
        data={"username": "user@example.com", "password": "secret"}, options={},
        runtime_data=SimpleNamespace(api=api),
    )
    return asyncio.run(async_get_config_entry_diagnostics(FakeHass(), entry))


def test_last_value_of_every_catalog_metric(api, cloud):
    api.thingDefinitionId = "def-1"
    cloud.catalog = [{"name": n} for n in CATALOG]
    cloud.last_values = {
        "Temperatura esterna": ("17.0", 1),
        "WiFi ssid": ("CasaRossi", 2),
        "Nome zona 1": ("Camera di Marco", 3),
        "Pompa di calore giornaliero": ("3600000", 4),
    }
    result = diagnostics(api)
    catalog = result["catalog_values"]
    assert catalog["values"]["Pompa di calore giornaliero"] == {"value": "3600000", "timestamp": 4}
    assert catalog["values"]["WiFi ssid"] == "**REDACTED**"
    assert catalog["values"]["Nome zona 1"] == "**REDACTED**"
    assert catalog["without_data"] == ["Solare on"]
    dump = json.dumps(result, default=str)
    assert "CasaRossi" not in dump and "Camera di Marco" not in dump and "thing-test" not in dump


def test_catalog_values_never_break_the_download(api, cloud):
    # Catalogo non leggibile (cloud.catalog = None): la diagnostica si scarica comunque.
    api.thingDefinitionId = "def-1"
    assert diagnostics(api)["catalog_values"] == {"values": "catalogo non disponibile"}
