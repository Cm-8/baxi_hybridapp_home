"""
API client for Baxi Hybrid App custom integration for Home Assistant.

custom_components/baxi_hybridapp_home/api.py
"""

import re
import requests
import json
from datetime import datetime, time, timedelta
from time import sleep as _sleep
from homeassistant.util import dt as dt_util
import logging
from zoneinfo import ZoneInfo
from urllib.parse import quote_plus
from .const import (
    APIKEY, TENANT, DEV_BROWSER,
    DEV_MODEL, DEV_ID, PLATFORM,
)
from .metrics import SIMPLE_METRICS, SimpleMetricSpec, ENERGY_SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)


class BaxiHybridAppAPI:
    BASE_URL = "https://baxi.servitly.com/api"
    LOGIN_URL = BASE_URL + "/identity/users/login?apiKey=" + APIKEY
    THINGS_URL = BASE_URL + "/v2/identity/users/me/things"
    # Endpoint user-level (NON per-thing): ritorna gli alert di tutti i device
    # dell'account. Filtriamo per self.thingId in fetch_historical_alerts.
    ALERTS_URL = BASE_URL + (
        "/identity/users/me/historicalAlerts"
        "?field=severity&field=date&field=customer.name&field=location.name"
        "&field=thing.serialNumber&field=title&field=description&field=duration"
    )

    # Tetto massimo al delay accettato da Retry-After (429). Oltre questo valore
    # rinunciamo per non bloccare a lungo il thread executor: meglio saltare il
    # ciclo e ritentare al prossimo refresh del coordinator.
    MAX_RETRY_AFTER_SECONDS = 30
    REQUEST_TIMEOUT = 15

    def __init__(self, username, password):
        self.username = username
        self.password = password
        # Sessione HTTP riusabile: una sola coppia TCP+TLS handshake invece di
        # una per ogni metrica. Gli header comuni vivono qui, niente ripetizioni.
        self._session = requests.Session()
        self._session.headers.update({
            'x-semioty-tenant': TENANT,
            'user-agent': DEV_BROWSER,
            'x-requested-with': 'it.baxi.HybridApp',
        })
        self.token = None
        self.refreshToken = None
        self.thingId = None
        self.thingModel = None
        self.thingSwVersion = None
        self.thingFirmware = None
        self.serialNumber = None
        self.thingDefinitionId = None    # ID del modello (thingDefinition), non del device
        self.thingDefinitionName = None  # Nome commerciale del modello (es. "CSI IN SPLIT E")

        # Metriche "semplici": un attributo + timestamp per ciascuna voce della
        # tabella SIMPLE_METRICS (definita a livello modulo). Aggiungerne una
        # NON richiede modifiche qui.
        for spec in SIMPLE_METRICS:
            setattr(self, spec.attr, None)
            setattr(self, f"{spec.attr}_timestamp", None)

        # Scheduler sanitario: parsing JSON con logica derivata custom
        # (vedi fetch_sanitary_scheduler / _compute_sanitary_schedule_state).
        self.sanitary_scheduler_raw = None           # JSON string proveniente dall'API
        self.sanitary_mode_now = None                # "Comfort" | "Eco"
        self.sanitary_next_change = None             # datetime (tz-aware) del prossimo cambio
        self.sanitary_today_summary = None           # "Comfort fino alle HH:MM" | "Eco fino alle HH:MM"
        self.sanitary_scheduler_status = None        # "ok" | "empty" | "error"
        self.setpoint_eco_fallback = None            # int/str se presente nel fallback ECO

        # Sensori energia: tabellari via ENERGY_SENSOR_TYPES in const.py.
        for desc in ENERGY_SENSOR_TYPES:
            setattr(self, desc.key, None)
        self.energy_timestamp = {}

        # Historical alerts: tracking FAILURE/WARNING + event sul bus HA.
        # active_*  → alert ancora aperto (endTimestamp==0 o >= now). Pilota i binary_sensor.
        # last_*    → ultimo alert (anche risolto) per severity. Per attributi dashboard.
        # *_count_* → conteggio aggregato per dashboard.
        self.active_failure_alert = None
        self.active_warning_alert = None
        self.last_failure_alert = None
        self.last_warning_alert = None
        self.failure_count_24h = None
        self.failure_count_7d = None
        self.warning_count_24h = None
        self.warning_count_7d = None
        # Dedup degli event SOLO in RAM (sopravvive ai polling, non al restart HA).
        # Al primo fetch post-startup si fa seed senza firing → niente notifiche
        # spam al riavvio per alert già attivi prima del restart.
        self._seen_alert_ids: set[str] = set()
        self._alerts_initialized = False
        # Coda dei "nuovi" alert dell'ultimo fetch: il coordinator la consuma
        # nell'event loop per fire event + log su Logbook.
        self.new_alerts_pending: list[dict] = []

    def authenticate(self):
        payload = json.dumps({
            "email": self.username,
            "password": self.password,
            "devices": [{
                "deviceId": DEV_ID,
                "model": DEV_MODEL,
                "platform": PLATFORM,
                "platformVersion": "12",
                "browser": DEV_BROWSER,
                "notificationDeviceId": "dummy"
            }]
        })

        # Solo header specifico della login: gli altri sono già sulla session.
        headers = {'content-type': 'application/json'}

        try:
            response = self._session.post(
                self.LOGIN_URL,
                headers=headers,
                data=payload,
                timeout=self.REQUEST_TIMEOUT,
            )
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
                
        # Solo l'authorization è specifica per la chiamata; il resto sta sulla session.
        headers = {'authorization': f'Bearer {self.token}'}

        try:
            response = self._session.get(
                self.THINGS_URL,
                headers=headers,
                timeout=self.REQUEST_TIMEOUT,
            )
            if response.ok:
                data = response.json()
                content = data.get("content", [])
                
                thing = content[0] if content else {}
                thing_def = thing.get("thingDefinition") or {}

                self.thingId              = thing.get("id")
                self.thingModel           = thing.get("properties", {}).get("model")
                self.thingSwVersion       = thing.get("properties", {}).get("versione_software_msc")
                self.thingFirmware        = thing.get("properties", {}).get("firmware")
                self.serialNumber         = thing.get("serialNumber")
                self.thingDefinitionId    = thing_def.get("id")
                self.thingDefinitionName  = thing_def.get("name")

                _LOGGER.info("✅ Thing ID ottenuto: %s", self.thingId)
                _LOGGER.info("✅ Model ottenuto: %s | Definizione: %s (%s)",
                             self.thingModel, self.thingDefinitionName, self.thingDefinitionId)
                _LOGGER.info("✅ SwVersion: %s | Firmware: %s | S/N: %s",
                             self.thingSwVersion, self.thingFirmware, self.serialNumber)

                return self.thingId
            else:
                _LOGGER.error("❌ Questo Account Baxi non ha un impianto(ThingId) associato: %s", response.text)
                return None
        except Exception as e:
            _LOGGER.exception("❌ Eccezione nel recupero thingId: %s", e)
            return None

    def _auth_headers(self) -> dict:
        """Header per le chiamate autenticate (gli altri stanno sulla session)."""
        return {'authorization': f'Bearer {self.token}'} if self.token else {}

    def _parse_retry_after(self, response) -> int | None:
        """
        Estrae il delay (in secondi) dall'header Retry-After di una risposta 429.
        Ritorna None se mancante, non parsabile, ≤0 o oltre MAX_RETRY_AFTER_SECONDS.
        Gestiamo solo il formato "secondi" (numero); l'eventuale HTTP-date viene saltato:
        servitly indica un bucket per minuto, quindi è ragionevole.
        """
        ra = response.headers.get('Retry-After')
        if not ra:
            return None
        try:
            secs = int(float(ra))
        except (TypeError, ValueError):
            return None
        if secs <= 0:
            return None
        if secs > self.MAX_RETRY_AFTER_SECONDS:
            _LOGGER.warning(
                "⏳ Retry-After=%ss > tetto %ss: rinuncio per questo ciclo.",
                secs, self.MAX_RETRY_AFTER_SECONDS,
            )
            return None
        return secs

    def _make_request(self, url: str):
        """
        GET autenticata con gestione centralizzata di:
        - token mancante / 401  → ri-autentica e ritenta una volta
        - 429 (rate limit)      → onora Retry-After ≤ MAX_RETRY_AFTER_SECONDS e ritenta una volta
        Riusa la sessione HTTP della classe (keep-alive, no TLS handshake ripetuto).
        """
        if not self.token:
            _LOGGER.warning("⚠️ Nessun token: provo a ri-autenticare.")
            self.authenticate()
            if not self.token:
                _LOGGER.error("❌ Impossibile autenticarsi.")
                return None

        try:
            response = self._session.get(
                url, headers=self._auth_headers(), timeout=self.REQUEST_TIMEOUT,
            )

            # 401: token scaduto → ri-autentica e ritenta una sola volta
            if response.status_code == 401:
                _LOGGER.warning("🔐 Token scaduto, riprovo autenticazione...")
                self.authenticate()
                response = self._session.get(
                    url, headers=self._auth_headers(), timeout=self.REQUEST_TIMEOUT,
                )

            # 429: rate limit → backoff via Retry-After e ritenta una sola volta
            if response.status_code == 429:
                delay = self._parse_retry_after(response)
                if delay is not None:
                    _LOGGER.warning(
                        "⏳ Rate limit (429) su %s, attendo %ss e riprovo.",
                        url, delay,
                    )
                    _sleep(delay)
                    response = self._session.get(
                        url, headers=self._auth_headers(), timeout=self.REQUEST_TIMEOUT,
                    )
                else:
                    _LOGGER.warning(
                        "⏳ Rate limit (429) su %s senza Retry-After utile — salto.",
                        url,
                    )
                    return None

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

    # Sentinelle "no data" pubblicate da Servitly: il valore esiste ma la misura
    # è assente (tipico per metriche non applicabili al device, es. flame status
    # su impianto solo elettrico — issue #6).
    _NO_DATA_SENTINELS = frozenset({"---", ""})

    # ---------------- Dispatcher metriche semplici ----------------
    def _fetch_one(self, spec: SimpleMetricSpec) -> None:
        """
        Legge una singola metrica e memorizza valore + timestamp.

        Casi gestiti (issue #6 — Baxi solo elettrica / metriche non applicabili
        al device):
          - data["data"] == []          → attributo None, log debug (NON è errore)
          - value in _NO_DATA_SENTINELS → attributo None, log debug
          - parsing fail 'vero'         → attributo None, log warning + estratto JSON
        In tutti i casi l'attributo viene azzerato: l'entità HA risulta unavailable.
        """
        data = self._make_request(self._metric_url(spec.metric_name))
        if not data:
            return

        # Caso 1: la metrica non è esposta dal device → "data" è un array vuoto.
        items = data.get("data") or []
        if not items:
            setattr(self, spec.attr, None)
            setattr(self, f"{spec.attr}_timestamp", None)
            _LOGGER.debug(
                "ℹ️ %s non disponibile su questo device (data vuoto)",
                spec.metric_name,
            )
            return

        try:
            item = items[0]
            raw = item["values"][0]["value"]

            # Caso 2: metrica esposta ma senza misura corrente (sentinella).
            if isinstance(raw, str) and raw.strip() in self._NO_DATA_SENTINELS:
                setattr(self, spec.attr, None)
                setattr(self, f"{spec.attr}_timestamp", None)
                _LOGGER.debug(
                    "ℹ️ %s = '%s' (sentinella no-data, ignorata)",
                    spec.metric_name, raw,
                )
                return

            value = spec.parser(raw)
            setattr(self, spec.attr, value)
            setattr(self, f"{spec.attr}_timestamp", item["timestamp"])
            _LOGGER.debug("%s %s = %s", spec.log_emoji, spec.metric_name, value)
        except (KeyError, IndexError, ValueError, TypeError) as e:
            setattr(self, spec.attr, None)
            setattr(self, f"{spec.attr}_timestamp", None)
            _LOGGER.warning(
                "⚠️ Parsing fallito (%s): %s — response: %s",
                spec.metric_name, e, json.dumps(data)[:300],
            )

    def fetch_simple_metrics(self) -> None:
        """Legge in sequenza tutte le metriche definite in SIMPLE_METRICS."""
        for spec in SIMPLE_METRICS:
            self._fetch_one(spec)

    # ----- I vecchi fetch_<metrica> per-attributo sono stati collassati in -----
    # fetch_simple_metrics() + SIMPLE_METRICS (dispatcher tabellare, vedi sopra).
    # Restano qui sotto solo i fetch con logica non-banale: energia e scheduler.

    # 🔴 Sensori energia
    def fetch_energy_metrics(self):
        """
        Legge tutte le metriche energia definite in ENERGY_SENSOR_TYPES.
        Salva i valori su self.<key> e (opzionale) i timestamp su self.energy_timestamp[key].
        """
        for desc in ENERGY_SENSOR_TYPES:
            try:
                data = self._make_request(self._metric_url(desc.metric_name))
                if not data:
                    setattr(self, desc.key, None)
                    self.energy_timestamp[desc.key] = None
                    continue

                item = data["data"][0]
                raw_val = item["values"][0]["value"]
                ts = item.get("timestamp")

                # prova a convertire in float (Servitly spesso manda stringhe)
                try:
                    val = float(str(raw_val).replace(",", "."))
                except (TypeError, ValueError):
                    val = None

                # ✅ WORKAROUND SOLO per "energia_totale_globale_day"
                if val is not None and ts and desc.key == "energia_totale_globale_day":
                    sample_local_date = datetime.fromtimestamp(
                        ts / 1000, tz=dt_util.DEFAULT_TIME_ZONE
                    ).date()
                    today_local_date = dt_util.now().date()
                
                    # Se il campione non è di oggi, forza 0 finché non arriva il nuovo giorno
                    if sample_local_date != today_local_date:
                        val = 0.0

                setattr(self, desc.key, val)
                self.energy_timestamp[desc.key] = ts

                _LOGGER.debug("⚡ %s = %s kWh", desc.metric_name, val)

            except (KeyError, IndexError, TypeError) as e:
                setattr(self, desc.key, None)
                self.energy_timestamp[desc.key] = None
                _LOGGER.warning(
                    "⚠️ Parsing fallito (energia: %s): %s — response 📦: %s",
                    desc.metric_name, e, json.dumps(data)[:300] if 'data' in locals() and data else "None"
                )


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
            _LOGGER.debug("📅 Schedulatore Sanitario: %s", self.sanitary_scheduler_raw)
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
        tz = ZoneInfo("Europe/Rome")
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
            start_cursor = datetime.combine(day_date, time(0, 0), tzinfo=tz)

            segments = []
            for (c_start_t, c_end_t) in comfort_ranges:
                c_start = datetime.combine(day_date, c_start_t, tzinfo=tz)
                c_end = datetime.combine(day_date, c_end_t, tzinfo=tz)
                # eco prima della fascia comfort (se c'è gap)
                if c_start > start_cursor:
                    segments.append({"start": start_cursor, "end": c_start, "mode": "Eco"})
                # comfort
                if c_end > c_start:
                    segments.append({"start": c_start, "end": c_end, "mode": "Comfort"})
                start_cursor = max(start_cursor, c_end)
            # coda Eco fino a 24:00
            end_of_day = datetime.combine(day_date, time(23, 59, 59), tzinfo=tz) + timedelta(seconds=1)
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





    # 🚨 Historical alerts (user-level): FAILURE + WARNING
    # Regex per estrarre il codice errore dalla description ("E60", "E14", ...).
    _ALERT_CODE_RE = re.compile(r"\bE\d{1,3}\b")

    def _normalize_alert(self, a: dict) -> dict:
        """Estrae i campi utili da un alert grezzo + prova a leggere il codice errore."""
        desc = a.get("description") or ""
        m = self._ALERT_CODE_RE.search(desc)
        code = m.group(0) if m else None
        if not code and "OFFLINE" in desc.upper():
            code = "OFFLINE"
        return {
            "id": a.get("id"),
            "severity": a.get("severity"),
            "title": a.get("title"),
            "description": desc,
            "code": code,
            "start_ts": a.get("startTimestamp"),
            "end_ts": a.get("endTimestamp"),
        }

    def fetch_historical_alerts(self) -> None:
        """
        Legge gli alert storici user-level e popola:
          - active_failure_alert / active_warning_alert (alert aperto, se c'è)
          - last_failure_alert / last_warning_alert (ultimo per severity, anche risolto)
          - failure_count_24h / failure_count_7d (per dashboard)
          - warning_count_24h / warning_count_7d
          - new_alerts_pending → consumata dal coordinator per fire event + Logbook

        Dedup degli event in RAM: al primo fetch della sessione si fa solo
        seed di _seen_alert_ids (niente firing → niente notifiche al riavvio HA).
        Dai fetch successivi, gli id mai visti generano event.
        """
        self.new_alerts_pending = []
        data = self._make_request(self.ALERTS_URL)
        if not data:
            return
        try:
            alerts = data.get("historicalAlerts", []) or []
            # Filtra per il thing dell'utente (se più di un device sull'account).
            if self.thingId:
                alerts = [
                    a for a in alerts
                    if (a.get("thing") or {}).get("id") == self.thingId
                ]

            now_ms = int(dt_util.utcnow().timestamp() * 1000)
            ms_24h = 24 * 3600 * 1000
            ms_7d = 7 * ms_24h

            current_ids = {a["id"] for a in alerts if a.get("id")}
            if not self._alerts_initialized:
                self._seen_alert_ids = current_ids
                self._alerts_initialized = True
                _LOGGER.info(
                    "🚨 Alerts: seeding iniziale (%d alert già visti, niente firing)",
                    len(current_ids),
                )
            else:
                new_ids = current_ids - self._seen_alert_ids
                self._seen_alert_ids = current_ids
                self.new_alerts_pending = [
                    self._normalize_alert(a) for a in alerts
                    if a.get("id") in new_ids
                ]

            active_failure = None
            active_warning = None
            last_failure = None
            last_warning = None
            failure_24h = 0
            failure_7d = 0
            warning_24h = 0
            warning_7d = 0

            for a in alerts:
                sev = a.get("severity")
                start = a.get("startTimestamp") or 0
                end = a.get("endTimestamp") or 0
                is_active = (end == 0 or end >= now_ms)
                in_24h = bool(start) and (now_ms - start) <= ms_24h
                in_7d = bool(start) and (now_ms - start) <= ms_7d

                if sev == "FAILURE":
                    if is_active and active_failure is None:
                        active_failure = a
                    if last_failure is None or start > (last_failure.get("startTimestamp") or 0):
                        last_failure = a
                    if in_24h:
                        failure_24h += 1
                    if in_7d:
                        failure_7d += 1
                elif sev == "WARNING":
                    if is_active and active_warning is None:
                        active_warning = a
                    if last_warning is None or start > (last_warning.get("startTimestamp") or 0):
                        last_warning = a
                    if in_24h:
                        warning_24h += 1
                    if in_7d:
                        warning_7d += 1

            self.active_failure_alert = self._normalize_alert(active_failure) if active_failure else None
            self.active_warning_alert = self._normalize_alert(active_warning) if active_warning else None
            self.last_failure_alert = self._normalize_alert(last_failure) if last_failure else None
            self.last_warning_alert = self._normalize_alert(last_warning) if last_warning else None
            self.failure_count_24h = failure_24h
            self.failure_count_7d = failure_7d
            self.warning_count_24h = warning_24h
            self.warning_count_7d = warning_7d

            _LOGGER.info(
                "🚨 Alerts: FAILURE attivo=%s, WARNING attivo=%s, FAILURE 24h=%d, 7g=%d, nuovi=%d",
                "sì" if active_failure else "no",
                "sì" if active_warning else "no",
                failure_24h, failure_7d, len(self.new_alerts_pending),
            )
        except (KeyError, IndexError, ValueError, TypeError) as e:
            _LOGGER.warning(
                "⚠️ Parsing fallito (historicalAlerts): %s — response: %s",
                e, json.dumps(data)[:300],
            )

    # 🔴🔴 API di scrittura (PUT)
    def send_command(self, command_id: str) -> bool:
        """
        Invia un comando al device tramite PUT /data/commands?commandId=...&thingId=...
        con body vuoto (HTTP 204 atteso). Usato per le modalità operative:
        Automatico, Standby, Solo Sanitario.
        """
        if not self.token:
            _LOGGER.warning("⚠️ Nessun token, provo a ri-autenticare...")
            self.authenticate()
            if not self.token:
                _LOGGER.error("❌ Impossibile autenticarsi per PUT command.")
                return False

        if not self.thingId:
            _LOGGER.warning("⚠️ Nessun thingId, provo a recuperarlo...")
            self.get_thingid()
            if not self.thingId:
                _LOGGER.error("❌ Impossibile ottenere il thingId per PUT command.")
                return False

        url = f"{self.BASE_URL}/data/commands?commandId={command_id}&thingId={self.thingId}"

        headers = {
            'authorization': f'Bearer {self.token}',
            'content-type': 'application/json',
        }

        try:
            response = self._session.put(
                url, headers=headers, data=None, timeout=self.REQUEST_TIMEOUT,
            )

            # 401: ri-autentica e ritenta una sola volta
            if response.status_code == 401:
                _LOGGER.warning("🔐 Token scaduto, ri-autentico...")
                self.authenticate()
                headers['authorization'] = f'Bearer {self.token}'
                response = self._session.put(
                    url, headers=headers, data=None, timeout=self.REQUEST_TIMEOUT,
                )

            # 429: backoff via Retry-After e ritenta una sola volta
            if response.status_code == 429:
                delay = self._parse_retry_after(response)
                if delay is not None:
                    _LOGGER.warning(
                        "⏳ Rate limit (429) su PUT command %s, attendo %ss e riprovo.",
                        command_id, delay,
                    )
                    _sleep(delay)
                    response = self._session.put(
                        url, headers=headers, data=None, timeout=self.REQUEST_TIMEOUT,
                    )
                else:
                    _LOGGER.warning(
                        "⏳ Rate limit (429) su PUT command %s senza Retry-After utile — abbandono.",
                        command_id,
                    )
                    return False

            # 204 = No Content → successo
            if response.status_code == 204 or response.ok:
                _LOGGER.info("📤✅ Comando %s eseguito (HTTP %s)", command_id, response.status_code)
                return True
            else:
                _LOGGER.error("❌ Errore PUT command %s → HTTP %s: %s", command_id, response.status_code, response.text)
                return False
        except Exception as e:
            _LOGGER.exception("❌ Eccezione nel PUT command %s: %s", command_id, e)
            return False

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

        # Header specifici della PUT: i comuni stanno sulla session.
        headers = {
            'authorization': f'Bearer {self.token}',
            'content-type': 'application/json',
        }

        try:
            response = self._session.put(
                url, headers=headers, data=payload, timeout=self.REQUEST_TIMEOUT,
            )

            # 401: ri-autentica e ritenta una sola volta
            if response.status_code == 401:
                _LOGGER.warning("🔐 Token scaduto, ri-autentico...")
                self.authenticate()
                headers['authorization'] = f'Bearer {self.token}'
                response = self._session.put(
                    url, headers=headers, data=payload, timeout=self.REQUEST_TIMEOUT,
                )

            # 429: backoff via Retry-After e ritenta una sola volta
            if response.status_code == 429:
                delay = self._parse_retry_after(response)
                if delay is not None:
                    _LOGGER.warning(
                        "⏳ Rate limit (429) su PUT %s, attendo %ss e riprovo.",
                        parameter_id, delay,
                    )
                    _sleep(delay)
                    response = self._session.put(
                        url, headers=headers, data=payload, timeout=self.REQUEST_TIMEOUT,
                    )
                else:
                    _LOGGER.warning(
                        "⏳ Rate limit (429) su PUT %s senza Retry-After utile — abbandono.",
                        parameter_id,
                    )
                    return False

            if response.ok:
                _LOGGER.info("📤✅ PUT parametro %s impostato a %s", parameter_id, value)
                return True
            else:
                _LOGGER.error("❌ Errore PUT parametro %s → %s", parameter_id, response.text)
                return False
        except Exception as e:
            _LOGGER.exception("❌ Eccezione nella PUT parametro %s: %s", parameter_id, e)
            return False

