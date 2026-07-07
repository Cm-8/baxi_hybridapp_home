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


class BaxiHybridAppHomeFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Gestione del flusso di configurazione per Baxi HybridApp Home."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Primo step di configurazione, richiede e valida le credenziali utente."""
        errors = {}

        if user_input is not None:
            # unique_id = email normalizzata → lo stesso account non può
            # essere configurato due volte (unique-config-entry, Bronze).
            await self.async_set_unique_id(user_input["username"].strip().lower())
            self._abort_if_unique_id_configured()

            # Test-before-configure (Bronze): valida il login PRIMA di creare
            # l'entry. login() è bloccante (requests) → executor, mai nell'event loop.
            api = BaxiHybridAppAPI(user_input["username"], user_input["password"])
            try:
                await self.hass.async_add_executor_job(api.login)
            except BaxiAuthError:
                errors["base"] = "invalid_auth"
            except BaxiConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("❌ Errore inatteso nella validazione credenziali")
                errors["base"] = "unknown"
            else:
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
            api = BaxiHybridAppAPI(username, user_input["password"])
            try:
                await self.hass.async_add_executor_job(api.login)
            except BaxiAuthError:
                errors["base"] = "invalid_auth"
            except BaxiConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("❌ Errore inatteso nella ri-autenticazione")
                errors["base"] = "unknown"
            else:
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
