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
from urllib.parse import parse_qs, quote_plus, urlparse
from .const import (
    APIKEY, TENANT, DEV_BROWSER,
    DEV_MODEL, DEV_ID, PLATFORM,
)
from .metrics import SIMPLE_METRICS, SimpleMetricSpec, ENERGY_SENSOR_TYPES, _parse_float

_LOGGER = logging.getLogger(__name__)

# metricName dello scheduler sanitario (parsing proprio, fuori dalle tabelle di metrics.py).
SANITARY_SCHEDULER_METRIC = "Schedulatore - Sanitario"
# Tutte le metriche lette a ogni ciclo: semplici, scheduler sanitario, energia
# (49 nomi, sotto il limite di 50 di /data/lastValues: oltre servono 2 richieste).
WIRED_METRIC_NAMES: tuple[str, ...] = tuple(dict.fromkeys(
    [spec.metric_name for spec in SIMPLE_METRICS]
    + [SANITARY_SCHEDULER_METRIC]
    + [desc.metric_name for desc in ENERGY_SENSOR_TYPES]
))
# Attributo dell'istanza API → metrica da cui dipende: le entità che lo leggono
# esistono solo se il modello ha quella metrica (vedi provides()).
METRIC_OF_ATTR: dict[str, str] = {
    **{spec.attr: spec.metric_name for spec in SIMPLE_METRICS},
    **{desc.key: desc.metric_name for desc in ENERGY_SENSOR_TYPES},
    "sanitary_mode_now": SANITARY_SCHEDULER_METRIC,
}


def _request_label(url: str) -> str:
    """Nome breve di una richiesta per i log: il metricName, se presente."""
    parsed = urlparse(url)
    names = parse_qs(parsed.query).get("metricName")
    endpoint = parsed.path.rsplit("/", 1)[-1]
    if names and len(names) > 1:
        return f"{endpoint} ({len(names)} metriche)"
    return names[0] if names else endpoint


def _mask_serial(serial) -> str:
    """Maschera un numero di serie o un identificativo (thingId, userId) per i log.

    Restano visibili le ultime 4 cifre: bastano a distinguere due impianti in
    una segnalazione senza esporre il valore completo. Valori brevi vengono
    oscurati del tutto.
    """
    if not serial:
        return "n.d."
    s = str(serial)
    if len(s) <= 4:
        return "***"
    return "***" + s[-4:]


def _mask_url(url: str) -> str:
    """URL per i log con il thingId mascherato (vedi _mask_serial)."""
    return re.sub(r"(thingId=)([^&]+)", lambda m: m.group(1) + _mask_serial(m.group(2)), url)


class BaxiApiError(Exception):
    """Errore generico dell'API Baxi Servitly."""


class BaxiAuthError(BaxiApiError):
    """Credenziali rifiutate dal cloud (login fallito)."""


class BaxiConnectionError(BaxiApiError):
    """Cloud Servitly non raggiungibile (rete, timeout, errore server)."""


