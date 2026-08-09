from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=2)
def load_weights() -> dict:
    # Weight config is externalized so tuning does not require code edits.
    p = Path(__file__).resolve().with_name("weights.json")
    return json.loads(p.read_text(encoding="utf-8"))


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _weight_overrides(weights: dict, emphasis: dict[str, float]) -> dict[str, float]:
    # Apply user emphasis multipliers (offense/defense/etc.) to component weights.
    out = {}
    merged = {}
    merged.update(weights.get("coverage", {}))
    merged.update(weights.get("synergy", {}))
    merged.update(weights.get("clash", {}))

    cats = weights.get("category_components", {})
    for component, w in merged.items():
        m = 1.0
        for cat_name, components in cats.items():
            if component in components:
                m *= _clamp(float(emphasis.get(cat_name, 1.0)), 0.5, 1.8)
        out[component] = float(w) * m
    return out


def _confidence(a: dict, b: dict) -> dict:
    # Confidence is a data-quality proxy, not model certainty:
    # more minutes/games/volume => more stable profile estimates.
    min_a = float(a.get("MIN", 0.0))
    min_b = float(b.get("MIN", 0.0))
    gp_a = float(a.get("GP", 0.0))
    gp_b = float(b.get("GP", 0.0))
    fga_a = float(a.get("FGA_PER100", 0.0))
    fga_b = float(b.get("FGA_PER100", 0.0))

    min_factor = _clamp(min(min_a, min_b) / 1800.0, 0.0, 1.0)
    gp_factor = _clamp(min(gp_a, gp_b) / 65.0, 0.0, 1.0)
    vol_factor = _clamp((fga_a + fga_b) / 40.0, 0.0, 1.0)

    score = round((0.55 * min_factor + 0.30 * gp_factor + 0.15 * vol_factor) * 100.0, 1)
    if score >= 75:
        label = "high"
    elif score >= 55:
        label = "medium"
    else:
        label = "low"
    return {"score": score, "label": label}


def explain_risks(a: dict, b: dict) -> list[str]:
    # Human-readable flags are threshold-based so explanations stay deterministic.
    risks = []

    asp = float(a.get("AXIS_SPACING_GRAVITY", 0.0))
    bsp = float(b.get("AXIS_SPACING_GRAVITY", 0.0))
    if asp < 35 and bsp < 35:
        risks.append("Two non-spacers: both players grade below 35th percentile in spacing/gravity.")

    ac = float(a.get("AXIS_CREATION_LOAD", 0.0))
    bc = float(b.get("AXIS_CREATION_LOAD", 0.0))
    if ac > 75 and bc > 75:
        risks.append("High-usage overlap: both players carry heavy creation load.")

    abs_ = float(a.get("AXIS_BALL_SECURITY", 0.0))
    bbs = float(b.get("AXIS_BALL_SECURITY", 0.0))
    if abs_ < 40 and bbs < 40:
        risks.append("Turnover overload: both players score low on ball security.")

    ar = float(a.get("AXIS_RIM_PROTECTION", 0.0))
    br = float(b.get("AXIS_RIM_PROTECTION", 0.0))
    if ar < 30 and br < 30:
        risks.append("Low interior resistance: neither player projects as rim protection help.")

    areb = float(a.get("AXIS_REBOUNDING", 0.0))
    breb = float(b.get("AXIS_REBOUNDING", 0.0))
    if areb < 35 and breb < 35:
        risks.append("Glass risk: both players project below average in rebounding.")

    return risks[:3]


def score_pair(a: dict, b: dict, pair_features: dict, emphasis: dict[str, float]) -> dict:
    # Final score: weighted positives (coverage + synergy) minus weighted clashes.
    weights = load_weights()
    weighted = _weight_overrides(weights, emphasis)

    pos_components = {**weights.get("coverage", {}), **weights.get("synergy", {})}
    neg_components = weights.get("clash", {})

    contribs = []
    pos_sum = 0.0
    for c in pos_components:
        val = float(pair_features.get(c, 0.0))
        w = float(weighted.get(c, 0.0))
        contrib = (val * w) / 100.0
        pos_sum += contrib
        contribs.append({"component": c, "direction": "positive", "value": round(val, 1), "impact": round(contrib, 3)})

    neg_sum = 0.0
    for c in neg_components:
        val = float(pair_features.get(c, 0.0))
        w = float(weighted.get(c, 0.0))
        contrib = (val * w) / 100.0
        neg_sum += contrib
        contribs.append({"component": c, "direction": "negative", "value": round(val, 1), "impact": round(-contrib, 3)})

    raw = pos_sum - neg_sum
    # Center at 50 so neutral profiles land near the middle of the 0-100 scale.
    fit_score = round(_clamp(50.0 + (raw * 100.0) / 2.0, 0.0, 100.0), 1)

    pos_drivers = [c for c in contribs if c["impact"] > 0]
    neg_drivers = [c for c in contribs if c["impact"] < 0]
    pos_drivers.sort(key=lambda x: x["impact"], reverse=True)
    neg_drivers.sort(key=lambda x: x["impact"])

    return {
        "fit_score": fit_score,
        "confidence": _confidence(a, b),
        "drivers_positive": pos_drivers[:3],
        "drivers_negative": neg_drivers[:3],
        "risks": explain_risks(a, b),
        "weight_version": weights.get("version", "fit-unknown"),
    }
