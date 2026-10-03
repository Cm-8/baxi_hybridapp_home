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

from .device import build_device_info

# Sola lettura, aggiornata dal coordinator: nessun limite al parallelismo.
PARALLEL_UPDATES = 0


class BaxiAlertBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor che riflette la presenza di un alert attivo per una severity."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    # Stessa categoria del pulsante "Aggiorna dati Baxi": compare nella sezione
    # "Diagnostica" del device card invece che nei sensori principali.
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    # Nome tradotto (entity.binary_sensor.<translation_key>); icone per stato
    # (on = alert attivo) in icons.json.
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        api,
        *,
        severity: str,
        translation_key: str,
        unique_id: str,
        enabled_default: bool,
    ) -> None:
        super().__init__(coordinator)
        self._api = api
        self._severity = severity
        self._attr_translation_key = translation_key
        self._attr_unique_id = unique_id
        self._attr_entity_registry_enabled_default = enabled_default
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
        return build_device_info(self._api)


async def async_setup_entry(hass, entry, async_add_entities):
    api = entry.runtime_data.api
    coordinator = entry.runtime_data.coordinator
    async_add_entities([
        BaxiAlertBinarySensor(
            coordinator, api,
            severity="FAILURE",
            translation_key="failure_alert",
            unique_id="baxi_failure_alert_active",
            enabled_default=True,
        ),
        BaxiAlertBinarySensor(
            coordinator, api,
            severity="WARNING",
            translation_key="warning_alert",
            unique_id="baxi_warning_alert_active",
            enabled_default=False,
        ),
    ])
