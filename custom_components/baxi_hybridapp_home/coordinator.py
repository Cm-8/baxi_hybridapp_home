"""
DataUpdateCoordinator for Baxi Hybrid App custom integration.

custom_components/baxi_hybridapp_home/coordinator.py
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import __version__ as ha_version
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BaxiAuthError, BaxiConnectionError, BaxiHybridAppAPI
from .const import CONF_POLLING_INTERVAL, DEFAULT_POLLING_INTERVAL, DOMAIN, INTEGRATION_VERSION
from .metrics import ENERGY_SENSOR_TYPES, SIMPLE_METRICS

_LOGGER = logging.getLogger(__name__)


def polling_interval(entry: ConfigEntry) -> timedelta:
    """Intervallo scelto con il pulsante Configura, altrimenti quello predefinito."""
    return timedelta(minutes=int(entry.options.get(CONF_POLLING_INTERVAL, DEFAULT_POLLING_INTERVAL)))


class BaxiDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator che gestisce il polling dei dati Baxi Servitly."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: BaxiHybridAppAPI) -> None:
        self.api = api
        # Riepilogo capabilities loggato una sola volta per sessione (solo debug).
        self._capabilities_logged = False
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="baxi_hybridapp_home",
            update_interval=polling_interval(entry),
        )

    def _log_fetch_info(self) -> None:
        """Logga versione HA/integrazione e modello device all'inizio di ogni ciclo."""
        _LOGGER.debug(
            "🔄 Ciclo fetch — HA: %s | Integrazione: %s | Polling: %s | Modello: %s (%s)",
            ha_version,
            INTEGRATION_VERSION,
            self.update_interval,
            self.api.thingModel or "?",
            self.api.thingDefinitionName or "?",
        )

    async def _async_log_capabilities_once(self) -> None:
        """Riepilogo capabilities del modello, una volta per sessione (solo debug).

        I cataloghi sono statici per-modello: le 3 GET extra le paga solo chi
        ha il debug attivo, una volta per riavvio. Il dettaglio completo si
        scarica dalla diagnostica dell'integrazione (diagnostics.py).
        """
        if self._capabilities_logged or not _LOGGER.isEnabledFor(logging.DEBUG):
            return
        caps = await self.hass.async_add_executor_job(self.api.fetch_capabilities)
        if not caps:
            return  # thingDefinitionId mancante: riproverà al prossimo ciclo
        self._capabilities_logged = True
        n_read = len(SIMPLE_METRICS) + len(ENERGY_SENSOR_TYPES) + 1  # +1 scheduler sanitario
        _LOGGER.debug(
            "🔍 Commands %s: %d comandi, %d parametri di configurazione",
            self.api.thingDefinitionName or "?",
            len(caps.get("commands") or []),
            len(caps.get("configuration_parameters") or []),
        )
        _LOGGER.debug(
            "🔍 Metrics %s: %d metriche cloud, %d lette dall'integrazione — dettaglio completo nella diagnostica dell'integrazione",
            self.api.thingDefinitionName or "?",
            len(caps.get("metrics") or []),
            n_read,
        )

    async def _async_update_data(self) -> bool:
        """Fetch all metrics from Baxi API."""
        # Authentication (solo se serve), con eccezioni tipizzate:
        # - credenziali rifiutate → ConfigEntryAuthFailed → HA avvia il re-auth flow
        # - cloud irraggiungibile → UpdateFailed → retry con backoff, entità unavailable
        if not self.api.token:
            try:
                await self.hass.async_add_executor_job(self.api.login)
            except BaxiAuthError as err:
                raise ConfigEntryAuthFailed("Credenziali Baxi non valide") from err
            except BaxiConnectionError as err:
                raise UpdateFailed(f"Cloud Baxi non raggiungibile: {err}") from err
        if not self.api.thingId:
            await self.hass.async_add_executor_job(self.api.get_thingid)
            if not self.api.thingId:
                raise UpdateFailed("Impossibile ottenere il thingId dal cloud Baxi")
        # Catalogo metriche del modello: una volta per avvio (ritentato finché
        # non riesce). Il primo ciclo gira prima della creazione delle entità,
        # quindi le piattaforme sanno già quali metriche esistono.
        if self.api.model_metrics is None:
            await self.hass.async_add_executor_job(self.api.fetch_model_metrics)
        # Log DOPO auth+thingId: thingModel e thingDefinitionName sono garantiti
        self._log_fetch_info()
        await self._async_log_capabilities_once()
        # Conteggio esiti delle richieste di lettura di questo ciclo.
        self.api.reset_request_stats()
        # Tutte le metriche (semplici di SIMPLE_METRICS, scheduler sanitario,
        # energia di ENERGY_SENSOR_TYPES) con una sola richiesta
        # /data/lastValues; letture singole solo per le metriche assenti.
        # Tutto nell'executor (lo scheduler usa ZoneInfo, che legge file).
        await self.hass.async_add_executor_job(self.api.fetch_all_metrics)
        # Historical alerts (FAILURE/WARNING): popola active/last/conteggi
        # sull'istanza API e accoda i nuovi alert in api.new_alerts_pending.
        await self.hass.async_add_executor_job(self.api.fetch_historical_alerts)
        # Token scaduto, rinnovo non riuscito e password rifiutata durante il
        # ciclo: ri-autenticazione subito, non al ciclo successivo.
        if self.api.auth_rejected:
            raise ConfigEntryAuthFailed("Credenziali Baxi non più valide")
        # Una richiesta fallita conserva il valore precedente. Se però non ne è
        # riuscita nessuna il cloud è irraggiungibile: UpdateFailed rende le
        # entità non disponibili e il coordinator lo logga una volta sola
        # (e una volta al ritorno), invece di un errore per ogni metrica.
        ok, failed = self.api.request_stats()
        if failed and not ok:
            raise UpdateFailed(
                f"Cloud Baxi non raggiungibile: nessuna delle {len(failed)} richieste è riuscita"
            )
        if failed:
            _LOGGER.warning(
                "⚠️ %d richieste su %d non riuscite in questo ciclo (valori precedenti mantenuti): %s",
                len(failed), ok + len(failed),
                ", ".join(failed[:8]) + (" …" if len(failed) > 8 else ""),
            )
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


@dataclass
class BaxiRuntimeData:
    """Dati di runtime della config entry, in entry.runtime_data (regola runtime-data)."""

    api: BaxiHybridAppAPI
    coordinator: BaxiDataUpdateCoordinator
    # Data di fine vacanza impostata a vacanza spenta e non ancora applicata:
    # la scrive il datetime "Modo Vacanza Fine", la applica lo switch.
    holiday_staged_end: datetime | None = None


type BaxiConfigEntry = ConfigEntry[BaxiRuntimeData]
