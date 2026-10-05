"""Autenticazione: rinnovo del JWT con il refreshToken, fallback al login, logout."""

import json

import pytest
import requests

URL = "https://baxi.servitly.com/api/data/values?thingId=thing-test&pageSize=1&metricName=Temperatura%20esterna"


class FakeResponse:
    def __init__(self, status, body=None):
        self.status_code = status
        self.ok = 200 <= status < 300
        self._body = body
        self.text = json.dumps(body) if body is not None else ""
        self.headers = {}

    def json(self):
        if self._body is None:
            raise ValueError("nessun JSON")
        return self._body


class FakeSession:
    """Restituisce le risposte in ordine e registra le chiamate (metodo, url, Bearer)."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def _next(self, method, url, headers):
        self.calls.append((method, url, (headers or {}).get("authorization")))
        nxt = self.responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    def request(self, method, url, headers=None, data=None, timeout=None):
        return self._next(method, url, headers)

    def post(self, url, headers=None, data=None, timeout=None):
        return self._next("POST", url, headers)


@pytest.fixture
def logged_in(api):
    api.token, api.refreshToken, api.userId, api.tenantId = "old", "r1", "user-1", "tenant-1"
    return api


def no_password_login():
    raise AssertionError("non doveva rifare il login con la password")


def test_expired_token_is_renewed_without_password(logged_in, monkeypatch):
    api = logged_in
    api._session = FakeSession(
        FakeResponse(401),
        FakeResponse(200, {"token": "new", "refreshToken": "r2"}),
        FakeResponse(200, {"data": []}),
    )
    monkeypatch.setattr(api, "login", no_password_login)

    assert api._make_request(URL) == {"data": []}
    assert (api.token, api.refreshToken) == ("new", "r2")
    method, url, bearer = api._session.calls[1]
    assert url == api.RENEW_URL and bearer == "Bearer old"  # rinnovo col token scaduto
    assert api._session.calls[2][2] == "Bearer new"  # nuovo tentativo col token nuovo


def test_rejected_renewal_falls_back_to_login(logged_in, monkeypatch):
    api = logged_in
    api._session = FakeSession(
        FakeResponse(401),
        FakeResponse(403),
        FakeResponse(200, {"data": []}),
    )

    def login():
        api.token = "fresh"

    monkeypatch.setattr(api, "login", login)
    assert api._make_request(URL) == {"data": []}
    assert api.token == "fresh"


def test_renewal_needs_identity_from_login(api):
    # Senza userId/tenantId (es. login di una versione precedente) non si tenta il rinnovo.
    api.token, api.refreshToken = "old", "r1"
    assert api.renew_token() is False


def test_login_stores_identity_for_renewal(api):
    api._session = FakeSession(
        FakeResponse(200, {"token": "t", "refreshToken": "r", "userId": "u", "tenantId": "x"}),
    )
    api.login()
    assert (api.token, api.refreshToken, api.userId, api.tenantId) == ("t", "r", "u", "x")


def test_login_log_hides_tokens_and_masks_user_id(api, caplog):
    api._session = FakeSession(FakeResponse(200, {
        "token": "secret-token", "refreshToken": "secret-refresh",
        "userId": "655e95a52b8045641cb5ca9d", "tenantId": "x",
    }))
    with caplog.at_level("INFO"):
        api.login()
    logged = caplog.text
    assert "secret-token" not in logged and "secret-refresh" not in logged
    assert "655e95a52b8045641cb5ca9d" not in logged and "***ca9d" in logged


def test_write_renews_expired_token(logged_in, monkeypatch):
    api = logged_in
    api._session = FakeSession(
        FakeResponse(401),
        FakeResponse(200, {"token": "new"}),
        FakeResponse(204),
    )
    monkeypatch.setattr(api, "login", no_password_login)
    assert api.set_configuration_parameter("param", 45) is True
    assert api.refreshToken == "r1"  # refreshToken non ruotato: si tiene il vecchio


def test_network_error_returns_none_without_raising(logged_in):
    api = logged_in
    api._session = FakeSession(requests.ConnectionError("rete giù"))
    assert api._make_request(URL) is None


def test_logout_clears_tokens_even_if_cloud_unreachable(logged_in):
    api = logged_in
    api._session = FakeSession(requests.ConnectionError("rete giù"))
    api.logout()
    assert api.token is None and api.refreshToken is None
