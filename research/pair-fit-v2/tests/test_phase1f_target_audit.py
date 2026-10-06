from __future__ import annotations

import json
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pair_fit_v2.phase1f_target_audit import (
    ALL_RATING_FIELDS,
    analyze_cached_phase1f,
    field_availability,
    intervals_overlap,
    league_exposure_audit,
    omission_sensitivity,
    published_rounding_interval,
    rating_identity_audit,
    recomposition_audit,
    rounding_feasibility_classification,
    stability_audit,
    weighted_rounding_interval,
)


HEADERS = [
    "GROUP_ID",
    "GROUP_NAME",
    "POSS",
    "OFF_RATING",
    "DEF_RATING",
    "NET_RATING",
    "E_OFF_RATING",
    "E_DEF_RATING",
    "E_NET_RATING",
]


def row(
    pair=("1", "2"),
    poss=20,
    off=110.0,
    defense=100.0,
    net=10.0,
    e_off=109.0,
    e_def=101.0,
    e_net=8.0,
):
    return [
        f"-{pair[0]}-{pair[1]}-",
        f"P{pair[0]} - P{pair[1]}",
        poss,
        off,
        defense,
        net,
        e_off,
        e_def,
        e_net,
    ]


def payload(rows):
    return {
        "resultSets": [
            {"name": "Overall", "headers": ["TEAM_ID"], "rowSet": [[1]]},
            {"name": "Lineups", "headers": HEADERS, "rowSet": rows},
        ]
    }


def test_standard_and_estimated_rating_identity_checks_are_separate():
    data = payload([row(net=10.1, e_net=8.1)])
    standard = rating_identity_audit([data])
    estimated = rating_identity_audit([data], estimated=True)

    assert standard["fields"] == ["OFF_RATING", "DEF_RATING", "NET_RATING"]
    assert estimated["fields"] == ["E_OFF_RATING", "E_DEF_RATING", "E_NET_RATING"]
    assert standard["metrics"]["maximum_absolute_error"] == pytest.approx(0.1)
    assert estimated["metrics"]["maximum_absolute_error"] == pytest.approx(0.1)


def test_possession_weighted_recomposition_reports_complete_row_detail():
    early = payload([row(poss=10, off=100, defense=90, net=10)])
    late = payload([row(poss=30, off=120, defense=110, net=10)])
    full = payload([row(poss=40, off=115, defense=105, net=10)])

    result = recomposition_audit(full, early, late, fields=("OFF_RATING",))
    detail = result["OFF_RATING"]["details"][0]

    assert detail["early_possessions"] == 10
    assert detail["late_possessions"] == 30
    assert detail["recomposed_rate"] == 115
    assert detail["signed_error"] == 0


def test_zero_possession_window_is_preserved_but_excluded_from_rate_arithmetic():
    early = payload([row(poss=0, off=0)])
    late = payload([row(poss=20, off=111)])
    full = payload([row(poss=20, off=111)])

    detail = recomposition_audit(full, early, late, fields=("OFF_RATING",))[
        "OFF_RATING"
    ]["details"][0]

    assert detail["early_possessions"] == 0
    assert detail["late_possessions"] == 20
    assert detail["recomposed_rate"] == 111


def test_missing_estimated_field_is_counted_without_imputation():
    item = row()
    item[HEADERS.index("E_NET_RATING")] = None
    result = field_availability([payload([item])])

    assert result["fields"]["E_NET_RATING"] == {
        "numeric": 0,
        "missing_or_nonnumeric": 1,
    }
    assert result["fields"]["NET_RATING"]["numeric"] == 1


def test_rounding_intervals_and_overlap_are_deterministic():
    assert published_rounding_interval(100.0) == pytest.approx((99.95, 100.05))
    aggregate = weighted_rounding_interval([(1, 100.0), (3, 100.2)])
    assert aggregate == pytest.approx((100.1, 100.2))
    assert intervals_overlap(aggregate, (100.15, 100.25))


def test_rounding_discrepancy_classifications_respect_denominator_uncertainty():
    aggregate = (100.0, 100.1)
    full = (100.3, 100.4)

    assert rounding_feasibility_classification(
        field="OFF_RATING", aggregate_interval=aggregate, full_season_interval=full
    ) == "not_explainable_by_published_rounding"
    assert rounding_feasibility_classification(
        field="DEF_RATING", aggregate_interval=aggregate, full_season_interval=full
    ) == "indeterminate_due_to_missing_denominator_or_precision"
    assert rounding_feasibility_classification(
        field="E_OFF_RATING", aggregate_interval=aggregate, full_season_interval=full
    ) == "indeterminate_due_to_missing_denominator_or_precision"


