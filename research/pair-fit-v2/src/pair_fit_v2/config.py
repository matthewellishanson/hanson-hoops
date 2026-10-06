from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Phase0Config:
    """Config for the research-only Phase 0 smoke test."""

    target_season: str = "2024-25"
    prior_season: str = "2023-24"
    season_type: str = "Regular Season"
    group_quantity: int = 2
    measure_types: list[str] = field(
        default_factory=lambda: ["Base", "Advanced", "Four Factors", "Usage"]
    )
    allow_live_calls: bool = False
    cache_dir: Path = Path(__file__).resolve().parents[2] / "cache"
    fixtures_dir: Path = Path(__file__).resolve().parents[2] / "fixtures"
    data_dictionary_path: Path = Path(__file__).resolve().parents[2] / "DATA_DICTIONARY.md"
    feasibility_report_path: Path = Path(__file__).resolve().parents[2] / "FEASIBILITY_REPORT.md"
