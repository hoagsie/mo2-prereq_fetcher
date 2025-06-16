"""
Prerequisite Fetcher – Mod Organizer 2 plug-in
Bootstraps the module and returns one PrereqFetcher instance.
"""

from __future__ import annotations
import sys, pathlib
from typing import cast
import mobase

# ── make bundled third-party libs (deps/) importable ─────────────────────────
_DEPS = pathlib.Path(__file__).parent / "deps"
if _DEPS.is_dir() and str(_DEPS) not in sys.path:
    sys.path.insert(0, str(_DEPS))

# ── actual plug-in class lives in plugin.py ──────────────────────────────────
from .plugin import PrereqFetcher


def createPlugin() -> mobase.IPlugin:
    """MO2 entry-point: return the single plug-in instance."""
    return cast(mobase.IPlugin, PrereqFetcher())
