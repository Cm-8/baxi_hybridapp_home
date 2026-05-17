"""
Binary sensor platform for Baxi Hybrid App custom integration.

Esponde due binary_sensor per gli alert storici Servitly:
- baxi_failure_alert_active (abilitato di default)
- baxi_warning_alert_active (DISABILITATO di default — l'utente lo abilita
  manualmente dal Registro Entità se vuole tracciare anche i WARNING tipo
  "device OFFLINE", che altrimenti creerebbero rumore).

device_class=PROBLEM → HA usa la semantica standard "se PROBLEM è on,
allora qualcosa non va" e l'icona di errore appropriata.

I valori (active_*_alert / last_*_alert) sono popolati da
BaxiHybridAppAPI.fetch_historical_alerts (vedi api.py).

custom_components/baxi_hybridapp_home/binary_sensor.py
"""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DATA_KEY_API


class BaxiAlertBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor che riflette la presenza di un alert attivo per una severity."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    # Stessa categoria del pulsante "Aggiorna dati Baxi": compare nella sezione
    # "Diagnostica" del device card invece che nei sensori principali.
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator,
        api,
        *,
        severity: str,
        name: str,
        unique_id: str,
        enabled_default: bool,
        icon: str | None = None,
        icon_off: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._api = api
        self._severity = severity
        self._attr_name = name
        self._attr_unique_id = unique_id
        self._attr_entity_registry_enabled_default = enabled_default
        # icon     → icona quando is_on=True (alert attivo)
        # icon_off → icona quando is_on=False (nessun alert). Se None, viene
        #            usata icon anche in stato off (icona statica).
        self._icon_on = icon
        self._icon_off = icon_off
        if icon is not None and icon_off is None:
            self._attr_icon = icon
        # Attributi sull'istanza API da cui leggere stato corrente e ultimo evento.
        self._active_attr = (
            "active_failure_alert" if severity == "FAILURE"
            else "active_warning_alert"
        )
        self._last_attr = (
            "last_failure_alert" if severity == "FAILURE"
            else "last_warning_alert"
        )

    @property
    def is_on(self) -> bool:
        return getattr(self._api, self._active_attr, None) is not None

    @property
    def icon(self) -> str | None:
        # Se è stato configurato icon_off, l'icona è condizionale; altrimenti
        # HA legge _attr_icon (statico).
        if self._icon_off is not None:
            return self._icon_on if self.is_on else self._icon_off
        return self._attr_icon

    @property
    def available(self) -> bool:
        # Disponibile appena il coordinator ha completato almeno un fetch.
        return self.coordinator.last_update_success

    @property
    def extra_state_attributes(self):
        # Fallback: se non c'è alert attivo, mostra comunque l'ultimo visto
        # (con is_active=False) per dare contesto in dashboard.
        active = getattr(self._api, self._active_attr, None)
        last = getattr(self._api, self._last_attr, None)
        snapshot = active or last
        if not snapshot:
            return {}
        return {
            "id": snapshot.get("id"),
            "title": snapshot.get("title"),
            "description": snapshot.get("description"),
            "code": snapshot.get("code"),
            "start_ts": snapshot.get("start_ts"),
            "end_ts": snapshot.get("end_ts"),
            "is_active": active is not None,
        }

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "baxi_hybridapp_home")},
            "name": "Baxi HybridApp Home",
            "manufacturer": "Baxi",
            "model": getattr(self._api, "thingModel", None) or "HybridApp",
            "serial_number": getattr(self._api, "serialNumber", None),
            "sw_version": getattr(self._api, "thingFirmware", None),
        }


async def async_setup_entry(hass, entry, async_add_entities):
    api = hass.data[DOMAIN][DATA_KEY_API]
    coordinator = hass.data[DOMAIN]["coordinator"]
    async_add_entities([
        BaxiAlertBinarySensor(
            coordinator, api,
            severity="FAILURE",
            name="Failure",
            unique_id="baxi_failure_alert_active",
            enabled_default=True,
            icon="mdi:alert-box",
            icon_off="mdi:check-circle",
        ),
        BaxiAlertBinarySensor(
            coordinator, api,
            severity="WARNING",
            name="Warning",
            unique_id="baxi_warning_alert_active",
            enabled_default=False,
            icon="mdi:alert-box-outline",
            icon_off="mdi:check-circle-outline",
        ),
    ])
