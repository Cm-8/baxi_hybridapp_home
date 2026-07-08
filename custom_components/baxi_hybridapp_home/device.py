"""
Device info condivisa per tutte le entità Baxi Hybrid App.

Unica fonte di verità per il blocco device_info: tutte le piattaforme la
importano, così il device registry riceve metadati completi e coerenti
indipendentemente dall'ordine di registrazione delle entità (prima era
sparso in 9 copie, alcune parziali).

custom_components/baxi_hybridapp_home/device.py
"""

from .const import DOMAIN


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
