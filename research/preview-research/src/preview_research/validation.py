from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
import pandas as pd

from .datasets import DatasetSpec


PERCENT_FRACTION_COLUMNS = {
    "W_PCT", "FG_PCT", "FG3_PCT", "FT_PCT",
    "AST_PCT", "OREB_PCT", "DREB_PCT", "REB_PCT", "TM_TOV_PCT",
    "E_TOV_PCT", "USG_PCT", "E_USG_PCT", "PCT_FGA_2PT", "PCT_FGA_3PT",
    "CALC_FG2_PCT", "CALC_FG_PCT", "CALC_FG3_PCT", "CALC_FT_PCT",
    "CALC_FG3_ATTEMPT_RATE",
}
EFFICIENCY_FRACTION_COLUMNS = {"EFG_PCT", "TS_PCT", "CALC_TS_PCT", "CALC_EFG_PCT"}


class ValidationError(ValueError):
    """A dataset failed a research-safety check."""


@dataclass
class ValidationReport:
    status: str
    row_count: int
    checks: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "validation_status": self.status,
            "row_count": self.row_count,
            "validation_checks": self.checks,
            "validation_warnings": self.warnings,
        }


def _require_columns(frame: pd.DataFrame, required: Iterable[str]) -> None:
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise ValidationError(f"Missing required columns: {', '.join(missing)}")


def _reject_duplicate_keys(frame: pd.DataFrame, keys: Iterable[str]) -> None:
    keys = list(keys)
    _require_columns(frame, keys)
    duplicate = frame.duplicated(keys, keep=False)
    if duplicate.any():
        sample = frame.loc[duplicate, keys].head(5).to_dict(orient="records")
        raise ValidationError(f"Duplicate row grain for keys {keys}: {sample}")


def _reject_nonfinite(frame: pd.DataFrame) -> None:
    numeric = frame.select_dtypes(include="number")
    if numeric.empty:
        return
    values = numeric.to_numpy(dtype=float, na_value=np.nan)
    bad = np.isinf(values)
    if bad.any():
        columns = sorted(set(numeric.columns[np.where(bad)[1]].tolist()))
        raise ValidationError(f"Infinite numeric values are not allowed: {', '.join(columns)}")


def _check_fraction_units(frame: pd.DataFrame) -> list[str]:
    warnings: list[str] = []
    relevant = (PERCENT_FRACTION_COLUMNS | EFFICIENCY_FRACTION_COLUMNS) & set(frame.columns)
    for column in sorted(relevant):
        values = pd.to_numeric(frame[column], errors="coerce").dropna()
        if values.empty:
            continue
        maximum = 1.50001 if column in EFFICIENCY_FRACTION_COLUMNS else 1.00001
        outside = values[(values < 0) | (values > maximum)]
        if not outside.empty:
            raise ValidationError(
                f"{column} must use fraction units with a plausible maximum of {maximum:g}; observed range "
                f"{values.min():.4g} to {values.max():.4g}"
            )
        if values.max() <= 0.05:
            warnings.append(f"{column} has a suspiciously small maximum ({values.max():.4g})")
    return warnings


def validate_dataset(frame: pd.DataFrame, spec: DatasetSpec) -> ValidationReport:
    if frame.empty:
        raise ValidationError("A successful dataset cannot be empty")
    _require_columns(frame, spec.required_columns)
    _reject_duplicate_keys(frame, spec.keys)
    _reject_nonfinite(frame)
    warnings = _check_fraction_units(frame)
    if not spec.expected_min_rows <= len(frame) <= spec.expected_max_rows:
        raise ValidationError(
            f"Unexpected {spec.name} population: {len(frame)} rows; expected "
            f"{spec.expected_min_rows}..{spec.expected_max_rows}"
        )
    checks = {
        "required_columns": "passed",
        "duplicate_keys": "passed",
        "finite_numeric_values": "passed",
        "percentage_fraction_units": "passed",
        "expected_population": "passed",
    }
    return ValidationReport("structurally_checked", len(frame), checks, warnings)


def validate_general(
    frame: pd.DataFrame,
    keys: Iterable[str],
    required: Iterable[str] = (),
) -> ValidationReport:
    if frame.empty:
        raise ValidationError("A successful dataset cannot be empty")
    _require_columns(frame, required)
    _reject_duplicate_keys(frame, keys)
    _reject_nonfinite(frame)
    warnings = _check_fraction_units(frame)
    return ValidationReport(
        "structurally_checked",
        len(frame),
        {
            "required_columns": "passed",
            "duplicate_keys": "passed",
            "finite_numeric_values": "passed",
            "percentage_fraction_units": "passed",
        },
        warnings,
    )


def safe_percentage(makes: pd.Series, attempts: pd.Series) -> pd.Series:
    makes_numeric = pd.to_numeric(makes, errors="coerce")
    attempts_numeric = pd.to_numeric(attempts, errors="coerce")
    result = makes_numeric / attempts_numeric
    return result.where(attempts_numeric > 0)


def combined_percentage(frame: pd.DataFrame, makes: str, attempts: str) -> float:
    """Calculate a combined rate from summed makes/attempts, never mean percentages."""
    made = pd.to_numeric(frame[makes], errors="coerce").sum(min_count=1)
    attempted = pd.to_numeric(frame[attempts], errors="coerce").sum(min_count=1)
    if pd.isna(made) or pd.isna(attempted) or attempted <= 0:
        return float("nan")
    return float(made / attempted)
