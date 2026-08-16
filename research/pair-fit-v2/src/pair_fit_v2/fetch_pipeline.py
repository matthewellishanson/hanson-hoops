from __future__ import annotations

from pathlib import Path
from typing import Any

from pair_fit_v2.live_fetch import run_cached_audit, run_live_audit


def run_phase0_audit(live: bool = False) -> dict[str, Any]:
    """Thin wrapper for the research pipeline. Use live=True for the bounded live run and live=False for cached validation."""
    return run_live_audit(force_live=live) if live else run_cached_audit()
