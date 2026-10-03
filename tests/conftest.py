"""Fixture condivise: client API con un cloud Servitly simulato (nessuna rete)."""

from urllib.parse import parse_qs, urlparse

import pytest

from custom_components.baxi_hybridapp_home.api import BaxiHybridAppAPI


def values_response(value, timestamp=1_700_000_000_000):
    """Risposta di /data/values con un solo campione, nel formato Servitly."""
    return {
        "data": [
            {
                "timestamp": timestamp,
                "values": [{"name": "X", "value": value, "path": "measures", "filled": False}],
            }
        ]
    }


@pytest.fixture
def api():
    """Client già 'collegato' a un impianto: thingId valorizzato, nessun login."""
    client = BaxiHybridAppAPI("user@example.com", "secret")
    client.thingId = "thing-test"
    return client


@pytest.fixture
def cloud(api, monkeypatch):
    """Sostituisce lo strato HTTP con risposte preparate, indicizzate per metricName.

    Una metrica senza risposta impostata restituisce None: lo stesso esito di
    una richiesta fallita (rete, timeout, errore server). Viene sostituito
    _http_get_json e non _make_request, così il conteggio degli esiti resta vero.
    """
    responses = {}

    def fake_http_get_json(url):
        name = parse_qs(urlparse(url).query).get("metricName", [None])[0]
        return responses.get(name)

    monkeypatch.setattr(api, "_http_get_json", fake_http_get_json)
    return responses
