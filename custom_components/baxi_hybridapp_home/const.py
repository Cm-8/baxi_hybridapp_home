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

# Grazia dopo una scrittura (PUT parametro/comando) prima del refresh dal
# cloud: il device deve applicare e ri-pubblicare la metrica (read-back).
# Con 8s il refresh arrivava troppo presto e riportava in UI il valore
# precedente (visto su setpoint raffrescamento e modo impianto).
WRITE_GRACE_SECONDS = 30

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
PARAM_ID_SETPOINT_RAFFRESCAMENTO = "5bec6273dbdf4f0008a6e011"
PARAM_ID_HOLIDAY_MODE_END = "5bec63132898ef0008034886"
# Valore inviato per DISATTIVARE la vacanza: la stringa "-1" (confermato da
# cattura della PUT di spegnimento dell'app — vedi PUT Modo Vacanza.http).
# NB: è una stringa, non un intero; l'attivazione invia invece l'epoch ms
# come numero.
HOLIDAY_MODE_DISABLE_VALUE = "-1"
# Chiave in hass.data[DOMAIN] per la data di fine vacanza "in staging":
# il datetime la memorizza qui senza inviare, lo switch la legge e la applica.
HOLIDAY_STAGED_KEY = "holiday_mode_staged_end"

# Command IDs — Modo Impianto (PUT /data/commands?commandId=...&thingId=...)
COMMAND_ID_MODE_STANDBY        = "5bec6335dbdf4f0008a6e059"
COMMAND_ID_MODE_SOLO_SANITARIO = "5bec6335dbdf4f0008a6e05a"
COMMAND_ID_MODE_AUTOMATICO     = "5bec6338dbdf4f0008a6e05f"

# Command IDs — Modo Stagione (stesso endpoint; scrivono P02P012C 0001-0004,
# letto dalla metrica "Modo Stagione" → api.season_mode)
COMMAND_ID_SEASON_ESTATE     = "5bec6336dbdf4f0008a6e05b"
COMMAND_ID_SEASON_INVERNO    = "5bec6336dbdf4f0008a6e05c"
COMMAND_ID_SEASON_AUTOMATICO = "5bec6337dbdf4f0008a6e05d"
COMMAND_ID_SEASON_REMOTO     = "5bec6337dbdf4f0008a6e05e"

# Sanitary temperature limits
SANITARY_MIN_TEMP = 30
SANITARY_MAX_TEMP = 52

# Cooling setpoint limits (range dal catalogo parametri: 7.0-30.0, step 1.0)
COOLING_MIN_TEMP = 7
COOLING_MAX_TEMP = 30
