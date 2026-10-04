"""Config flow: configurazione, ri-autenticazione e riconfigurazione.

Il flusso usa la classe ConfigFlow vera di Home Assistant; sono simulati solo
il gestore delle config entry (FakeConfigEntries) e il client del cloud.
"""

import asyncio
from datetime import timedelta
from types import SimpleNamespace

import pytest
from homeassistant.data_entry_flow import AbortFlow, FlowResultType

from custom_components.baxi_hybridapp_home import _async_options_updated, config_flow
from custom_components.baxi_hybridapp_home.api import BaxiAuthError, BaxiConnectionError
from custom_components.baxi_hybridapp_home.const import DOMAIN
from custom_components.baxi_hybridapp_home.coordinator import polling_interval

USER = {"username": "User@Example.com ", "password": "secret"}


class FakeConfigEntries:
    def __init__(self, entries=()):
        self.entries = list(entries)
        self.reloaded = []
        self.flow = SimpleNamespace(
            async_progress_by_handler=lambda *a, **k: [],
            async_abort=lambda flow_id: None,
        )

    def async_entry_for_domain_unique_id(self, domain, unique_id):
        return next((e for e in self.entries if e.unique_id == unique_id), None)

    def async_get_known_entry(self, entry_id):
        return next(e for e in self.entries if e.entry_id == entry_id)

    def async_update_entry(self, entry, *, data=None, **_):
        if data is not None:
            entry.data = dict(data)
        return True

    def async_schedule_reload(self, entry_id):
        self.reloaded.append(entry_id)


class FakeHass:
    def __init__(self, entries=()):
        self.config_entries = FakeConfigEntries(entries)
        # Usato da HA a fine ri-autenticazione per chiudere la notifica relativa.
        self.data = {}

    async def async_add_executor_job(self, func, *args):
        return func(*args)


class FakeApi:
    """Client simulato: login riuscito, oppure l'eccezione indicata in `error`."""

    error = None
    instances = []

    def __init__(self, username, password):
        self.credentials = (username, password)
        self.closed = False
        FakeApi.instances.append(self)

    def login(self):
        if FakeApi.error:
            raise FakeApi.error

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def fake_api(monkeypatch):
    FakeApi.error, FakeApi.instances = None, []
    monkeypatch.setattr(config_flow, "BaxiHybridAppAPI", FakeApi)
    return FakeApi


def existing_entry(options=None):
    return SimpleNamespace(
        entry_id="entry-1", unique_id="user@example.com", title="Baxi HybridApp Home",
        data={"username": "user@example.com", "password": "old"}, source="user",
        options=options or {},
    )


def flow(hass, source, entry_id=None):
    handler = config_flow.BaxiHybridAppHomeFlowHandler()
    handler.hass, handler.handler, handler.flow_id = hass, DOMAIN, "flow-1"
    handler.context = {"source": source, **({"entry_id": entry_id} if entry_id else {})}
    return handler


def run(coro):
    return asyncio.run(coro)


# --- Prima configurazione -----------------------------------------------------------


def test_user_step_shows_form():
    result = run(flow(FakeHass(), "user").async_step_user())
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "user"


def test_user_step_creates_entry_and_closes_session(fake_api):
    handler = flow(FakeHass(), "user")
    result = run(handler.async_step_user(USER))
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == USER
    assert handler.unique_id == "user@example.com"  # email normalizzata
    assert fake_api.instances[0].closed  # login di sola validazione


@pytest.mark.parametrize(
    ("error", "code"),
    [(BaxiAuthError("no"), "invalid_auth"), (BaxiConnectionError("no"), "cannot_connect"),
     (RuntimeError("boom"), "unknown")],
)
def test_user_step_errors(fake_api, error, code):
    fake_api.error = error
    result = run(flow(FakeHass(), "user").async_step_user(USER))
    assert result["type"] is FlowResultType.FORM and result["errors"] == {"base": code}
    assert not fake_api.instances[0].closed


def test_same_account_cannot_be_added_twice():
    with pytest.raises(AbortFlow) as err:
        run(flow(FakeHass([existing_entry()]), "user").async_step_user(USER))
    assert err.value.reason == "already_configured"


# --- Ri-autenticazione --------------------------------------------------------------


def test_reauth_updates_password_and_reloads():
    entry = existing_entry()
    hass = FakeHass([entry])
    result = run(flow(hass, "reauth", "entry-1").async_step_reauth_confirm({"password": "new"}))
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "reauth_successful"
    assert entry.data == {"username": "user@example.com", "password": "new"}
    assert hass.config_entries.reloaded == ["entry-1"]


