import requests
import json
import logging

_LOGGER = logging.getLogger(__name__)

class BaxiHybridAppAPI:
    BASE_URL = "https://baxi.servitly.com/api"
    LOGIN_URL = BASE_URL + "/identity/users/login?apiKey=%2FY0ZcwoKJDmtRjXZzsOUmSJUoVQgT5Pka3F38EoD8ng0"
    TEMP_EXT_URL = BASE_URL + "/data/values?thingId=655f0852c9683d184890e7dd&pageSize=1&metricName=Temperatura%20esterna"
    TEMP_INT_URL = BASE_URL + "/data/values?thingId=655f0852c9683d184890e7dd&pageSize=1&metricName=Zona%201%20-%20Temperatura%20ambiente"
    WATER_PRESSURE_URL = BASE_URL + "/data/values?thingId=655f0852c9683d184890e7dd&pageSize=1&metricName=Pressione%20impianto"
    BOILER_FLOW_TEMP_URL = BASE_URL + "/data/values?thingId=655f0852c9683d184890e7dd&pageSize=1&metricName=Temperatura%20di%20mandata"
    DHW_STORAGE_TEMP_URL = BASE_URL + "/data/values?thingId=655f0852c9683d184890e7dd&pageSize=1&metricName=Temperatura%20accumulo%20sanitario"

    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.token = None
        self.refreshToken = None
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
                "browser": "Mozilla/5.0",
                "notificationDeviceId": "dummy"
            }]
        })

        headers = {
            'x-semioty-tenant': 'baxi',
            'content-type': 'application/json',
            'user-agent': 'Mozilla/5.0',
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

    def _make_request(self, url):
        if not self.token:
            _LOGGER.warning("⚠️ Nessun token: provo a ri-autenticare...")
            self.authenticate()
            if not self.token:
                _LOGGER.error("❌ Impossibile autenticarsi.")
                return None

        headers = {
            'x-semioty-tenant': 'baxi',
            'authorization': f'Bearer {self.token}',
            'user-agent': 'Mozilla/5.0',
            'x-requested-with': 'it.baxi.HybridApp'
        }

        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 401:
                _LOGGER.warning("🔐 Token scaduto o non valido. Riprovo con login...")
                self.authenticate()
                if not self.token:
                    _LOGGER.error("❌ Login fallito durante retry.")
                    return None
                headers['authorization'] = f'Bearer {self.token}'
                response = requests.get(url, headers=headers)

            if response.ok:
                return response.json()
            else:
                _LOGGER.error("❌ Errore nella richiesta: %s", response.text)
                return None
        except Exception as e:
            _LOGGER.exception("❌ Eccezione nella richiesta a %s: %s", url, e)
            return None

    def fetch_temperature_ext(self):
        data = self._make_request(self.TEMP_EXT_URL)
        if not data:
            return
        try:
            self.temp_ext = float(data["data"][0]["values"][0]["value"])
            self.temp_ext_timestamp = data["data"][0]["timestamp"]
            _LOGGER.info("🌡️ External temperature: %s °C at %s", self.temp_ext, self.temp_ext_timestamp)
        except (KeyError, IndexError, ValueError) as parse_error:
            _LOGGER.warning("⚠️ Parsing fallito temperatura esterna: %s", parse_error)

    def fetch_temperature_int(self):
        data = self._make_request(self.TEMP_INT_URL)
        if not data:
            return
        try:
            self.temp_int = float(data["data"][0]["values"][0]["value"])
            self.temp_int_timestamp = data["data"][0]["timestamp"]
            _LOGGER.info("🌡️ Internal temperature: %s °C at %s", self.temp_int, self.temp_int_timestamp)
        except (KeyError, IndexError, ValueError) as parse_error:
            _LOGGER.warning("⚠️ Parsing fallito temperatura interna: %s", parse_error)

    def fetch_water_pressure(self):
        data = self._make_request(self.WATER_PRESSURE_URL)
        if not data:
            return
        try:
            self.water_pressure = float(data["data"][0]["values"][0]["value"])
            self.water_pressure_timestamp = data["data"][0]["timestamp"]
            _LOGGER.info("🚿📊️ Water Pressure: %s Bar at %s", self.water_pressure, self.water_pressure_timestamp)
        except (KeyError, IndexError, ValueError) as parse_error:
            _LOGGER.warning("⚠️ Parsing fallito pressione impianto: %s", parse_error)

    def fetch_boiler_flow_temp(self):
        data = self._make_request(self.BOILER_FLOW_TEMP_URL)
        if not data:
            return
        try:
            self.boiler_flow_temp = float(data["data"][0]["values"][0]["value"])
            self.boiler_flow_temp_timestamp = data["data"][0]["timestamp"]
            _LOGGER.info("🌡️ Boiler flow temperature: %s °C at %s", self.boiler_flow_temp, self.boiler_flow_temp_timestamp)
        except (KeyError, IndexError, ValueError) as parse_error:
            _LOGGER.warning("⚠️ Parsing fallito temperatura mandata: %s", parse_error)

    def fetch_dhw_storage_temp(self):
        data = self._make_request(self.DHW_STORAGE_TEMP_URL)
        if not data:
            return
        try:
            self.dhw_storage_temp = float(data["data"][0]["values"][0]["value"])
            self.dhw_storage_temp_timestamp = data["data"][0]["timestamp"]
            _LOGGER.info("🌡️ DHW storage temperature: %s °C at %s", self.dhw_storage_temp, self.dhw_storage_temp_timestamp)
        except (KeyError, IndexError, ValueError) as parse_error:
            _LOGGER.warning("⚠️ Parsing fallito accumulo sanitario: %s", parse_error)
