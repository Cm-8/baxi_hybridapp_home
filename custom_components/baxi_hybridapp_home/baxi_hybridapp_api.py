import requests
import json
import logging
from urllib.parse import quote_plus
from .const import APIKEY, DEV_BROWSER

_LOGGER = logging.getLogger(__name__)

class BaxiHybridAppAPI:
    BASE_URL = "https://baxi.servitly.com/api"
    LOGIN_URL = BASE_URL + "/identity/users/login?apiKey=" + APIKEY
    THINGS_URL = BASE_URL + "/v2/identity/users/me/things"

    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.token = None
        self.refreshToken = None
        self.thingId = None
        self.temp_ext = None
        self.temp_ext_timestamp = None
        self.temp_int = None
        self.temp_int_timestamp = None
        self.water_pressure = None
        self.water_pressure_timestamp = None
        self.boiler_flow_temp = None
        self.boiler_flow_temp_timestamp = None
        self.dhw_storage_temp = None
        self.dhw_storage_temp_timestamp = None

    def authenticate(self):
        payload = json.dumps({
            "email": self.username,
            "password": self.password,
            "devices": [{
                "deviceId": "d26611220fb0ca70",
                "model": "sdk_gphone64_x86_64",
                "platform": "Android",
                "platformVersion": "12",
                "browser": DEV_BROWSER,
                "notificationDeviceId": "dummy"
            }]
        })

        headers = {
            'x-semioty-tenant': 'baxi',
            'content-type': 'application/json',
            'user-agent': DEV_BROWSER,
            'x-requested-with': 'it.baxi.HybridApp'
        }

        try:
            response = requests.post(self.LOGIN_URL, headers=headers, data=payload)
            if response.ok:
                data = response.json()
                self.token = data.get("token")
                self.refreshToken = data.get("refreshToken")
                _LOGGER.info("✅ BAXI Login successful: %s", data)
            else:
                _LOGGER.error("❌ BAXI Login failed: %s", response.text)
        except Exception as e:
            _LOGGER.exception("❌ BAXI Login exception: %s", e)

    def get_thingid (self) -> str:
        if not self.token:
            _LOGGER.warning("⚠️ Nessun token: provo a ri-autenticare...")
            self.authenticate()
            if not self.token:
                _LOGGER.error("❌ Impossibile autenticarsi.")
                return None
                
        headers = {
            'x-semioty-tenant': 'baxi',
            'authorization': f'Bearer {self.token}',
            'user-agent': DEV_BROWSER,
            'x-requested-with': 'it.baxi.HybridApp'
        }
        
        try:
            response = requests.get(self.THINGS_URL, headers=headers)
            if response.ok:
                data = response.json()
                content = data.get("content", [])
                
                self.thingId = content[0].get("id") if content else None
                _LOGGER.info("✅ Thing ID ottenuto: %s", self.thingId)
                return self.thingId
            else:
                _LOGGER.error("❌ Questo Account Baxi non ha un impianto(ThingId) associato: %s", response.text)
                return None
        except Exception as e:
            _LOGGER.exception("❌ Eccezione nel recupero thingId: %s", e)
            return None

    def _make_request(self, url: str):
        if not self.token:
            _LOGGER.warning("⚠️ Nessun token: provo a ri-autenticare.")
            self.authenticate()
            if not self.token:
                _LOGGER.error("❌ Impossibile autenticarsi.")
                return None

        headers = {
            'x-semioty-tenant': 'baxi',
            'authorization': f'Bearer {self.token}',
            'user-agent': DEV_BROWSER,
            'x-requested-with': 'it.baxi.HybridApp'
        }

        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 401:
                _LOGGER.warning("🔐 Token scaduto, riprovo autenticazione...")
                self.authenticate()
                headers['authorization'] = f'Bearer {self.token}'
                response = requests.get(url, headers=headers)

            if response.ok:
                return response.json()
            else:
                _LOGGER.error("❌ Errore nella richiesta %s: %s", url, response.text)
                return None
        except Exception as e:
            _LOGGER.exception("❌ Eccezione nella richiesta a %s: %s", url, e)
            return None

    def _metric_url(self, metric_name: str) -> str:
        if not self.thingId:
            raise RuntimeError("thingId non inizializzato")
        return (
            f"{self.BASE_URL}/data/values?"
            f"thingId={self.thingId}&pageSize=1&metricName={quote_plus(metric_name)}"
        )

    def fetch_temperature_ext(self):
        data = self._make_request(self._metric_url("Temperatura esterna"))
        if not data:
            return
        try:
            item = data["data"][0]
            self.temp_ext = float(item["values"][0]["value"])
            self.temp_ext_timestamp = item["timestamp"]
            _LOGGER.info("🌡️ External temperature: %s °C at %s", self.temp_ext, self.temp_ext_timestamp)
        except (KeyError, IndexError, ValueError) as e:
            _LOGGER.warning("⚠️ Parsing fallito temperatura esterna: %s", e)

    def fetch_temperature_int(self):
        data = self._make_request(self._metric_url("Zona 1 - Temperatura ambiente"))
        if not data:
            return
        try:
            item = data["data"][0]
            self.temp_int = float(item["values"][0]["value"])
            self.temp_int_timestamp = item["timestamp"]
            _LOGGER.info("🌡️ Internal temperature: %s °C at %s", self.temp_int, self.temp_int_timestamp)
        except (KeyError, IndexError, ValueError) as e:
            _LOGGER.warning("⚠️ Parsing fallito temperatura interna: %s", e)

    def fetch_water_pressure(self):
        data = self._make_request(self._metric_url("Pressione impianto"))
        if not data:
            return
        try:
            item = data["data"][0]
            self.water_pressure = float(item["values"][0]["value"])
            self.water_pressure_timestamp = item["timestamp"]
            _LOGGER.info("🚿📊️ Water pressure: %s Bar at %s", self.water_pressure, self.water_pressure_timestamp)
        except (KeyError, IndexError, ValueError) as e:
            _LOGGER.warning("⚠️ Parsing fallito pressione impianto: %s", e)

    def fetch_boiler_flow_temp(self):
        data = self._make_request(self._metric_url("Temperatura di mandata"))
        if not data:
            return
        try:
            item = data["data"][0]
            self.boiler_flow_temp = float(item["values"][0]["value"])
            self.boiler_flow_temp_timestamp = item["timestamp"]
            _LOGGER.info("🌡️ Boiler flow temperature: %s °C at %s", self.boiler_flow_temp, self.boiler_flow_temp_timestamp)
        except (KeyError, IndexError, ValueError) as e:
            _LOGGER.warning("⚠️ Parsing fallito temperatura mandata: %s", e)

    def fetch_dhw_storage_temp(self):
        data = self._make_request(self._metric_url("Temperatura accumulo sanitario"))
        if not data:
            return
        try:
            item = data["data"][0]
            self.dhw_storage_temp = float(item["values"][0]["value"])
            self.dhw_storage_temp_timestamp = item["timestamp"]
            _LOGGER.info("🌡️ DHW storage temperature: %s °C at %s", self.dhw_storage_temp, self.dhw_storage_temp_timestamp)
        except (KeyError, IndexError, ValueError) as e:
            _LOGGER.warning("⚠️ Parsing fallito accumulo sanitario: %s", e)
