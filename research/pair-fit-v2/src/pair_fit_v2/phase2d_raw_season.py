"""Thin Phase 2D configuration for the shared historical raw-season engine."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from pair_fit_v2 import phase2c_raw_season as engine


SPEC = engine.HistoricalSeasonSpec(
    release_key="phase2d",
    phase_label="Phase 2D",
    target_season="2021-22",
    prior_feature_season="2020-21",
    manifest_version="phase2d.raw-season.v1",
    ledger_version="phase2d.attempt-ledger.v1",
    analysis_version="phase2d.release-audit.v1",
    asset_namespace="phase2d-raw-asset",
    manifest_namespace="phase2d-manifest",
    plan_version="phase2d.initial-plan.v1",
    allowlist_version="phase2d.live-allowlist.v1",
    provenance_format="phase2d-live-v1",
    request_kind="phase2d_live",
    prerequisite_key="phase2c_prerequisite",
    supported_classification=(
        "2021-22 raw release supported with population caveats; "
        "older historical expansion ready for separate planning"
    ),
    unresolved_classification="2021-22 request set complete; release audit unresolved",
    incomplete_classification="2021-22 raw acquisition incomplete; historical expansion blocked",
)


def build_expected_manifest(cache_root: Path) -> dict:
    return engine.build_expected_manifest(cache_root, SPEC)


def create_store(
    cache_root: Path, *, clock: Callable[[], str] | None = None
) -> engine.Phase2CStore:
    return engine.create_store(cache_root, clock=clock, spec=SPEC)


def manifest_path(cache_root: Path) -> Path:
    return engine.manifest_path(cache_root, SPEC)


def ledger_path(cache_root: Path) -> Path:
    return engine.ledger_path(cache_root, SPEC)


def plan_path(cache_root: Path) -> Path:
    return engine.plan_path(cache_root, SPEC)


def allowlist_path(cache_root: Path) -> Path:
    return engine.allowlist_path(cache_root, SPEC)


dry_run_plan = engine.dry_run_plan
persist_initial_plan = engine.persist_initial_plan
run_acquisition = engine.run_acquisition
analyze_release = engine.analyze_release
