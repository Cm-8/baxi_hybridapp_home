"""
Device info e creazione delle entità, condivise da tutte le piattaforme Baxi Hybrid App.

Unica fonte di verità per il blocco device_info: tutte le piattaforme la
importano, così il device registry riceve metadati completi e coerenti
indipendentemente dall'ordine di registrazione delle entità (prima era
sparso in 9 copie, alcune parziali).

custom_components/baxi_hybridapp_home/device.py
"""

import logging

from homeassistant.helpers import entity_registry as er

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


def build_device_info(api) -> dict:
    """Blocco device_info comune (un solo device per config entry)."""
    return {
        "identifiers": {(DOMAIN, "baxi_hybridapp_home")},
        "name": "Baxi HybridApp Home",
        "manufacturer": "Baxi",
        "model": getattr(api, "thingModel", None) or "HybridApp",
        "model_id": getattr(api, "thingModel", None),
        "serial_number": getattr(api, "serialNumber", None),
        "hw_version": "n.d.",
        "sw_version": getattr(api, "thingFirmware", None),
        "configuration_url": "https://altuofianco.baxi.it/login",
    }


def async_add_provided_entities(hass, api, platform: str, entities, async_add_entities, *args) -> None:
    """Aggiunge solo le entità i cui dati esistono sul modello dell'impianto.

    Ogni entità indica in `_source_attr` l'attributo dell'API che legge; se la
    metrica corrispondente non è nel catalogo del modello (api.provides) l'entità
    non viene creata e, se registrata da una versione precedente, viene tolta
    dal registro, altrimenti resterebbe come "non disponibile". Con il catalogo
    non ancora noto si crea tutto, come prima.
    """
    registry = er.async_get(hass)
    provided = []
    for entity in entities:
        attr = getattr(entity, "_source_attr", None)
        if attr is None or api.provides(attr):
            provided.append(entity)
            continue
        entity_id = registry.async_get_entity_id(platform, DOMAIN, entity.unique_id)
        if entity_id:
            registry.async_remove(entity_id)
            _LOGGER.info("🧹 %s rimossa: dato non presente su questo modello", entity_id)
    async_add_entities(provided, *args)
