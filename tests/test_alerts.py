"""Alert aperti e risolti: binary_sensor Failure/Warning, conteggi, eventi."""

from homeassistant.util import dt as dt_util

MINUTE_MS = 60_000


def now_ms():
    return int(dt_util.utcnow().timestamp() * 1000)


def alert(alert_id, severity="WARNING", start=None, end=None, thing="thing-test"):
    """Alert nel formato Servitly (descrizione dell'avviso di prodotto offline)."""
    return {
        "id": alert_id,
        "title": "BAXI AVVISA",
        "description": "Il tuo prodotto CSI IN SPLIT E è OFFLINE da almeno un ora.",
        "startTimestamp": start if start is not None else now_ms() - 10 * MINUTE_MS,
        "endTimestamp": end,
        "severity": severity,
        "thing": {"id": thing},
    }


def history(*alerts):
    return {"historicalAlerts": list(alerts)}


def closed(a):
    return {**a, "endTimestamp": now_ms() - MINUTE_MS}


def test_open_alert_turns_warning_on(api, cloud):
    # Lo storico contiene solo alert risolti: quello aperto è nell'altro elenco.
    cloud.active_alerts = [alert("a1")]
    cloud.historical_alerts = history()
    api.fetch_alerts()
    assert api.active_warning_alert["id"] == "a1"
    assert api.active_warning_alert["code"] == "OFFLINE"
    assert api.active_failure_alert is None
    assert api.warning_count_24h == 1


def test_closed_alerts_are_not_active(api, cloud):
    cloud.active_alerts = []
    cloud.historical_alerts = history(closed(alert("a1")))
    api.fetch_alerts()
    assert api.active_warning_alert is None
    assert api.last_warning_alert["id"] == "a1"


def test_new_alert_fires_once_when_it_opens(api, cloud):
    cloud.active_alerts = []
    cloud.historical_alerts = history()
    api.fetch_alerts()  # seed
    a1 = alert("a1")
    cloud.active_alerts = [a1]
    api.fetch_alerts()
    assert [a["id"] for a in api.new_alerts_pending] == ["a1"]
    # Alla chiusura passa nello storico con lo stesso id: nessun nuovo evento.
    cloud.active_alerts = []
    cloud.historical_alerts = history(closed(a1))
    api.fetch_alerts()
    assert api.new_alerts_pending == []
    assert api.active_warning_alert is None


def test_alert_opened_and_closed_between_reads_fires_from_history(api, cloud):
    cloud.active_alerts = []
    cloud.historical_alerts = history()
    api.fetch_alerts()  # seed
    cloud.historical_alerts = history(closed(alert("a2")))
    api.fetch_alerts()
    assert [a["id"] for a in api.new_alerts_pending] == ["a2"]


def test_alerts_already_there_at_startup_do_not_fire(api, cloud):
    cloud.active_alerts = [alert("a1")]
    cloud.historical_alerts = history(closed(alert("old")))
    api.fetch_alerts()
    assert api.new_alerts_pending == []
    api.fetch_alerts()
    assert api.new_alerts_pending == []


def test_critical_severity_counts_as_failure(api, cloud):
    cloud.active_alerts = [alert("c1", severity="CRITICAL")]
    cloud.historical_alerts = history()
    api.fetch_alerts()
    assert api.active_failure_alert["severity"] == "FAILURE"
    assert api.active_warning_alert is None
    assert api.failure_count_24h == 1


def test_failed_active_request_keeps_previous_state(api, cloud):
    cloud.active_alerts = [alert("a1")]
    cloud.historical_alerts = history()
    api.fetch_alerts()
    cloud.active_alerts = None  # richiesta fallita
    api.fetch_alerts()
    assert api.active_warning_alert["id"] == "a1"


def test_failed_history_request_keeps_counts(api, cloud):
    cloud.active_alerts = []
    cloud.historical_alerts = history(closed(alert("a1")))
    api.fetch_alerts()
    cloud.historical_alerts = None
    api.fetch_alerts()
    assert api.warning_count_24h == 1
    assert api.last_warning_alert["id"] == "a1"


def test_paginated_response_and_other_things(api, cloud):
    cloud.active_alerts = {"content": [alert("x", thing="other"), alert("a1")]}
    cloud.historical_alerts = history()
    api.fetch_alerts()
    assert api.active_warning_alert["id"] == "a1"
    assert api.warning_count_24h == 1


def test_both_requests_failed_change_nothing(api, cloud):
    cloud.active_alerts = [alert("a1")]
    cloud.historical_alerts = history()
    api.fetch_alerts()
    cloud.active_alerts = cloud.historical_alerts = None
    api.fetch_alerts()
    assert api.active_warning_alert["id"] == "a1"
    assert api.request_stats()[1]  # le due richieste fallite sono contate
