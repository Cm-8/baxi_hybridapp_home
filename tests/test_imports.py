"""Ogni modulo dell'integrazione si importa con la versione minima di HA supportata.

Intercetta subito import non più validi (es. HomeAssistantType, rimosso da HA)
e NameError a livello di modulo, che py_compile non vede.
"""

import importlib
from pathlib import Path

import pytest

PACKAGE = "custom_components.baxi_hybridapp_home"
PACKAGE_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "baxi_hybridapp_home"
MODULES = sorted(p.stem for p in PACKAGE_DIR.glob("*.py") if p.stem != "__init__")


@pytest.mark.parametrize("module", ["__init__", *MODULES])
def test_module_imports(module):
    importlib.import_module(PACKAGE if module == "__init__" else f"{PACKAGE}.{module}")


def test_every_platform_has_a_module():
    from custom_components.baxi_hybridapp_home import PLATFORMS

    assert set(PLATFORMS) <= set(MODULES)
