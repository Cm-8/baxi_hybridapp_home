import requests
import json
import logging
from urllib.parse import quote_plus
from .const import APIKEY, TENANT, DEV_BROWSER, DEV_MODEL

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
        self.sanitary_on = None
        self.sanitary_on_timestamp = None
        self.boiler_flow_temp = None
        self.boiler_flow_temp_timestamp = None
        self.dhw_storage_temp = None
        self.dhw_storage_temp_timestamp = None
        self.dhw_aux_storage_temp = None
        self.dhw_aux_storage_temp_timestamp = None
        self.pdc_exit_temp = None
        self.pdc_exit_temp_timestamp = None
        self.pdc_return_temp = None
        self.pdc_return_temp_timestamp = None
        self.setpoint_instant_temp = None
        self.setpoint_instant_temp_timestamp = None
        self.setpoint_comfort_temp = None
        self.setpoint_comfort_temp_timestamp = None
        self.setpoint_eco_temp = None
        self.setpoint_eco_temp_timestamp = None
        self.system_mode = None
        self.system_mode_timestamp = None
        self.season_mode = None
        self.season_mode_timestamp = None

    def authenticate(self):
        payload = json.dumps({
            "email": self.username,
            "password": self.password,
            "devices": [{
                "deviceId": "d26611220fb0ca70",
                "model": DEV_MODEL,
                "platform": "Android",
                "platformVersion": "12",
                "browser": DEV_BROWSER,
                "notificationDeviceId": "dummy"
            }]
        })

        headers = {
            'x-semioty-tenant': TENANT,
            'content-type': 'application/json',
            'user-agent': DEV_BROWSER,
            'x-requested-with': 'it.baxi.HybridApp'
        }

        try:
            response = requests.post(self.LOGIN_URL, headers=headers, data=payload, timeout=15)
            if response.ok:
                data = response.json()
                self.token = data.get("token")
                self.refreshToken = data.get("refreshToken")
                # safe token
                safe = {**data, "token": "***", "refreshToken": "***"}
                _LOGGER.info("✅ BAXI Login successful: %s", json.dumps(safe)[:300])
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
            'x-semioty-tenant': TENANT,
            'authorization': f'Bearer {self.token}',
            'user-agent': DEV_BROWSER,
            'x-requested-with': 'it.baxi.HybridApp'
        }
        
        try:
            response = requests.get(self.THINGS_URL, headers=headers, timeout=15)
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
            'x-semioty-tenant': TENANT,
            'authorization': f'Bearer {self.token}',
            'user-agent': DEV_BROWSER,
            'x-requested-with': 'it.baxi.HybridApp'
        }

        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 401:
                _LOGGER.warning("🔐 Token scaduto, riprovo autenticazione...")
                self.authenticate()
                headers['authorization'] = f'Bearer {self.token}'
                response = requests.get(url, headers=headers, timeout=15)

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
            f"thingId={self.thingId}"
            f"&pageSize=1"
            f"&metricName={quote_plus(metric_name)}"
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
            # logga l’errore e tutta la risposta 'data'
            _LOGGER.warning("⚠️ Parsing fallito (temperatura esterna): %s — response 📦: %s", e, json.dumps(data)[:300])
            _LOGGER.debug("📦 Contenuto data (temperatura esterna): %s", data)

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
            # logga l’errore e tutta la risposta 'data'
            _LOGGER.warning("⚠️ Parsing fallito (temperatura interna): %s — response 📦: %s", e, json.dumps(data)[:300])
            _LOGGER.debug("📦 Contenuto data (temperatura interna): %s", data)

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
            # logga l’errore e tutta la risposta 'data'
            _LOGGER.warning("⚠️ Parsing fallito (pressione impianto): %s — response 📦: %s", e, json.dumps(data)[:300])
            _LOGGER.debug("📦 Contenuto data (pressione impianto): %s", data)

    def fetch_sanitary_on(self):
        data = self._make_request(self._metric_url("Sanitario on"))
        if not data:
            return
        try:
            item = data["data"][0]
            raw = item["values"][0]["value"]  # sarà "0" o "1"
            # 0 = Spento, 1 = Acceso
            mapping = {
                "0": "Off",
                "0_1": "On 0_1",
                "1": "On 1",
            }
            self.sanitary_on = mapping.get(raw, f"Sconosciuto ({raw})")
            self.sanitary_on_timestamp = item["timestamp"]
            _LOGGER.info("🚿️ Sanitario: %s", self.sanitary_on)
        except (KeyError, IndexError, ValueError) as e:
            # logga l’errore e tutta la risposta 'data'
            _LOGGER.warning("⚠️ Parsing fallito (sanitario on): %s — response 📦: %s", e, json.dumps(data)[:300])
            _LOGGER.debug("📦 Contenuto data (sanitario on): %s", data)

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
            # logga l’errore e tutta la risposta 'data'
            _LOGGER.warning("⚠️ Parsing fallito (temperatura mandata): %s — response 📦: %s", e, json.dumps(data)[:300])
            _LOGGER.debug("📦 Contenuto data (temperatura mandata): %s", data)

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
            # Azzera il campo, logga l’errore, tutta la risposta 'data'
            self.dhw_storage_temp = None
            self.dhw_storage_temp_timestamp = None    
            _LOGGER.warning("⚠️ Parsing fallito (accumulo sanitario): %s — response 📦: %s", e, json.dumps(data)[:300])
            _LOGGER.debug("📦 Contenuto data (accumulo sanitario): %s", data)

    def fetch_dhw_aux_storage_temp(self):
        data = self._make_request(self._metric_url("Sonda accumulo ausiliario"))
        if not data:
            return
        try:
            item = data["data"][0]
            self.dhw_aux_storage_temp = float(item["values"][0]["value"])
            self.dhw_aux_storage_temp_timestamp = item["timestamp"]
            _LOGGER.info("🌡️ DHW aux storage temperature: %s °C", self.dhw_aux_storage_temp)
        except (KeyError, IndexError, ValueError) as e:
            # logga l’errore e tutta la risposta 'data'
            _LOGGER.warning("⚠️ Parsing fallito (accumulo ausigliario sanitario): %s — response 📦: %s", e, json.dumps(data)[:300])
            _LOGGER.debug("📦 Contenuto data (accumulo ausigliario sanitario): %s", data)

    def fetch_pdc_exit_temp(self):
        data = self._make_request(self._metric_url("Temperatura uscita pdc"))
        if not data:
            return
        try:
            item = data["data"][0]
            self.pdc_exit_temp = float(item["values"][0]["value"])
            self.pdc_exit_temp_timestamp = item["timestamp"]
            _LOGGER.info("🌡️ PDC exit temperature: %s °C", self.pdc_exit_temp)
        except (KeyError, IndexError, ValueError) as e:
            # logga l’errore e tutta la risposta 'data'
            _LOGGER.warning("⚠️ Parsing fallito (temperatura uscita PDC): %s — response 📦: %s", e, json.dumps(data)[:300])
            _LOGGER.debug("📦 Contenuto data (temperatura uscita PDC): %s", data)

    def fetch_pdc_return_temp(self):
        data = self._make_request(self._metric_url("Temperatura ritorno pdc"))
        if not data:
            return
        try:
            item = data["data"][0]
            self.pdc_return_temp = float(item["values"][0]["value"])
            self.pdc_return_temp_timestamp = item["timestamp"]
            _LOGGER.info("🌡️ PDC return temperature: %s °C", self.pdc_return_temp)
        except (KeyError, IndexError, ValueError) as e:
            # logga l’errore e tutta la risposta 'data'
            _LOGGER.warning("⚠️ Parsing fallito (temperatura ritorno PDC): %s — response 📦: %s", e, json.dumps(data)[:300])
            _LOGGER.debug("📦 Contenuto data (temperatura ritorno PDC): %s", data)



    def fetch_setpoint_instant_temp(self):
        data = self._make_request(self._metric_url("Set-point sanitario istantaneo"))
        if not data:
            return
        try:
            item = data["data"][0]
            self.setpoint_instant_temp = float(item["values"][0]["value"])
            self.setpoint_instant_temp_timestamp = item["timestamp"]
            _LOGGER.info("🌡️ Setpoint Istant temperature: %s °C", self.setpoint_instant_temp)
        except (KeyError, IndexError, ValueError) as e:
            # logga l’errore e tutta la risposta 'data'
            _LOGGER.warning("⚠️ Parsing fallito (Set-point Istantaneo): %s — response 📦: %s", e, json.dumps(data)[:300])
            _LOGGER.debug("📦 Contenuto data (Set-point Istantaneo): %s", data)

    def fetch_setpoint_comfort_temp(self):
        data = self._make_request(self._metric_url("Set-point sanitario comfort"))
        if not data:
            return
        try:
            item = data["data"][0]
            self.setpoint_comfort_temp = float(item["values"][0]["value"])
            self.setpoint_comfort_temp_timestamp = item["timestamp"]
            _LOGGER.info("🌡️ Setpoint Comfort temperature: %s °C", self.setpoint_comfort_temp)
        except (KeyError, IndexError, ValueError) as e:
            # logga l’errore e tutta la risposta 'data'
            _LOGGER.warning("⚠️ Parsing fallito (Set-point Comfort): %s — response 📦: %s", e, json.dumps(data)[:300])
            _LOGGER.debug("📦 Contenuto data (Set-point Comfort): %s", data)

    def fetch_setpoint_eco_temp(self):
        data = self._make_request(self._metric_url("Set-point sanitario eco"))
        if not data:
            return
        try:
            item = data["data"][0]
            self.setpoint_eco_temp = float(item["values"][0]["value"])
            self.setpoint_eco_temp_timestamp = item["timestamp"]
            _LOGGER.info("🌡️ Setpoint Eco temperature: %s °C", self.setpoint_eco_temp)
        except (KeyError, IndexError, ValueError) as e:
            # logga l’errore e tutta la risposta 'data'
            _LOGGER.warning("⚠️ Parsing fallito (Set-point Eco): %s — response 📦: %s", e, json.dumps(data)[:300])
            _LOGGER.debug("📦 Contenuto data (Set-point Eco): %s", data)



    def fetch_system_mode(self):
        data = self._make_request(self._metric_url("Modo Impianto"))
        if not data:
            return
        try:
            item = data["data"][0]
            raw = item["values"][0]["value"]
            mapping = {
                None: "Automatico",
                "0000": "Standby",
                "0005": "Solo Sanitario",
            }
            # salva la stringa leggibile (o il codice se non è previsto)
            self.system_mode = mapping.get(raw, f"Sconosciuto ({raw})")
            self.system_mode_timestamp = item["timestamp"]
            _LOGGER.info("🔄️ System Mode: %s",
                         self.system_mode)
        except (KeyError, IndexError, ValueError) as e:
            # logga l’errore e tutta la risposta 'data'
            _LOGGER.warning("⚠️ Parsing fallito (Modo Impianto): %s — response 📦: %s", e, json.dumps(data)[:300])
            _LOGGER.debug("📦 Contenuto data (Modo Impianto): %s", data)

    def fetch_season_mode(self):
        data = self._make_request(self._metric_url("Modo Stagione"))
        if not data:
            return
        try:
            item = data["data"][0]
            raw = item["values"][0]["value"]
            mapping = {
                "0001": "Inverno",
                "0002": "Estate",
                "0003": "Estate/Inverno automatico",
                "0004": "Estate/Inverno remoto",
            }
            # salva la stringa leggibile (o il codice se non è previsto)
            self.season_mode = mapping.get(raw, f"Sconosciuto ({raw})")
            self.season_mode_timestamp = item["timestamp"]
            _LOGGER.info("❄️️ Season Mode: %s", self.season_mode)
        except (KeyError, IndexError, ValueError) as e:
            # logga l’errore e tutta la risposta 'data'
            _LOGGER.warning("⚠️ Parsing fallito (Modo Stagione): %s — response 📦: %s", e, json.dumps(data)[:300])
            _LOGGER.debug("📦 Contenuto data (Modo Stagione): %s", data)







