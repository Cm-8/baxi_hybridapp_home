"""
Constants for Baxi Hybrid App custom integration for Home Assistant.

Solo valori "fissi": identificativi di dominio, credenziali statiche
dell'app Android Baxi, parameter ID, limiti, intervallo di polling.
Le tabelle delle metriche e i descrittori dei sensori energia vivono in
metrics.py.

custom_components/baxi_hybridapp_home/const.py
"""

import json
from pathlib import Path
from datetime import timedelta

# Versione letta direttamente da manifest.json — rimane automaticamente
# in sync senza dover duplicare il numero in due posti.
_manifest = json.loads((Path(__file__).parent / "manifest.json").read_text(encoding="utf-8"))
INTEGRATION_VERSION: str = _manifest.get("version", "?")

# Intervallo di polling del coordinator (modificare qui per tutti i cicli).
POLLING_INTERVAL: timedelta = timedelta(minutes=10)

DOMAIN = "baxi_hybridapp_home"
DATA_KEY_API = "api"

APIKEY = "%2FY0ZcwoKJDmtRjXZzsOUmSJUoVQgT5Pka3F38EoD8ng0"
TENANT = 'baxi'

DEV_BROWSER = "Mozilla/5.0"
DEV_MODEL = "sdk_gphone64_x86_64"
DEV_ID = "d26611220fb0ca70"
PLATFORM = "Android"

# Parameter IDs
PARAM_ID_SETPOINT_COMFORT = "5bec6274dbdf4f0008a6e012"
PARAM_ID_SETPOINT_ECO     = "5bec6275dbdf4f0008a6e013"

# Command IDs — Modo Impianto (PUT /data/commands?commandId=...&thingId=...)
COMMAND_ID_MODE_STANDBY        = "5bec6335dbdf4f0008a6e059"
COMMAND_ID_MODE_SOLO_SANITARIO = "5bec6335dbdf4f0008a6e05a"
COMMAND_ID_MODE_AUTOMATICO     = "5bec6338dbdf4f0008a6e05f"

# Sanitary temperature limits
SANITARY_MIN_TEMP = 30
SANITARY_MAX_TEMP = 52
