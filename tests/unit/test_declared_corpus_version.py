"""Pin one declared corpus version across the participating exchange helpers."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from scripts.package_plugin import read_plugin_version
from scripts.semver import SEMVER_PATTERN

ROOT = Path(__file__).resolve().parents[2]
PARTICIPATING_HELPERS = (
    "skills/review-exchange/scripts/review_exchange.py",
    "skills/review-exchange/scripts/issue_exchange.py",
    "skills/pr-review/scripts/deliver_go.py",
)


def _declared_corpus_version(relative: str) -> str:
    """Read the compiled corpus version constant from one helper file."""
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(f"declared_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"The helper cannot be loaded: '{relative}'.")
    module: ModuleType = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    declared = getattr(module, "CORPUS_VERSION", None)
    if not isinstance(declared, str):
        raise TypeError(f"The helper declares no corpus version: '{relative}'.")
    return declared


def test_participating_helpers_declare_the_host_manifest_version() -> None:
    """Each participating helper declares exactly one valid host-manifest version."""
    expected = read_plugin_version(ROOT)
    for relative in PARTICIPATING_HELPERS:
        declared = _declared_corpus_version(relative)
        assert SEMVER_PATTERN.fullmatch(declared) is not None, relative
        assert declared == expected, relative