class BaxiHybridAppAPI:
    BASE_URL = "https://baxi.servitly.com/api"
    LOGIN_URL = BASE_URL + "/identity/users/login?apiKey=" + APIKEY
    # Rinnovo JWT scaduto via refreshToken (Bearer = token scaduto).
    RENEW_URL = BASE_URL + "/identity/users/me/renewToken"
    LOGOUT_URL = BASE_URL + "/identity/users/me/logout"
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
    # GET /data/lastValues: massimo di metricName per richiesta, e fallimenti di
    # fila (con le letture singole che riescono) dopo cui non la si tenta più.
    LAST_VALUES_MAX_METRICS = 50
    LAST_VALUES_MAX_FAILURES = 3

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
        self.userId = None
        self.tenantId = None
        self.tokenExpirationTimestamp = None  # epoch ms, solo informativo
        # Password rifiutata da un login di ripiego (token scaduto e non
        # rinnovabile): niente altri tentativi finché un login non riesce; il
        # coordinator avvia la ri-autenticazione (vedi _request).
        self.auth_rejected = False
        self.thingId = None
        self.thingModel = None
        self.thingSwVersion = None
        self.thingFirmware = None
        self.serialNumber = None
        self.thingDefinitionId = None    # ID del modello (thingDefinition), non del device
        self.thingDefinitionName = None  # Nome commerciale del modello (es. "CSI IN SPLIT E")
        # Nomi delle metriche del modello (catalogo letto all'avvio, vedi
        # fetch_model_metrics). None = catalogo non ancora noto: si legge tutto.
        self.model_metrics: frozenset[str] | None = None
        # Catalogo completo, riusato da fetch_capabilities: è statico per
        # modello e scaricarlo di nuovo rallenta l'avvio con il debug attivo.
        self._metric_catalog: list | None = None

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
        # Esiti delle richieste di lettura del ciclo corrente (vedi _make_request).
        self.reset_request_stats()
        # Lettura multipla di tutte le metriche (vedi fetch_all_metrics).
        self._last_values_enabled = True
        self._last_values_failures = 0
        self._bulk_samples: dict[str, dict] | None = None

    def login(self):
        """Esegue il login e solleva eccezioni tipizzate.

        Usato dal config flow per validare le credenziali (test-before-configure):
        - BaxiAuthError       → credenziali non valide (400/401/403 o token assente)
        - BaxiConnectionError → cloud non raggiungibile (rete, timeout, 5xx)
        Il runtime del coordinator usa invece authenticate(), che non solleva.
        """
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
        except requests.exceptions.RequestException as e:
            raise BaxiConnectionError(f"Cloud Baxi non raggiungibile: {e}") from e

        if response.status_code in (400, 401, 403):
            raise BaxiAuthError(f"Credenziali rifiutate (HTTP {response.status_code})")
        if not response.ok:
            raise BaxiConnectionError(f"Errore server Baxi (HTTP {response.status_code})")

        data = response.json()
        token = data.get("token")
        if not token:
            # 200 senza token: risposta anomala, trattata come auth fallita
            raise BaxiAuthError("Login senza token nella risposta")

        self.token = token
        self.auth_rejected = False
        self.refreshToken = data.get("refreshToken")
        self.userId = data.get("userId")
        self.tenantId = data.get("tenantId")
        self.tokenExpirationTimestamp = data.get("tokenExpirationTimestamp")
        # Token oscurati, userId mascherato come il numero di serie.
        safe = {**data, "token": "***", "refreshToken": "***", "userId": _mask_serial(self.userId)}
        _LOGGER.info("✅ BAXI Login successful: %s", json.dumps(safe)[:300])

    def authenticate(self):
        """Wrapper tollerante di login(): logga senza sollevare.

        Mantiene il contratto storico del runtime (coordinator/retry 401):
        in caso di errore self.token resta None e il chiamante gestisce.
        """
        try:
            self.login()
        except BaxiAuthError as e:
            # Credenziali rifiutate: invalida il token stantio, così il prossimo
            # ciclo del coordinator ripassa da login() e propaga l'errore tipizzato
            # (→ ConfigEntryAuthFailed → re-auth flow), invece di insistere con
            # un token morto. auth_rejected ferma gli altri login del ciclo.
            self.token = None
            self.refreshToken = None
            self.auth_rejected = True
            _LOGGER.error("❌ BAXI Login failed: %s", e)
        except BaxiApiError as e:
            _LOGGER.error("❌ BAXI Login failed: %s", e)
        except Exception as e:
            _LOGGER.exception("❌ BAXI Login exception: %s", e)

    def renew_token(self) -> bool:
        """Rinnova il JWT scaduto usando il refreshToken (niente password).

        POST /identity/users/me/renewToken con Bearer = token scaduto e body
        {refreshToken, userId, tenantId}. Servitly consente il rinnovo solo a
        JWT scaduto, quindi va chiamato in risposta a un 401.
        Ritorna True se il token è stato rinnovato; non solleva.
        """
        if not (self.token and self.refreshToken and self.userId and self.tenantId):
            return False

        payload = json.dumps({
            "refreshToken": self.refreshToken,
            "userId": self.userId,
            "tenantId": self.tenantId,
        })
        headers = {
            'authorization': f'Bearer {self.token}',
            'accept': 'application/json',
            'content-type': 'application/json',
        }

        try:
            response = self._session.post(
                self.RENEW_URL, headers=headers, data=payload,
                timeout=self.REQUEST_TIMEOUT,
            )
        except requests.exceptions.RequestException as e:
            _LOGGER.warning("⚠️ Rinnovo token non riuscito (rete): %s", e)
            return False

        if not response.ok:
            _LOGGER.warning("⚠️ Rinnovo token rifiutato (HTTP %s)", response.status_code)
            return False

        try:
            data = response.json()
        except ValueError:
            _LOGGER.warning("⚠️ Rinnovo token: risposta non JSON")
            return False

        token = data.get("token") if isinstance(data, dict) else None
        if not token:
            _LOGGER.warning("⚠️ Rinnovo token: nessun token nella risposta")
            return False

        self.token = token
        # Se il cloud ruota il refreshToken lo aggiorniamo, altrimenti teniamo il vecchio.
        self.refreshToken = data.get("refreshToken") or self.refreshToken
        self.tokenExpirationTimestamp = data.get("tokenExpirationTimestamp")
        _LOGGER.info("🔄 BAXI token rinnovato via refreshToken")
        return True

    def _reauthenticate(self) -> None:
        """Dopo un 401: prova il renewToken, se fallisce ripiega sul login completo."""
        if self.renew_token():
            return
        _LOGGER.warning("🔐 Rinnovo token non disponibile, eseguo login completo...")
        self.authenticate()

    def logout(self) -> None:
        """Chiude la sessione lato cloud invalidando il refreshToken (best-effort).

        Chiamato all'unload dell'integrazione e dopo le login di sola validazione
        del config flow, per non lasciare sessioni orfane sull'account. Non solleva.
        """
        if self.token and self.refreshToken:
            try:
                response = self._session.post(
                    self.LOGOUT_URL,
                    headers={
                        'authorization': f'Bearer {self.token}',
                        'content-type': 'application/json',
                    },
                    data=json.dumps({"refreshToken": self.refreshToken}),
                    timeout=self.REQUEST_TIMEOUT,
                )
                _LOGGER.debug("👋 BAXI logout (HTTP %s)", response.status_code)
            except requests.exceptions.RequestException as e:
                _LOGGER.debug("👋 BAXI logout non riuscito: %s", e)
        self.token = None
        self.refreshToken = None

    def close(self) -> None:
        """Logout dal cloud e chiusura della sessione HTTP (unload / fine validazione)."""
        self.logout()
        self._session.close()

    def get_thingid (self) -> str:
        response = self._request("GET", self.THINGS_URL)
        if response is None:
            return None

        try:
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

                _LOGGER.info("✅ Thing ID ottenuto: %s", _mask_serial(self.thingId))
                _LOGGER.info("✅ Model ottenuto: %s | Definizione: %s (%s)",
                             self.thingModel, self.thingDefinitionName, self.thingDefinitionId)
                # S/N mascherato: i log finiscono spesso nelle issue (la
                # diagnostica scaricabile lo oscura già del tutto).
                _LOGGER.info("✅ SwVersion: %s | Firmware: %s | S/N: %s",
                             self.thingSwVersion, self.thingFirmware,
                             _mask_serial(self.serialNumber))

                return self.thingId
            else:
                _LOGGER.error("❌ Questo Account Baxi non ha un impianto(ThingId) associato: %s", response.text)
                return None
        except Exception as e:
            _LOGGER.exception("❌ Eccezione nel recupero thingId: %s", e)
            return None

    def fetch_capabilities(self) -> dict:
        """Scarica i cataloghi statici del modello (thingDefinition).

        Ritorna {"commands": [...], "configuration_parameters": [...], "metrics": [...]}.
        Sono cataloghi per-modello, non per-device: non cambiano tra i polling,
        quindi NON vanno chiamati ad ogni ciclo. Usato on-demand dalla
        diagnostica (diagnostics.py) e una tantum dal log di riepilogo debug
        del coordinator. Non solleva: su errore la sezione è [].
        """
        if not self.thingDefinitionId:
            _LOGGER.debug("🔍 fetch_capabilities: thingDefinitionId non disponibile.")
            return {}
        base = f"{self.BASE_URL}/inventory/thingDefinitions/{self.thingDefinitionId}"
        result = {}
        for key, url in (
            ("commands", f"{base}/commands"),
            ("configuration_parameters", f"{base}/configurationParameters"),
            ("metrics", f"{base}/metrics"),
        ):
            if key == "metrics" and self._metric_catalog is not None:
                result[key] = self._metric_catalog  # già letto all'avvio
                continue
            data = self._make_request(url)
            result[key] = data if isinstance(data, list) else []
        return result

    def fetch_model_metrics(self) -> bool:
        """Legge una volta il catalogo delle metriche del modello (thingDefinition).

        Serve a non leggere, e a non creare come entità, le metriche che il
        modello non ha (es. Flame status su un impianto solo elettrico). Non
        conta negli esiti del ciclo e non solleva: se non riesce il catalogo
        resta None, si legge tutto come prima e si ritenta al ciclo successivo.
        """
        if not self.thingDefinitionId:
            return False
        data = self._http_get_json(
            f"{self.BASE_URL}/inventory/thingDefinitions/{self.thingDefinitionId}/metrics"
        )
        if not isinstance(data, list):
            _LOGGER.debug("📚 Catalogo metriche del modello non disponibile, riprovo al prossimo ciclo")
            return False
        self._metric_catalog = data
        self.model_metrics = frozenset(
            m["name"] for m in data if isinstance(m, dict) and m.get("name")
        )
        missing = [n for n in WIRED_METRIC_NAMES if n not in self.model_metrics]
        _LOGGER.debug(
            "📚 Catalogo %s: %d metriche; non presenti su questo modello: %s",
            self.thingDefinitionName or "?", len(self.model_metrics),
            ", ".join(missing) or "nessuna",
        )
        return True

    def has_metric(self, metric_name: str) -> bool:
        """False solo se il catalogo del modello è noto e non contiene la metrica."""
        return self.model_metrics is None or metric_name in self.model_metrics

    def provides(self, attr: str) -> bool:
        """Il modello fornisce il valore dell'attributo? (True se non dipende da una metrica)."""
        metric = METRIC_OF_ATTR.get(attr)
        return metric is None or self.has_metric(metric)

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

    def reset_request_stats(self) -> None:
        """Azzera i contatori delle richieste di lettura (inizio ciclo di polling)."""
        self._requests_ok = 0
        self._requests_failed: list[str] = []

    def request_stats(self) -> tuple[int, list[str]]:
        """Richieste riuscite e nomi di quelle fallite dall'ultimo reset."""
        return self._requests_ok, list(self._requests_failed)

    def _make_request(self, url: str):
        """GET di lettura (vedi _http_get_json) con conteggio degli esiti.

        Il coordinator usa i contatori per distinguere una singola richiesta
        fallita (valore precedente conservato) dal cloud irraggiungibile.
        """
        data = self._http_get_json(url)
        if data is None:
            self._requests_failed.append(_request_label(url))
        else:
            self._requests_ok += 1
        return data

    def _request(self, method: str, url: str, headers: dict | None = None, data=None):
        """
        Richiesta autenticata (GET o PUT) con gestione centralizzata di:
        - token mancante        → login
        - 401 (token scaduto)   → renewToken (fallback: login completo) e ritenta una volta
        - 429 (rate limit)      → onora Retry-After ≤ MAX_RETRY_AFTER_SECONDS e ritenta una volta
        Riusa la sessione HTTP della classe (keep-alive, no TLS handshake ripetuto).
        Ritorna la response (anche non-ok), oppure None se non è possibile
        autenticarsi, il 429 non è ritentabile o la richiesta non va a buon fine.
        Gli errori di rete sono loggati solo in debug: il riepilogo per ciclo
        (o l'indisponibilità) lo logga il coordinator.
        Con la password già rifiutata (auth_rejected) non parte nessuna
        richiesta: ogni richiesta rifarebbe il login con la password sbagliata.
        """
        if self.auth_rejected:
            return None
        if not self.token:
            _LOGGER.warning("⚠️ Nessun token: provo a ri-autenticare.")
            self.authenticate()
            if not self.token:
                _LOGGER.error("❌ Impossibile autenticarsi.")
                return None

        def send():
            # Header ricostruiti a ogni invio: dopo il rinnovo il Bearer cambia.
            return self._session.request(
                method, url,
                headers={**(headers or {}), **self._auth_headers()},
                data=data,
                timeout=self.REQUEST_TIMEOUT,
            )

        try:
            response = send()

            # 401: token scaduto → rinnova (o ri-login) e ritenta una sola volta.
            # Evento atteso (JWT da 1 ora): solo debug; i fallimenti del rinnovo
            # restano warning.
            if response.status_code == 401:
                _LOGGER.debug("🔐 Token scaduto, rinnovo in corso...")
                self._reauthenticate()
                if not self.token:
                    _LOGGER.error("❌ Impossibile autenticarsi.")
                    return None
                response = send()

            # 429: rate limit → backoff via Retry-After e ritenta una sola volta
            if response.status_code == 429:
                delay = self._parse_retry_after(response)
                if delay is None:
                    _LOGGER.warning(
                        "⏳ Rate limit (429) su %s %s senza Retry-After utile — salto.",
                        method, _mask_url(url),
                    )
                    return None
                _LOGGER.warning(
                    "⏳ Rate limit (429) su %s %s, attendo %ss e riprovo.",
                    method, _mask_url(url), delay,
                )
                _sleep(delay)
                response = send()

            return response
        except requests.RequestException as e:
            # Rete/timeout: atteso durante un'interruzione del cloud.
            _LOGGER.debug("❌ Richiesta %s %s non riuscita: %s", method, _mask_url(url), e)
            return None
        except Exception as e:
            # Inatteso: resta visibile con traceback.
            _LOGGER.exception("❌ Eccezione nella richiesta %s %s: %s", method, _mask_url(url), e)
            return None

    def _http_get_json(self, url: str):
        """GET autenticata (vedi _request) che ritorna il JSON, o None se non riesce."""
        response = self._request("GET", url)
        if response is None:
            return None
        if not response.ok:
            _LOGGER.debug(
                "❌ HTTP %s su %s: %s", response.status_code, _mask_url(url), response.text[:300],
            )
            return None
        try:
            return response.json()
        except ValueError as e:
            _LOGGER.warning("❌ Risposta non JSON da %s: %s", _mask_url(url), e)
            return None

    def _metric_url(self, metric_name: str, page_size: int = 1) -> str:
        if not self.thingId:
            raise RuntimeError("thingId non inizializzato")
        return (
            f"{self.BASE_URL}/data/values?"
            f"thingId={self.thingId}"
            f"&pageSize={page_size}"
            f"&metricName={quote_plus(metric_name)}"
        )

    def fetch_metric_history(self, metric_name: str, size: int) -> list[dict] | None:
        """Ultimi `size` campioni di una metrica, dal più recente (solo per la diagnostica).

        Il cloud salva un campione solo quando il valore cambia: sono gli
        ultimi cambi, ognuno con il suo timestamp. Una richiesta per metrica,
        non conta negli esiti del ciclo. None se la richiesta non riesce.
        """
        data = self._http_get_json(self._metric_url(metric_name, page_size=size))
        if not isinstance(data, dict):
            return None
        history = []
        for item in data.get("data") or []:
            try:
                history.append({"timestamp": item["timestamp"], "value": item["values"][0]["value"]})
            except (KeyError, IndexError, TypeError):
                continue
        return history

    # Sentinelle "no data" pubblicate da Servitly: il valore esiste ma la misura
    # è assente (tipico per metriche non applicabili al device, es. flame status
    # su impianto solo elettrico — issue #6).
    _NO_DATA_SENTINELS = frozenset({"---", ""})

    # ---------------- Dispatcher metriche semplici ----------------
    def _bulk_sample(self, metric_name: str) -> dict | None:
        """Campione della lettura multipla del ciclo corrente, se presente (vedi fetch_all_metrics)."""
        return (self._bulk_samples or {}).get(metric_name)

    def _apply_simple_sample(self, spec: SimpleMetricSpec, raw, timestamp, context: str) -> None:
        """Applica il valore grezzo di una metrica semplice: stesse regole per lettura multipla e singola.

          - value in _NO_DATA_SENTINELS → attributo None, log debug
          - None su metrica numerica    → valore precedente conservato, log debug
          - parsing fallito             → attributo None, log warning + estratto della risposta
        """
        # Metrica numerica senza lettura in questo momento (es. "WiFi signal"
        # alterna valori e vuoti ogni minuto): come una richiesta fallita, si
        # tiene il valore precedente. Le metriche a codici usano None come
        # valore vero (es. Modo Impianto null = Automatico): restano al parser.
        if raw is None and spec.parser is _parse_float:
            _LOGGER.debug("ℹ️ %s senza valore in questo momento, tengo il precedente", spec.metric_name)
            return
        # Metrica esposta ma senza misura corrente (sentinella).
        if isinstance(raw, str) and raw.strip() in self._NO_DATA_SENTINELS:
            setattr(self, spec.attr, None)
            setattr(self, f"{spec.attr}_timestamp", None)
            _LOGGER.debug(
                "ℹ️ %s = '%s' (sentinella no-data, ignorata)",
                spec.metric_name, raw,
            )
            return
        try:
            value = spec.parser(raw)
        except (KeyError, IndexError, ValueError, TypeError) as e:
            setattr(self, spec.attr, None)
            setattr(self, f"{spec.attr}_timestamp", None)
            _LOGGER.warning(
                "⚠️ Parsing fallito (%s): %s — response: %s",
                spec.metric_name, e, context[:300],
            )
            return
        setattr(self, spec.attr, value)
        setattr(self, f"{spec.attr}_timestamp", timestamp)
        _LOGGER.debug("%s %s = %s", spec.log_emoji, spec.metric_name, value)

    def _fetch_one(self, spec: SimpleMetricSpec) -> None:
        """
        Legge una singola metrica con /data/values e memorizza valore + timestamp.

        Casi gestiti (issue #6 — Baxi solo elettrica / metriche non applicabili
        al device):
          - richiesta fallita            → valore precedente conservato
          - data["data"] == []          → attributo None, log debug (NON è errore)
          - sentinella / parsing         → vedi _apply_simple_sample
        """
        data = self._make_request(self._metric_url(spec.metric_name))
        if not data:
            return

        # La metrica non è esposta dal device → "data" è un array vuoto.
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
            timestamp = item["timestamp"]
        except (KeyError, IndexError, TypeError) as e:
            setattr(self, spec.attr, None)
            setattr(self, f"{spec.attr}_timestamp", None)
            _LOGGER.warning(
                "⚠️ Parsing fallito (%s): %s — response: %s",
                spec.metric_name, e, json.dumps(data)[:300],
            )
            return
        self._apply_simple_sample(spec, raw, timestamp, json.dumps(data))

    def fetch_simple_metrics(self) -> None:
        """Applica tutte le metriche definite in SIMPLE_METRICS.

        Usa i campioni della lettura multipla del ciclo (fetch_all_metrics); le
        metriche assenti, o tutte se la lettura multipla non c'è, sono lette
        singolarmente come prima. Le metriche che il modello non ha non vengono
        lette (valore None).
        """
        for spec in SIMPLE_METRICS:
            if not self.has_metric(spec.metric_name):
                setattr(self, spec.attr, None)
                setattr(self, f"{spec.attr}_timestamp", None)
                continue
            sample = self._bulk_sample(spec.metric_name)
            if sample is None:
                self._fetch_one(spec)
            else:
                self._apply_simple_sample(
                    spec, sample["value"], sample["timestamp"], json.dumps(sample, default=str),
                )
        # "Data/Ora fine modo vacanza" è calcolata dal cloud: a vacanza spenta
        # non arriva vuota ma con l'ora del suo ultimo ricalcolo (circa ogni 2
        # ore). È una data di fine valida solo a vacanza attiva.
        if self.holiday_mode != "On":
            self.holiday_mode_end = None
            self.holiday_mode_end_timestamp = None

    # ----- I vecchi fetch_<metrica> per-attributo sono stati collassati in -----
    # fetch_simple_metrics() + SIMPLE_METRICS (dispatcher tabellare, vedi sopra).
    # Restano qui sotto solo i fetch con logica non-banale: energia e scheduler.

    # 🔴 Sensori energia
    def _fetch_last_values(self, metric_names) -> dict[str, dict] | None:
        """Ultimo campione di più metriche con GET /data/lastValues.

        Fino a LAST_VALUES_MAX_METRICS metricName per richiesta (oltre si fanno
        più richieste). Ritorna {metricName: {"value": ..., "timestamp": ...}}
        per le metriche presenti nella risposta, oppure None se una richiesta
        non riesce.
        """
        if not self.thingId:
            raise RuntimeError("thingId non inizializzato")
        names = list(dict.fromkeys(metric_names))
        samples: dict[str, dict] = {}
        for start in range(0, len(names), self.LAST_VALUES_MAX_METRICS):
            chunk = names[start:start + self.LAST_VALUES_MAX_METRICS]
            params = "&".join(f"metricName={quote_plus(n)}" for n in chunk)
            data = self._make_request(
                f"{self.BASE_URL}/data/lastValues?thingId={self.thingId}&{params}"
            )
            if not isinstance(data, dict):
                return None
            for item in data.get("data") or []:
                if isinstance(item, dict) and item.get("metric") in chunk:
                    ts = item.get("ts", item.get("timestamp"))
                    if isinstance(ts, str):
                        try:
                            ts = int(float(ts))
                        except ValueError:
                            ts = None
                    samples[item["metric"]] = {"value": item.get("value"), "timestamp": ts}
        return samples

    def _last_value_single(self, metric_name: str) -> dict | None:
        """Ultimo campione di una sola metrica con /data/values (stesso formato di _fetch_last_values).

        None se la richiesta non riesce; KeyError/IndexError/TypeError se la
        risposta non contiene un campione (gestite dal chiamante).
        """
        data = self._make_request(self._metric_url(metric_name))
        if not data:
            return None
        item = data["data"][0]
        return {"value": item["values"][0]["value"], "timestamp": item.get("timestamp")}

    def _apply_energy_sample(self, desc, sample: dict | None) -> None:
        """Converte un campione energia in kWh e lo salva (stessa logica per lettura multipla e singola)."""
        if sample is None:
            # Richiesta non riuscita: valore non disponibile (come le letture singole).
            setattr(self, desc.key, None)
            self.energy_timestamp[desc.key] = None
            return

        raw_val = sample["value"]
        ts = sample["timestamp"]

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

    def fetch_energy_metrics(self):
        """
        Legge tutte le metriche energia definite in ENERGY_SENSOR_TYPES.
        Salva i valori su self.<key> e (opzionale) i timestamp su self.energy_timestamp[key].

        Usa i campioni della lettura multipla del ciclo (fetch_all_metrics); le
        metriche assenti, o tutte se la lettura multipla non c'è, sono lette
        singolarmente come prima. Le metriche che il modello non ha non vengono
        lette (valore None).
        """
        for desc in ENERGY_SENSOR_TYPES:
            if not self.has_metric(desc.metric_name):
                setattr(self, desc.key, None)
                self.energy_timestamp[desc.key] = None
                continue
            sample = self._bulk_sample(desc.metric_name)
            try:
                if sample is None:
                    sample = self._last_value_single(desc.metric_name)
                self._apply_energy_sample(desc, sample)
            except (KeyError, IndexError, TypeError) as e:
                setattr(self, desc.key, None)
                self.energy_timestamp[desc.key] = None
                _LOGGER.warning(
                    "⚠️ Parsing fallito (energia: %s): %s — campione 📦: %s",
                    desc.metric_name, e, str(sample)[:300],
                )

    def fetch_all_metrics(self) -> None:
        """Legge tutte le metriche del ciclo con una richiesta GET /data/lastValues.

        Una sola richiesta per WIRED_METRIC_NAMES, poi metriche semplici,
        scheduler sanitario ed energia applicano quei campioni. Le metriche
        assenti dalla risposta, o tutte se la richiesta multipla non riesce,
        sono lette singolarmente con /data/values come prima: il risultato è lo
        stesso. Dopo LAST_VALUES_MAX_FAILURES fallimenti di fila mentre le
        letture singole riescono, la lettura multipla viene disattivata fino al
        riavvio. Le metriche che il modello non ha (catalogo, vedi
        fetch_model_metrics) non vengono chieste affatto.
        """
        names = [n for n in WIRED_METRIC_NAMES if self.has_metric(n)]
        bulk_tried = self._last_values_enabled
        self._bulk_samples = self._fetch_last_values(names) if bulk_tried else None
        bulk_failed = bulk_tried and self._bulk_samples is None
        if self._bulk_samples is not None:
            self._last_values_failures = 0
            missing = [n for n in names if n not in self._bulk_samples]
            if missing:
                _LOGGER.debug(
                    "📥 Metriche assenti da lastValues, lette singolarmente: %s",
                    ", ".join(missing),
                )
        elif bulk_tried:
            _LOGGER.debug("📥 lastValues non riuscita: letture singole")

        ok_before = self._requests_ok
        try:
            self.fetch_simple_metrics()
            self.fetch_sanitary_scheduler()
            self.fetch_energy_metrics()
        finally:
            self._bulk_samples = None

        # La lettura multipla fallisce mentre quelle singole riescono: dopo
        # alcuni cicli di fila l'endpoint è considerato non disponibile per
        # questo impianto (fino al riavvio), per non pagare una richiesta in più.
        if bulk_failed and self._requests_ok > ok_before:
            self._last_values_failures += 1
            if self._last_values_failures >= self.LAST_VALUES_MAX_FAILURES:
                self._last_values_enabled = False
                _LOGGER.info(
                    "ℹ️ lastValues non disponibile per questo impianto: uso le letture singole"
                )

    def fetch_sanitary_scheduler(self):
        """Programma del sanitario: campione della lettura multipla del ciclo o lettura singola."""
        if not self.has_metric(SANITARY_SCHEDULER_METRIC):
            self.sanitary_scheduler_status = "empty"
            return
        sample = self._bulk_sample(SANITARY_SCHEDULER_METRIC)
        data = None
        try:
            if sample is None:
                data = self._make_request(self._metric_url(SANITARY_SCHEDULER_METRIC))
                if not data:
                    self.sanitary_scheduler_status = "error"
                    return
                raw_str = data["data"][0]["values"][0]["value"]  # è una stringa JSON
            else:
                raw_str = sample["value"]
            self.sanitary_scheduler_raw = raw_str
            self._compute_sanitary_schedule_state(raw_str)
            self.sanitary_scheduler_status = "ok"
            _LOGGER.debug("📅 Schedulatore Sanitario: %s", self.sanitary_scheduler_raw)
        except (KeyError, IndexError, ValueError, TypeError, AttributeError) as e:
            # Azzera il campo, warning + debug della risposta. AttributeError:
            # JSON valido ma non un oggetto (i dispatcher non devono sollevare).
            self.sanitary_scheduler_raw = None
            self.sanitary_scheduler_status = "error"
            response = json.dumps(data if data is not None else sample, default=str)
            _LOGGER.warning("⚠️ Parsing fallito (Schedulatore sanitario): %s — response 📦: %s", e, response[:300])
            _LOGGER.debug("📦 Contenuto (Schedulatore sanitario): %s", response)

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

            # Debug, non info: gira a ogni ciclo di polling (~144 righe/giorno).
            # I nuovi alert restano visibili via evento sul bus + Logbook.
            _LOGGER.debug(
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
        if not self.thingId:
            _LOGGER.warning("⚠️ Nessun thingId, provo a recuperarlo...")
            self.get_thingid()
            if not self.thingId:
                _LOGGER.error("❌ Impossibile ottenere il thingId per PUT command.")
                return False

        url = f"{self.BASE_URL}/data/commands?commandId={command_id}&thingId={self.thingId}"
        response = self._request(
            "PUT", url, headers={'content-type': 'application/json'},
        )
        if response is None:
            _LOGGER.error("❌ PUT command %s non eseguito.", command_id)
            return False

        # 204 = No Content → successo
        if response.ok:
            _LOGGER.info("📤✅ Comando %s eseguito (HTTP %s)", command_id, response.status_code)
            return True
        _LOGGER.error("❌ Errore PUT command %s → HTTP %s: %s", command_id, response.status_code, response.text)
        return False

    def set_configuration_parameter(self, parameter_id: str, value: float | int | str):
        """
        Esegue una chiamata PUT per aggiornare un parametro configurabile
        (es. setpoint eco, comfort, ecc.)
        """
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

        response = self._request(
            "PUT", url, headers={'content-type': 'application/json'}, data=payload,
        )
        if response is None:
            _LOGGER.error("❌ PUT parametro %s non eseguita.", parameter_id)
            return False

        if response.ok:
            _LOGGER.info("📤✅ PUT parametro %s impostato a %s", parameter_id, value)
            return True
        _LOGGER.error("❌ Errore PUT parametro %s → %s", parameter_id, response.text)
        return False
