"""Coerenza tra codice, traduzioni (it/en) e icons.json."""

import json
import re
from pathlib import Path

import pytest

from custom_components.baxi_hybridapp_home import _SANITARY_SERVICES
from custom_components.baxi_hybridapp_home.const import CONF_POLLING_INTERVAL, POLLING_INTERVAL_OPTIONS
from custom_components.baxi_hybridapp_home.metrics import ENERGY_SENSOR_TYPES

PKG = Path(__file__).resolve().parents[1] / "custom_components" / "baxi_hybridapp_home"
# Stessa regola di hassfest per chiavi di traduzione e stati.
RE_TRANSLATION_KEY = re.compile(r"^(?!.+[_-]{2})(?![_-])[a-z0-9-_]+(?<![_-])$")
PLATFORM_OF = {
    "sensor.py": "sensor", "metrics.py": "sensor", "binary_sensor.py": "binary_sensor",
    "button.py": "button", "select.py": "select", "number.py": "number",
    "water_heater.py": "water_heater", "switch.py": "switch", "datetime.py": "datetime",
}


def load(name):
    return json.loads((PKG / name).read_text(encoding="utf-8"))


IT, EN, ICONS = load("translations/it.json"), load("translations/en.json"), load("icons.json")


def key_paths(node, prefix=()):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from key_paths(v, (*prefix, k))
    else:
        yield prefix


def strings(node):
    if isinstance(node, dict):
        for v in node.values():
            yield from strings(v)
    else:
        yield node


def code_keys():
    """(file, chiave) usate nel codice per nomi di entità ed errori tradotti."""
    found = set()
    for f in PKG.glob("*.py"):
        src = f.read_text(encoding="utf-8")
        for pattern in (r'translation_key\s*=\s*"([^"]+)"', r'_raise_write_failed\("([^"]+)"'):
            found |= {(f.name, k) for k in re.findall(pattern, src)}
    found |= {("metrics.py", d.translation_key) for d in ENERGY_SENSOR_TYPES}
    found |= {("__init__.py", spec[-1]) for spec in _SANITARY_SERVICES.values()}
    return found


def test_italian_and_english_have_the_same_keys():
    assert set(key_paths(IT)) == set(key_paths(EN))


def test_keys_follow_hassfest_rules():
    for platform, entities in EN["entity"].items():
        for key in entities:
            assert RE_TRANSLATION_KEY.match(key), f"entity.{platform}.{key}"
    for key in EN["exceptions"]:
        assert RE_TRANSLATION_KEY.match(key), f"exceptions.{key}"
    for selector, spec in EN["selector"].items():
        for key in spec["options"]:
            assert RE_TRANSLATION_KEY.match(key), f"selector.{selector}.options.{key}"


def test_polling_interval_choices_are_translated():
    options = EN["selector"][CONF_POLLING_INTERVAL]["options"]
    assert set(options) == {str(m) for m in POLLING_INTERVAL_OPTIONS}
    assert CONF_POLLING_INTERVAL in EN["options"]["step"]["init"]["data"]


@pytest.mark.parametrize("translations", [IT, EN], ids=["it", "en"])
def test_strings_are_clean(translations):
    for text in strings(translations):
        assert text == text.strip(), repr(text)
        assert "'{" not in text, repr(text)


def test_every_key_used_in_code_is_translated():
    for file, key in code_keys():
        platform = PLATFORM_OF.get(file)
        in_entity = platform is not None and key in EN["entity"].get(platform, {})
        assert in_entity or key in EN["exceptions"], f"{file}: chiave {key} non tradotta"


def test_every_translation_is_used():
    used = {key for _, key in code_keys()}
    for platform, entities in EN["entity"].items():
        for key in entities:
            assert key in used, f"entity.{platform}.{key} non usata nel codice"
    for key in EN["exceptions"]:
        assert key in used, f"exceptions.{key} non usata nel codice"


def test_icons_reference_translated_entities():
    for platform, entities in ICONS["entity"].items():
        for key, icon in entities.items():
            assert key in EN["entity"].get(platform, {}), f"icona per {platform}.{key} senza traduzione"
            assert icon["default"].startswith("mdi:")
            for state, state_icon in icon.get("state", {}).items():
                assert RE_TRANSLATION_KEY.match(state) and state_icon.startswith("mdi:")
