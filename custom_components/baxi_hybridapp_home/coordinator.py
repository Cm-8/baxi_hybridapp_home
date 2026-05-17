"""
DataUpdateCoordinator for Baxi Hybrid App custom integration.

custom_components/baxi_hybridapp_home/coordinator.py
"""

from __future__ import annotations

from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import BaxiHybridAppAPI
from .const import DOMAIN

import logging

_LOGGER = logging.getLogger(__name__)


class BaxiDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator che gestisce il polling dei dati Baxi Servitly."""

    def __init__(self, hass: HomeAssistant, api: BaxiHybridAppAPI) -> None:
        self.api = api
        super().__init__(
            hass,
            _LOGGER,
            name="baxi_hybridapp_home",
            update_interval=timedelta(minutes=10),
        )

    async def _async_update_data(self) -> bool:
        """Fetch all metrics from Baxi API."""
        # Authentication and thingId (solo se serve)
        if not self.api.token:
            await self.hass.async_add_executor_job(self.api.authenticate)
        if not self.api.thingId:
            await self.hass.async_add_executor_job(self.api.get_thingid)
        # Metriche "semplici" (un valore per metric_name): tutte in un unico
        # dispatcher tabellare, vedi SIMPLE_METRICS in metrics.py.
        await self.hass.async_add_executor_job(self.api.fetch_simple_metrics)
        # Scheduler sanitario (parsing JSON con logica derivata custom)
        await self.hass.async_add_executor_job(self.api.fetch_sanitary_scheduler)
        # Sensori energia (tabellari via ENERGY_SENSOR_TYPES in metrics.py)
        await self.hass.async_add_executor_job(self.api.fetch_energy_metrics)
        # Historical alerts (FAILURE/WARNING): popola active/last/conteggi
        # sull'istanza API e accoda i nuovi alert in api.new_alerts_pending.
        await self.hass.async_add_executor_job(self.api.fetch_historical_alerts)
        # Per ogni alert mai visto in questa sessione:
        #   1) fire event sul bus HA → trigger per automazioni (severity in payload)
        #   2) entry nel Logbook → "sezione attività" dell'integrazione
        # Risolvi l'entity_id reale via entity registry: hardcodarlo non
        # funziona perché HA lo genera dal primo `name` dell'entità (es.
        # "binary_sensor.avviso_failure_attivo" su installazioni precedenti
        # ai rename).
        ent_reg = er.async_get(self.hass)
        for alert in list(self.api.new_alerts_pending):
            self.hass.bus.async_fire("baxi_hybridapp_alert", alert)
            unique_id = (
                "baxi_failure_alert_active"
                if alert.get("severity") == "FAILURE"
                else "baxi_warning_alert_active"
            )
            entity_id = (
                ent_reg.async_get_entity_id("binary_sensor", DOMAIN, unique_id)
                or f"binary_sensor.{unique_id}"
            )
            code = alert.get("code")
            base_msg = (
                alert.get("description")
                or alert.get("title")
                or "Nuovo avviso"
            )
            msg = f"{code} — {base_msg}" if code else base_msg
            await self.hass.services.async_call(
                "logbook", "log",
                {
                    "name": f"Baxi {alert.get('severity', 'ALERT')}",
                    "message": msg,
                    "entity_id": entity_id,
                },
                blocking=False,
            )
        return True