def test_reauth_wrong_password_shows_error(fake_api):
    fake_api.error = BaxiAuthError("no")
    result = run(flow(FakeHass([existing_entry()]), "reauth", "entry-1")
                 .async_step_reauth_confirm({"password": "bad"}))
    assert result["errors"] == {"base": "invalid_auth"}


# --- Riconfigurazione ---------------------------------------------------------------


def test_reconfigure_form_prefills_email():
    result = run(flow(FakeHass([existing_entry()]), "reconfigure", "entry-1").async_step_reconfigure())
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "reconfigure"
    keys = {str(k): k for k in result["data_schema"].schema}
    assert keys["username"].description == {"suggested_value": "user@example.com"}


def test_reconfigure_same_account_updates_credentials():
    entry = existing_entry()
    hass = FakeHass([entry])
    new = {"username": "user@example.com", "password": "new"}
    result = run(flow(hass, "reconfigure", "entry-1").async_step_reconfigure(new))
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "reconfigure_successful"
    assert entry.data == new
    assert hass.config_entries.reloaded == ["entry-1"]


def test_reconfigure_other_account_is_rejected(fake_api):
    entry = existing_entry()
    other = {"username": "someone.else@example.com", "password": "x"}
    with pytest.raises(AbortFlow) as err:
        run(flow(FakeHass([entry]), "reconfigure", "entry-1").async_step_reconfigure(other))
    assert err.value.reason == "wrong_account"
    assert entry.data["password"] == "old" and not fake_api.instances  # nessun login tentato


def test_reconfigure_wrong_password_keeps_entry(fake_api):
    fake_api.error = BaxiAuthError("no")
    entry = existing_entry()
    result = run(flow(FakeHass([entry]), "reconfigure", "entry-1")
                 .async_step_reconfigure({"username": "user@example.com", "password": "bad"}))
    assert result["errors"] == {"base": "invalid_auth"}
    assert entry.data["password"] == "old"


# --- Opzioni (pulsante Configura) ---------------------------------------------------


def options_flow(entry):
    handler = config_flow.BaxiHybridAppHomeFlowHandler.async_get_options_flow(entry)
    handler.hass, handler.handler, handler.flow_id = FakeHass([entry]), entry.entry_id, "flow-2"
    handler.context = {}
    return handler


def interval_field(result):
    return next(k for k in result["data_schema"].schema if str(k) == "polling_interval")


def test_options_form_defaults_to_five_minutes():
    result = run(options_flow(existing_entry()).async_step_init())
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "init"
    field = interval_field(result)
    assert field.default() == "5"
    assert result["data_schema"].schema[field].config["options"] == ["2", "5", "10"]


def test_options_form_shows_current_interval():
    result = run(options_flow(existing_entry({"polling_interval": 2})).async_step_init())
    assert interval_field(result).default() == "2"


def test_options_store_minutes_as_number():
    result = run(options_flow(existing_entry()).async_step_init({"polling_interval": "10"}))
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"polling_interval": 10}


def test_polling_interval_from_options():
    assert polling_interval(existing_entry()) == timedelta(minutes=5)
    assert polling_interval(existing_entry({"polling_interval": 10})) == timedelta(minutes=10)


def entry_with_coordinator(options, current_minutes):
    refreshes = []

    async def refresh():
        refreshes.append(True)

    coordinator = SimpleNamespace(update_interval=timedelta(minutes=current_minutes),
                                  async_request_refresh=refresh)
    entry = existing_entry(options)
    entry.runtime_data = SimpleNamespace(coordinator=coordinator)
    return entry, coordinator, refreshes


def test_new_interval_applied_right_away():
    entry, coordinator, refreshes = entry_with_coordinator({"polling_interval": 2}, 5)
    run(_async_options_updated(None, entry))
    assert coordinator.update_interval == timedelta(minutes=2)
    assert refreshes == [True]  # il ciclo immediato riprogramma il timer


def test_entry_update_without_new_interval_changes_nothing():
    # Es. ri-autenticazione: la entry cambia ma l'intervallo no.
    entry, coordinator, refreshes = entry_with_coordinator({}, 5)
    run(_async_options_updated(None, entry))
    assert coordinator.update_interval == timedelta(minutes=5) and not refreshes
