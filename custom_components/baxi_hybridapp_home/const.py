"""
Constants for Baxi Hybrid App custom integration for Home Assistant.

Solo valori "fissi" (nessun import da Home Assistant): identificativi di
dominio, credenziali statiche dell'app Android Baxi, parameter ID, limiti.
Le tabelle delle metriche e i descrittori dei sensori energia vivono in
metrics.py.

custom_components/baxi_hybridapp_home/const.py
"""

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

# Sanitary temperature limits
SANITARY_MIN_TEMP = 30
SANITARY_MAX_TEMP = 52