def test_recomposition_exposure_bands_count_sparse_discrepancies():
    early = payload([row(("1", "2"), 2, off=100), row(("3", "4"), 60, off=100)])
    late = payload([row(("1", "2"), 3, off=100), row(("3", "4"), 60, off=100)])
    full = payload([row(("1", "2"), 5, off=101), row(("3", "4"), 120, off=100)])

    result = recomposition_audit(full, early, late, fields=("OFF_RATING",))[
        "OFF_RATING"
    ]
    by_band = {item["band"]: item for item in result["errors_by_total_possessions"]}

    assert by_band["0-9"]["comparable_rows"] == 1
    assert by_band["0-9"]["over_0_2_count"] == 1
    assert by_band["100-199"]["over_0_2_count"] == 0


def test_stability_metrics_include_pearson_spearman_and_sign_agreement():
    early = payload(
        [
            row(("1", "2"), 20, net=-5),
            row(("3", "4"), 30, net=5),
            row(("5", "6"), 40, net=15),
        ]
    )
    late = payload(
        [
            row(("1", "2"), 20, net=-4),
            row(("3", "4"), 30, net=6),
            row(("5", "6"), 40, net=14),
        ]
    )

    result = stability_audit(
        early, late, thresholds=(1,), fields=("NET_RATING",)
    )["rows"][0]

    assert result["qualifying_pair_count"] == 3
    assert result["pearson_correlation"] == pytest.approx(0.9979487158)
    assert result["spearman_correlation"] == 1
    assert result["sign_agreement"] == 1


def test_undefined_correlation_is_recorded_instead_of_fabricated():
    early = payload([row(("1", "2"), 20), row(("3", "4"), 20)])
    late = payload([row(("1", "2"), 20), row(("3", "4"), 20)])

    result = stability_audit(
        early, late, thresholds=(1,), fields=("OFF_RATING",)
    )["rows"][0]

    assert result["pearson_correlation"] is None
    assert result["spearman_correlation"] is None
    assert result["correlation_undefined_reason"] == "zero_variance"
    assert result["sample_too_small_to_interpret_responsibly"] is True


def test_league_exposure_thresholds_and_extreme_bands():
    first = payload([row(("1", "2"), 2, net=100), row(("3", "4"), 20, net=30)])
    second = payload([row(("5", "6"), 200, net=5)])

    result = league_exposure_audit({"1": first, "2": second}, thresholds=(1, 10, 100))
    thresholds = {item["threshold_possessions"]: item for item in result["thresholds"]}
    bands = {item["band"]: item for item in result["bands"]}

    assert thresholds[10]["rows_retained"] == 2
    assert thresholds[100]["rows_retained"] == 1
    assert bands["0-9"]["absolute_net_at_least_50_count"] == 1
    assert bands["200-499"]["absolute_net_at_least_50_count"] == 0


def test_known_omission_sensitivity_uses_bounded_language():
    full = payload([row(("1", "2"), 100)])
    union = [
        {"pair_ids": ("1", "2"), "advanced_possessions": 100},
        {"pair_ids": ("3", "4"), "advanced_possessions": 6},
    ]
    omitted = [union[1]]

    result = omission_sensitivity(full, omitted, union, thresholds=(5, 10))

    assert result[0]["known_recovered_only_pairs_retained"] == 1
    assert result[1]["bounded_statement"] == "no known omission survives this threshold"
    assert "exhaustive" not in result[1]["bounded_statement"]


def test_all_six_fields_are_explicitly_audited():
    result = field_availability([payload([row()])])
    assert tuple(result["fields"]) == ALL_RATING_FIELDS


def test_phase1f_module_has_no_transport_surface():
    import pair_fit_v2.phase1f_target_audit as module

    assert not hasattr(module, "requests")
    assert not hasattr(module, "transport")


def test_immutable_cache_replay_and_analysis_are_deterministic_and_network_blocked(
    monkeypatch,
):
    cache_root = Path(__file__).resolve().parents[1] / "cache"

    def forbidden(*args, **kwargs):
        raise AssertionError("Phase 1F attempted network access")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    try:
        import requests

        monkeypatch.setattr(requests.sessions.Session, "request", forbidden)
    except ImportError:
        pass

    first = analyze_cached_phase1f(cache_root)
    second = analyze_cached_phase1f(cache_root)

    assert first["summary_sha256"] == second["summary_sha256"]
    assert first["immutable_replay"]["unchanged"] is True
    assert first["immutable_replay"]["phase1c"]["asset_count"] == 60
    assert first["immutable_replay"]["phase1c"]["totals"]["matched_pairs"] == 5297
    assert first["immutable_replay"]["phase1d"]["classification"] == "proven_non_exhaustive"
    assert first["immutable_replay"]["phase1e"]["union"]["unique_recovered_pair_keys"] == 257
    assert first["availability"]["phase1c_all_teams"]["row_count"] == 5297
