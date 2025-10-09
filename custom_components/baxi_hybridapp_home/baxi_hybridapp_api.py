import requests
import json
from datetime import datetime, time, timedelta
import logging
import pytz
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
        self.system_icon = None
        self.system_icon_timestamp = None
        self.season_mode = None
        self.season_mode_timestamp = None
        self.flame_status = None
        self.flame_status_timestamp = None
        self.sanitary_scheduler_raw = None           # JSON string proveniente dall’API
        self.sanitary_mode_now = None                # "Comfort" | "Eco"
        self.sanitary_next_change = None             # datetime (tz-aware) del prossimo cambio
        self.sanitary_today_summary = None           # "Comfort fino alle HH:MM" | "Eco fino alle HH:MM"
        self.sanitary_scheduler_status = None        # "ok" | "empty" | "error"
        self.setpoint_eco_fallback = None           # int/str se presente nel fallback ECO

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
            # Azzera il campo, warning + debug 'data'
            self.temp_ext = None
            self.temp_ext_timestamp = None
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
            # Azzera il campo, warning + debug 'data'
            self.temp_int = None
            self.temp_int_timestamp = None
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
            # Azzera il campo, warning + debug 'data'
            self.water_pressure = None
            self.water_pressure_timestamp = None
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
            # Azzera il campo, warning + debug 'data'
            self.sanitary_on = None
            self.sanitary_on_timestamp = None
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
            # Azzera il campo, warning + debug 'data'
            self.boiler_flow_temp = None
            self.boiler_flow_temp_timestamp = None
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
            # Azzera il campo, warning + debug 'data'
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
            # Azzera il campo, warning + debug 'data'
            self.dhw_aux_storage_temp = None
            self.dhw_aux_storage_temp_timestamp = None
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
            # Azzera il campo, warning + debug 'data'
            self.pdc_exit_temp = None
            self.pdc_exit_temp_timestamp = None
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
            # Azzera il campo, warning + debug 'data'
            self.pdc_return_temp = None
            self.pdc_return_temp_timestamp = None
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
            # Azzera il campo, warning + debug 'data'
            self.setpoint_instant_temp = None
            self.setpoint_instant_temp_timestamp = None
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
            # Azzera il campo, warning + debug 'data'
            self.setpoint_comfort_temp = None
            self.setpoint_comfort_temp_timestamp = None
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
            # Azzera il campo, warning + debug 'data'
            self.setpoint_eco_temp = None
            self.setpoint_eco_temp_timestamp = None
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
            # Azzera il campo, warning + debug 'data'
            self.system_mode = None
            self.system_mode_timestamp = None
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
            # Azzera il campo, warning + debug 'data'
            self.season_mode = None
            self.season_mode_timestamp = None
            _LOGGER.warning("⚠️ Parsing fallito (Modo Stagione): %s — response 📦: %s", e, json.dumps(data)[:300])
            _LOGGER.debug("📦 Contenuto data (Modo Stagione): %s", data)

    def fetch_flame_status(self):
        data = self._make_request(self._metric_url("Flame status"))
        if not data:
            return
        try:
            item = data["data"][0]
            raw = str(item["values"][0]["value"]).strip().lower()
            mapping = {
                "0": "Off", "1": "On",
                "false": "Off", "true": "On"
            }
            self.flame_status = mapping.get(raw, f"Sconosciuto ({raw})")
            self.flame_status_timestamp = item["timestamp"]
            _LOGGER.info("🔥 Flame status: %s (raw=%s)", self.flame_status, raw)
        except (KeyError, IndexError, ValueError) as e:
            # Azzera il campo, warning + debug 'data'
            self.flame_status = None
            self.flame_status_timestamp = None
            _LOGGER.warning("⚠️ Parsing fallito (Flame status): %s — response 📦: %s", e, json.dumps(data)[:300])
            _LOGGER.debug("📦 Contenuto data (Flame status): %s", data)

    def fetch_sanitary_scheduler(self):
        data = self._make_request(self._metric_url("Schedulatore - Sanitario"))
        if not data:
            self.sanitary_scheduler_status = "error"
            return
        try:
            item = data["data"][0]
            raw_str = item["values"][0]["value"]  # è una stringa JSON
            self.sanitary_scheduler_raw = raw_str
            self._compute_sanitary_schedule_state(raw_str)
            self.sanitary_scheduler_status = "ok"
        except (KeyError, IndexError, ValueError, TypeError) as e:
            # Azzera il campo, warning + debug 'data'
            self.sanitary_scheduler_raw = None
            self.sanitary_scheduler_status = "error"
            _LOGGER.warning("⚠️ Parsing fallito (Schedulatore sanitario): %s — response 📦: %s", e, json.dumps(data)[:300])
            _LOGGER.debug("📦 Contenuto data (Schedulatore sanitario): %s", data)
    
    def _compute_sanitary_schedule_state(self, raw_str, now_dt: datetime | None = None):
        """
        Converte lo scheduler in segmenti giornalieri e calcola:
          - modalità attuale (Comfort/Eco)
          - prossimo cambio
          - riepilogo 'oggi: Comfort fino alle HH:MM' / 'Eco fino alle HH:MM'
        Assume che gli intervalli con start/end siano Comfort.
        Il resto del tempo (start=null) è Eco, da cui estraiamo eventuale setpoint eco.
        """
        # Timezone: Europa/Roma (puoi cambiarla se preferisci leggere quella di HA)
        tz = pytz.timezone("Europe/Rome")
        now_dt = now_dt.astimezone(tz) if now_dt else datetime.now(tz)

        j = json.loads(raw_str) if isinstance(raw_str, str) else raw_str

        # Mappatura weekday python (0=lun .. 6=dom) -> chiavi italiane Baxi
        day_keys = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
        today_key = day_keys[now_dt.weekday()]
        tomorrow_key = day_keys[(now_dt.weekday() + 1) % 7]

        def parse_hhmm(s: str) -> time:
            hh, mm = s.split(":")
            return time(int(hh), int(mm))

        def build_segments_for_day(day_key: str):
            """
            Costruisce segmenti ordinati per il giorno:
            - lista di dict: { 'start': datetime, 'end': datetime, 'mode': 'Comfort'|'Eco' }
            Copre 00:00 → 24:00. Comfort dagli intervalli espliciti; Eco il resto.
            Estrae setpoint eco dal blocco params con start=null.
            """
            items = j.get(day_key, []) or []
            # comfort blocks (start/end valorizzati)
            comfort_ranges = []
            eco_setpoint_local = None

            for it in items:
                s = it.get("start")
                e = it.get("end")
                params = it.get("params") or {}
                if s and e:
                    comfort_ranges.append((parse_hhmm(s), parse_hhmm(e)))
                else:
                    # fallback eco per il resto
                    eco_sp = params.get("Set-point sanitario eco")
                    if eco_sp is not None:
                        eco_setpoint_local = eco_sp

            # ordina i comfort per ora di inizio
            comfort_ranges.sort(key=lambda t: t[0])

            # costruisci segmenti pieni 00:00-24:00
            day_date = now_dt.date()  # useremo solo l'orario; la data non importa per "oggi"
            start_cursor = datetime.combine(day_date, time(0, 0), tz)

            segments = []
            for (c_start_t, c_end_t) in comfort_ranges:
                c_start = datetime.combine(day_date, c_start_t, tz)
                c_end = datetime.combine(day_date, c_end_t, tz)
                # eco prima della fascia comfort (se c'è gap)
                if c_start > start_cursor:
                    segments.append({"start": start_cursor, "end": c_start, "mode": "Eco"})
                # comfort
                if c_end > c_start:
                    segments.append({"start": c_start, "end": c_end, "mode": "Comfort"})
                start_cursor = max(start_cursor, c_end)
            # coda Eco fino a 24:00
            end_of_day = datetime.combine(day_date, time(23, 59, 59), tz) + timedelta(seconds=1)
            if start_cursor < end_of_day:
                segments.append({"start": start_cursor, "end": end_of_day, "mode": "Eco"})

            return segments, eco_setpoint_local

        # Costruisci i segmenti di oggi e domani
        today_segments, eco_sp_today = build_segments_for_day(today_key)
        tomorrow_segments, eco_sp_tom = build_segments_for_day(tomorrow_key)

        # scegli eco setpoint se presente
        self.sanitary_eco_setpoint = eco_sp_today if eco_sp_today is not None else eco_sp_tom

        # trova il segmento corrente e il prossimo cambio
        def find_current_and_next(segments, ref_dt: datetime):
            cur = None
            nxt = None
            for seg in segments:
                if seg["start"] <= ref_dt < seg["end"]:
                    cur = seg
                    # prossimo cambio è la fine del segmento corrente (se < 24:00)
                    if seg["end"] > ref_dt:
                        nxt = seg["end"]
                    break
            # se non trovato (edge case), prossimo è il primo segmento del giorno successivo
            return cur, nxt

        cur_seg, next_change = find_current_and_next(today_segments, now_dt)
        if cur_seg is None:
            # fuori range? fallback: prendi il primo di domani
            self.sanitary_mode_now = None
            self.sanitary_next_change = tomorrow_segments[0]["start"] if tomorrow_segments else None
            self.sanitary_today_summary = "N/D"
            return

        # Modalità attuale
        self.sanitary_mode_now = cur_seg["mode"]

        # Prossimo cambio: se non c’è più oggi, prendi il primo di domani
        if not next_change:
            self.sanitary_next_change = tomorrow_segments[0]["start"] if tomorrow_segments else None
        else:
            self.sanitary_next_change = next_change

        # Riepilogo “oggi … fino alle HH:MM”
        until_dt = self.sanitary_next_change
        # se il prossimo cambio è domani, il riepilogo di oggi va fino alle 24:00
        if until_dt and until_dt.date() != now_dt.date():
            until_txt = "24:00"
        else:
            until_txt = until_dt.strftime("%H:%M") if until_dt else "24:00"

        self.sanitary_today_summary = f"{self.sanitary_mode_now} fino alle {until_txt}"





    # API di scrittura (PUT)
    def set_configuration_parameter(self, parameter_id: str, value: float | int | str):
        """
        Esegue una chiamata PUT per aggiornare un parametro configurabile
        (es. setpoint eco, comfort, ecc.)
        """
        if not self.token:
            _LOGGER.warning("⚠️ Nessun token, provo a ri-autenticare...")
            self.authenticate()
            if not self.token:
                _LOGGER.error("❌ Impossibile autenticarsi per PUT.")
                return False

        if not self.thingId:
            _LOGGER.warning("⚠️ Nessun thingId, provo a recuperarlo...")
            self.get_thingid()
            if not self.thingId:
                _LOGGER.error("❌ Impossibile ottenere il thingId per PUT.")
                return False

        url = f"{self.BASE_URL}/data/configurationParameters?thingId={self.thingId}"

        payload = json.dumps([
            {
                "parameterId": parameter_id,
                "value": value,
                "content": ""
            }
        ])

        headers = {
            'x-semioty-tenant': TENANT,
            'authorization': f'Bearer {self.token}',
            'content-type': 'application/json',
            'user-agent': DEV_BROWSER,
            'x-requested-with': 'it.baxi.HybridApp'
        }

        try:
            response = requests.put(url, headers=headers, data=payload, timeout=15)
            if response.status_code == 401:
                _LOGGER.warning("🔐 Token scaduto, ri-autentico...")
                self.authenticate()
                headers['authorization'] = f'Bearer {self.token}'
                response = requests.put(url, headers=headers, data=payload, timeout=15)

            if response.ok:
                _LOGGER.info("✅ PUT parametro %s impostato a %s", parameter_id, value)
                return True
            else:
                _LOGGER.error("❌ Errore PUT parametro %s → %s", parameter_id, response.text)
                return False
        except Exception as e:
            _LOGGER.exception("❌ Eccezione nella PUT parametro %s: %s", parameter_id, e)
            return False















