"""Test dei parser e delle tabelle dichiarative in metrics.py."""

from datetime import datetime, timezone

import pytest

from custom_components.baxi_hybridapp_home.metrics import (
    ENERGY_SENSOR_TYPES,
    SIMPLE_METRICS,
    _parse_epoch_ms,
    _parse_float,
)


def parser_for(attr):
    """Parser reale della metrica, preso dalla tabella SIMPLE_METRICS."""
    return next(spec.parser for spec in SIMPLE_METRICS if spec.attr == attr)


# --- Tabelle -----------------------------------------------------------------


def test_simple_metric_attrs_are_unique():
    attrs = [spec.attr for spec in SIMPLE_METRICS]
    assert len(attrs) == len(set(attrs))


def test_simple_metric_names_are_unique():
    names = [spec.metric_name for spec in SIMPLE_METRICS]
    assert len(names) == len(set(names))


def test_energy_keys_and_names_are_unique():
    keys = [desc.key for desc in ENERGY_SENSOR_TYPES]
    names = [desc.metric_name for desc in ENERGY_SENSOR_TYPES]
    assert len(keys) == len(set(keys))
    assert len(names) == len(set(names))


# --- Parser numerici -----------------------------------------------------------


def test_parse_float():
    assert _parse_float("21.5") == 21.5


class TestParseEpochMs:
    def test_integer_string(self):
        assert _parse_epoch_ms("1784494020000") == datetime(2026, 7, 19, 20, 47, tzinfo=timezone.utc)

    def test_float_string(self):
        # Il cloud a volte manda l'epoch come float: "invalid literal for int()".
        assert _parse_epoch_ms("1784797954954.0") == datetime(
            2026, 7, 23, 9, 12, 34, 954000, tzinfo=timezone.utc
        )

    def test_native_float(self):
        assert _parse_epoch_ms(1784797954954.0) == datetime(
            2026, 7, 23, 9, 12, 34, 954000, tzinfo=timezone.utc
        )

    @pytest.mark.parametrize("raw", ["0", "0.0", "-1", -1])
    def test_no_date_is_none(self, raw):
        # "-1" è anche il valore inviato per spegnere la vacanza.
        assert _parse_epoch_ms(raw) is None

    def test_non_numeric_raises(self):
        # L'errore è gestito dal dispatcher (warning + attributo None).
        with pytest.raises(ValueError):
            _parse_epoch_ms("---")


# --- Mapper dei codici -----------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0001", "Automatico"),
        ("1", "Automatico"),
        ("0007", "Standby"),
        ("000D", "Solo Sanitario"),
        ("000d", "Solo Sanitario"),
        (" 000D ", "Solo Sanitario"),
        ("D", "Solo Sanitario"),
    ],
)
def test_system_operation_mode(raw, expected):
    assert parser_for("system_operation_mode")(raw) == expected


def test_unknown_code_is_reported_not_hidden():
    assert parser_for("system_operation_mode")("0009") == "Sconosciuto (0009)"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, "Automatico"), ("0000", "Standby"), ("0005", "Solo Sanitario")],
)
def test_system_mode(raw, expected):
    # Il cloud manda null quando l'impianto è in Automatico.
    assert parser_for("system_mode")(raw) == expected


@pytest.mark.parametrize(("raw", "expected"), [("0000", "Off"), ("0001", "On")])
def test_holiday_mode(raw, expected):
    assert parser_for("holiday_mode")(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0000", "Off"),
        ("0001", "On"),
        # Il cloud alterna il codice grezzo e il valore già trasformato.
        ("Off", "Off"),
        ("On", "On"),
    ],
)
def test_status_boiler(raw, expected):
    assert parser_for("status_boiler")(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("0000", "Off"), ("0001", "On"), ("0002", "Avvio"), ("Off", "Off")],
)
def test_status_pdc(raw, expected):
    assert parser_for("status_pdc")(raw) == expected


@pytest.mark.parametrize(
    ("attr", "raw", "expected"),
    [
        # Valore vuoto: sanitario in Standby, resistenze non abilitate → spenti.
        ("sanitary_on", None, "Off"),
        ("sanitary_on", "1", "On"),
        ("resistances_on", None, "Off"),
        ("resistances_on", "0001", "On"),
        # Funzione in corso (metriche "per counter").
        ("heating_active", "0001", "On"),
        ("heating_active", "0000", "Off"),
        ("dhw_active", "0001", "On"),
    ],
)
def test_on_off_states(attr, raw, expected):
    assert parser_for(attr)(raw) == expected
