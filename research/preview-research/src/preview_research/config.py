from __future__ import annotations

import os
from pathlib import Path

DEFAULT_SEASONS = ("2021-22", "2022-23", "2023-24", "2024-25", "2025-26")
DEFAULT_SEASON_TYPE = "Regular Season"
ALLOWED_SEASON_TYPES = ("Regular Season", "Playoffs", "Pre Season")


def project_root() -> Path:
    configured = os.getenv("PREVIEW_RESEARCH_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def season_slug(season: str) -> str:
    return season.replace("/", "-").replace("\\", "-")


def season_type_slug(season_type: str) -> str:
    return season_type.lower().replace(" ", "_")

