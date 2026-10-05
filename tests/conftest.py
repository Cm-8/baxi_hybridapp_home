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


class FakeCloud(dict):
    """Risposte di /data/values per metricName, più la lettura multipla /data/lastValues.

    - cloud[metricName] = values_response(...): risposta di /data/values; una
      metrica senza risposta restituisce None (= richiesta fallita).
    - cloud.last_values: None = /data/lastValues fallisce (default, come prima
      della lettura multipla); un dict {metricName: (value, ts)} = metriche
      presenti nella risposta multipla.
    - cloud.catalog: catalogo metriche del modello (lista di {"name": ...});
      None = la richiesta del catalogo fallisce (default).
    - cloud.calls: elenco delle richieste fatte, come ("values", nome),
      ("lastValues", [nomi]) o ("catalog", None).
    """

    def __init__(self):
        super().__init__()
        self.last_values = None
        self.catalog = None
        self.calls = []

    def get_json(self, url):
        parsed = urlparse(url)
        if parsed.path.endswith("/metrics"):
            self.calls.append(("catalog", None))
            return self.catalog
        names = parse_qs(parsed.query).get("metricName", [])
        if parsed.path.endswith("/data/lastValues"):
            self.calls.append(("lastValues", names))
            if self.last_values is None:
                return None
            return {"data": [
                {"metric": n, "ts": self.last_values[n][1], "value": self.last_values[n][0]}
                for n in names if n in self.last_values
            ]}
        name = names[0] if names else None
        self.calls.append(("values", name))
        return self.get(name)


@pytest.fixture
def cloud(api, monkeypatch):
    """Sostituisce lo strato HTTP con un cloud simulato (vedi FakeCloud).

    Viene sostituito _http_get_json e non _make_request, così il conteggio
    degli esiti delle richieste resta vero.
    """
    fake = FakeCloud()
    monkeypatch.setattr(api, "_http_get_json", fake.get_json)
    return fake
