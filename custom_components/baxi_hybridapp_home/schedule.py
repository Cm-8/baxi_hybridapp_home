"""
Programma settimanale del riscaldamento di una zona ("Riscaldamento - Zona 1").

Formato del cloud, uguale su ibridi (CSI IN SPLIT E) e caldaie LUNA IN PLUS:
JSON con i giorni "Lun".."Dom"; ogni giorno è una lista di fasce
{"start": "HH:MM", "end": "HH:MM", "params": {"Temperatura": 21}} più una
voce con start/end null, la temperatura fuori dalle fasce. Le temperature
possono avere mezzi gradi (20.5 sulla LUNA).

Funzioni pure, senza richieste né stato: le usa api.fetch_heating_schedule.

custom_components/baxi_hybridapp_home/schedule.py
"""

import json
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

# Stesse chiavi e stessa timezone del programma sanitario.
DAY_KEYS = ("Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom")
SCHEDULE_TZ = ZoneInfo("Europe/Rome")
_DAY_MINUTES = 24 * 60


def _minutes(hhmm: str) -> int:
    hh, mm = str(hhmm).split(":")
    return int(hh) * 60 + int(mm)


def _hhmm(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _temperature(slot: dict) -> float | None:
    value = (slot.get("params") or {}).get("Temperatura")
    return float(value) if value is not None else None


def day_segments(slots) -> tuple[list[tuple[int, int, float | None]], float | None]:
    """Fasce di un giorno come (inizio, fine, temperatura) in minuti, da 0 a 1440 senza buchi.

    Le ore non coperte dalle fasce hanno la temperatura della voce senza
    orari. Una fascia che finisce a "00:00"/"24:00" o dopo la mezzanotte vale
    fino a fine giornata. Fasce consecutive con la stessa temperatura sono
    unite. Ritorna anche la temperatura fuori dalle fasce.
    """
    base = None
    ranges = []
    for slot in slots or []:
        start, end = slot.get("start"), slot.get("end")
        if start and end:
            s, e = _minutes(start), _minutes(end)
            if e <= s:
                e = _DAY_MINUTES
            ranges.append((s, min(e, _DAY_MINUTES), _temperature(slot)))
        else:
            base = _temperature(slot)
    ranges.sort(key=lambda r: r[0])

    segments: list[tuple[int, int, float | None]] = []

    def add(s, e, temp):
        if e <= s:
            return
        if segments and segments[-1][2] == temp and segments[-1][1] == s:
            segments[-1] = (segments[-1][0], e, temp)
        else:
            segments.append((s, e, temp))

    cursor = 0
    for s, e, temp in ranges:
        if s > cursor:
            add(cursor, s, base)
        s = max(s, cursor)
        add(s, e, temp)
        cursor = max(cursor, e)
    add(cursor, _DAY_MINUTES, base)
    return segments, base


def heating_schedule_state(raw, now: datetime | None = None) -> dict:
    """Stato del programma in un istante: temperatura, prossimo cambio, fasce di oggi.

    Solleva ValueError se il programma non è un oggetto JSON con i giorni.
    """
    data = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(data, dict):
        raise ValueError("programma non valido")
    now = (now or datetime.now(SCHEDULE_TZ)).astimezone(SCHEDULE_TZ)
    minute = now.hour * 60 + now.minute

    today_segments, base = day_segments(data.get(DAY_KEYS[now.weekday()]))
    # (data, fasce) da oggi a oggi + 7 giorni: il cambio può essere più avanti.
    days = [(now.date(), today_segments)]
    for offset in range(1, 8):
        day = now.date() + timedelta(days=offset)
        days.append((day, day_segments(data.get(DAY_KEYS[day.weekday()]))[0]))

    temperature = next((t for s, e, t in today_segments if s <= minute < e), None)

    # Prossimo cambio di temperatura, anche nei giorni seguenti.
    next_change = next_temperature = None
    for offset, (day, segments) in enumerate(days):
        for s, _e, temp in segments:
            if offset == 0 and s <= minute:
                continue
            if temp != temperature:
                next_change = datetime.combine(day, time(s // 60, s % 60), tzinfo=SCHEDULE_TZ)
                next_temperature = temp
                break
        if next_change:
            break

    return {
        "temperature": temperature,
        "next_change": next_change,
        "next_temperature": next_temperature,
        "base_temperature": base,
        "today": [
            {"dalle": _hhmm(s), "alle": _hhmm(e), "temperatura": t}
            for s, e, t in today_segments
        ],
    }
