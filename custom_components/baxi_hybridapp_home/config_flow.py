from homeassistant import config_entries
import voluptuous as vol
from .const import DOMAIN

CONFIG_SCHEMA = vol.Schema({
    vol.Required("username"): str,
    vol.Required("password"): str,
})

class BaxiHybridAppHomeFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Gestione del flusso di configurazione per Baxi HybridApp Home."""

    async def async_step_user(self, user_input=None):
        """Primo step di configurazione, richiede credenziali utente."""
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="Baxi HybridApp Home",
                data=user_input
            )

        return self.async_show_form(
            step_id="user",
            data_schema=CONFIG_SCHEMA
        )