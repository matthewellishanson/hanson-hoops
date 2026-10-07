"""Small notebook-facing API; all reads are cache-only."""

from .config import DEFAULT_SEASONS, DEFAULT_SEASON_TYPE
from .query import (
    QueryResult,
    compare_entity,
    export_result,
    filter_rows,
    join_compatible,
    load_dataset,
    year_over_year,
)
from .storage import ResearchStore
from .transform import build_shooting
from .validation import combined_percentage

__all__ = [
    "DEFAULT_SEASONS",
    "DEFAULT_SEASON_TYPE",
    "QueryResult",
    "ResearchStore",
    "build_shooting",
    "combined_percentage",
    "compare_entity",
    "export_result",
    "filter_rows",
    "join_compatible",
    "load_dataset",
    "year_over_year",
]

