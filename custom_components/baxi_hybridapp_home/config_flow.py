"""
Config flow for Baxi Hybrid App custom integration for Home Assistant.

custom_components/baxi_hybridapp_home/config_flow.py
"""

import logging

from homeassistant import config_entries
import voluptuous as vol

from .api import BaxiAuthError, BaxiConnectionError, BaxiHybridAppAPI
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    vol.Required("username"): str,
    vol.Required("password"): str,
})


def _unique_id(username: str) -> str:
    """unique_id della config entry: l'email normalizzata."""
    return username.strip().lower()


class BaxiHybridAppHomeFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Gestione del flusso di configurazione per Baxi HybridApp Home."""

    VERSION = 1

    async def _async_validate_login(self, username: str, password: str) -> dict[str, str]:
        """Prova il login sul cloud (test-before-configure): errori per il form, {} se riesce.

        login() è bloccante (requests) → executor, mai nell'event loop. È una
        login di sola validazione: se riesce, la sessione cloud viene chiusa subito.
        """
        api = BaxiHybridAppAPI(username, password)
        try:
            await self.hass.async_add_executor_job(api.login)
        except BaxiAuthError:
            return {"base": "invalid_auth"}
        except BaxiConnectionError:
            return {"base": "cannot_connect"}
        except Exception:
            _LOGGER.exception("❌ Errore inatteso nella validazione credenziali")
            return {"base": "unknown"}
        await self.hass.async_add_executor_job(api.close)
        return {}

    async def async_step_user(self, user_input=None):
        """Primo step di configurazione, richiede e valida le credenziali utente."""
        errors = {}

        if user_input is not None:
            # unique_id = email normalizzata → lo stesso account non può
            # essere configurato due volte (unique-config-entry, Bronze).
            await self.async_set_unique_id(_unique_id(user_input["username"]))
            self._abort_if_unique_id_configured()

            errors = await self._async_validate_login(user_input["username"], user_input["password"])
            if not errors:
                return self.async_create_entry(
                    title="Baxi HybridApp Home",
                    data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=CONFIG_SCHEMA,
            errors=errors
        )

    async def async_step_reauth(self, entry_data):
        """Avviato da HA quando il coordinator solleva ConfigEntryAuthFailed."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Chiede la nuova password (l'email resta quella dell'entry esistente)."""
        errors = {}
        reauth_entry = self._get_reauth_entry()
        username = reauth_entry.data["username"]

        if user_input is not None:
            errors = await self._async_validate_login(username, user_input["password"])
            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={"password": user_input["password"]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required("password"): str}),
            description_placeholders={"username": username},
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input=None):
        """Aggiorna le credenziali senza rimuovere l'integrazione (reconfiguration-flow, Gold).

        L'account deve restare lo stesso: un'email diversa è un altro impianto,
        che si aggiunge come nuova integrazione.
        """
        errors = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            await self.async_set_unique_id(_unique_id(user_input["username"]))
            self._abort_if_unique_id_mismatch(reason="wrong_account")

            errors = await self._async_validate_login(user_input["username"], user_input["password"])
            if not errors:
                return self.async_update_reload_and_abort(entry, data_updates=user_input)

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                CONFIG_SCHEMA, {"username": entry.data["username"]}
            ),
            errors=errors,
        )
