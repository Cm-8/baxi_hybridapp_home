"""
Switch platform for Baxi Hybrid App custom integration for Home Assistant.

Entità "Modo Vacanza": interruttore on/off che rispecchia il flag dell'app.
- ON  → invia la data di fine in staging (o quella corrente dal cloud, se
        futura) tramite PUT del parametro; attiva la vacanza.
- OFF → invia un valore nullo (data nel passato) e disattiva la vacanza.

La data si imposta nell'entità datetime "Modo Vacanza Fine" (staging), poi la
si applica con questo switch: così una modifica alla data non viene mai
inviata per errore al solo salvataggio.

custom_components/baxi_hybridapp_home/switch.py
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN, DATA_KEY_API,
    PARAM_ID_HOLIDAY_MODE_END,
    HOLIDAY_MODE_DISABLE_VALUE,
    HOLIDAY_STAGED_KEY,
    WRITE_GRACE_SECONDS,
)
from .device import build_device_info

_LOGGER = logging.getLogger(__name__)


class BaxiHolidayModeSwitch(CoordinatorEntity, SwitchEntity):
    """Interruttore Modo Vacanza (attiva/disattiva la programmazione vacanza)."""

    _attr_name = "Modo Vacanza"
    _attr_unique_id = "baxi_holiday_mode_switch"
    _attr_icon = "mdi:palm-tree"

    def __init__(self, coordinator, api) -> None:
        super().__init__(coordinator)
        self._api = api

    @property
    def is_on(self) -> bool:
        """Attivo quando la metrica 'Modo vacanza' (holiday_mode) è On."""
        return (getattr(self._api, "holiday_mode", None) or "").lower() == "on"

    @property
    def available(self) -> bool:
        return super().available and getattr(self._api, "holiday_mode", None) is not None

    def _target_end(self) -> datetime | None:
        """Data da inviare: staging se presente, altrimenti quella dal cloud."""
        staged = self.hass.data[DOMAIN].get(HOLIDAY_STAGED_KEY)
        if isinstance(staged, datetime):
            return staged
        server = getattr(self._api, "holiday_mode_end", None)
        return server if isinstance(server, datetime) else None

    async def async_turn_on(self, **kwargs) -> None:
        """Attiva la vacanza inviando la data di fine impostata (se futura)."""
        target = self._target_end()
        now = datetime.now(timezone.utc)

        if target is None or target <= now:
            _LOGGER.warning(
                "⚠️ Modo vacanza: imposta prima una data di fine futura "
                "nell'entità 'Modo Vacanza Fine', poi attiva lo switch."
            )
            # Nessun invio: ripristina lo stato reale (resta Off).
            self.async_write_ha_state()
            return

        epoch_ms = int(target.timestamp() * 1000)
        _LOGGER.info(
            "🏖️ Attivazione modo vacanza fino a %s (epoch_ms: %d)",
            target.isoformat(), epoch_ms,
        )

        ok = await self.hass.async_add_executor_job(
            self._api.set_configuration_parameter,
            PARAM_ID_HOLIDAY_MODE_END,
            epoch_ms,
        )

        if ok:
            _LOGGER.info("✅ Modo vacanza attivato fino a %s", target.isoformat())
            # Optimistic + pulizia staging
            self._api.holiday_mode = "On"
            self._api.holiday_mode_end = target
            self.hass.data[DOMAIN][HOLIDAY_STAGED_KEY] = None
            self.async_write_ha_state()
            await self._log(f"attivato fino a {target.isoformat()}")
            self.hass.async_create_task(self._grace_refresh())
        else:
            _LOGGER.error("❌ Attivazione modo vacanza fallita")

    async def async_turn_off(self, **kwargs) -> None:
        """Disattiva la vacanza inviando un valore nullo."""
        _LOGGER.info("🏖️ Disattivazione modo vacanza")

        ok = await self.hass.async_add_executor_job(
            self._api.set_configuration_parameter,
            PARAM_ID_HOLIDAY_MODE_END,
            HOLIDAY_MODE_DISABLE_VALUE,
        )

        if ok:
            _LOGGER.info("✅ Modo vacanza disattivato")
            # Optimistic + pulizia staging
            self._api.holiday_mode = "Off"
            self._api.holiday_mode_end = None
            self.hass.data[DOMAIN][HOLIDAY_STAGED_KEY] = None
            self.async_write_ha_state()
            await self._log("disattivato")
            self.hass.async_create_task(self._grace_refresh())
        else:
            _LOGGER.error("❌ Disattivazione modo vacanza fallita")

    async def _log(self, message: str) -> None:
        """Scrive una entry nel Logbook."""
        await self.hass.services.async_call(
            "logbook",
            "log",
            {
                "name": "Modo Vacanza",
                "message": message,
                "entity_id": self.entity_id,
            },
            blocking=False,
        )

    async def _grace_refresh(self) -> None:
        """Attende il read-back del device e riallinea dal cloud."""
        await asyncio.sleep(WRITE_GRACE_SECONDS)
        await self.coordinator.async_request_refresh()

    @property
    def device_info(self):
        return build_device_info(self._api)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Setup switch entities."""
    api = hass.data[DOMAIN][DATA_KEY_API]
    coordinator = hass.data[DOMAIN]["coordinator"]

    async_add_entities([BaxiHolidayModeSwitch(coordinator, api)])
