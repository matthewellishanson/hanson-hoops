from __future__ import annotations


def _f(v: object) -> float:
    try:
        return float(v)
    except Exception:
        return 0.0


def build_pair_features(a: dict, b: dict, primary_handler: str = "auto") -> dict:
    # Build pair-level features from two axis profiles:
    # - coverage terms (max of pair),
    # - synergy interactions,
    # - clash penalties.
    ac = _f(a.get("AXIS_CREATION_LOAD"))
    bc = _f(b.get("AXIS_CREATION_LOAD"))
    asp = _f(a.get("AXIS_SPACING_GRAVITY"))
    bsp = _f(b.get("AXIS_SPACING_GRAVITY"))
    afin = _f(a.get("AXIS_FINISHING"))
    bfin = _f(b.get("AXIS_FINISHING"))
    aball = _f(a.get("AXIS_BALL_SECURITY"))
    bball = _f(b.get("AXIS_BALL_SECURITY"))
    adis = _f(a.get("AXIS_DISRUPTION"))
    bdis = _f(b.get("AXIS_DISRUPTION"))
    arim = _f(a.get("AXIS_RIM_PROTECTION"))
    brim = _f(b.get("AXIS_RIM_PROTECTION"))
    areb = _f(a.get("AXIS_REBOUNDING"))
    breb = _f(b.get("AXIS_REBOUNDING"))

    if primary_handler == "a":
        # Forced role assumption: player A as primary creator.
        creator_spacer = (ac * bsp) / 100.0
        creator_finisher = (ac * bfin) / 100.0
    elif primary_handler == "b":
        # Forced role assumption: player B as primary creator.
        creator_spacer = (bc * asp) / 100.0
        creator_finisher = (bc * afin) / 100.0
    else:
        # Auto mode averages both directional pairings.
        creator_spacer = (ac * bsp + bc * asp) / 200.0
        creator_finisher = (ac * bfin + bc * afin) / 200.0

    poa_rim = ((adis * brim) + (bdis * arim)) / 200.0
    rebounder_spacer = (areb * bsp + breb * asp) / 200.0

    usage_overlap = max(0.0, min(ac, bc) - 55.0) * 2.2
    double_non_spacer = max(0.0, 40.0 - asp) + max(0.0, 40.0 - bsp)
    turnover_overload = max(0.0, 50.0 - aball) + max(0.0, 50.0 - bball)

    return {
        "coverage_creation": max(ac, bc),
        "coverage_spacing": max(asp, bsp),
        "coverage_rim": max(arim, brim),
        "coverage_rebounding": max(areb, breb),
        "coverage_disruption": max(adis, bdis),
        "synergy_creator_spacer": max(0.0, min(100.0, creator_spacer)),
        "synergy_creator_finisher": max(0.0, min(100.0, creator_finisher)),
        "synergy_poa_rim": max(0.0, min(100.0, poa_rim)),
        "synergy_rebounder_spacer": max(0.0, min(100.0, rebounder_spacer)),
        "clash_usage_overlap": max(0.0, min(100.0, usage_overlap)),
        "clash_double_non_spacer": max(0.0, min(100.0, double_non_spacer)),
        "clash_turnover_overload": max(0.0, min(100.0, turnover_overload)),
    }
