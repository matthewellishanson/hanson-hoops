from __future__ import annotations

import numpy as np
import pandas as pd


METRIC_COLUMNS = [
    "USG_PCT",
    "AST_PCT",
    "TOV_PCT",
    "PTS_PER100",
    "FGA_PER100",
    "FTAR",
    "FG3A_PER100",
    "FG3_PCT",
    "TS_PCT",
    "EFG_PCT",
    "STL_PER100",
    "BLK_PER100",
    "ORB_PCT",
    "DRB_PCT",
    "PF_PER100",
]


def _global_percentile(series: pd.Series) -> pd.Series:
    # League-wide percentile fallback for shrinkage when body-neighborhood is sparse.
    s = pd.to_numeric(series, errors="coerce")
    return (s.rank(pct=True).fillna(0.0) * 100.0).astype("float64")


def _row_percentile(values: np.ndarray, target: float) -> float:
    if values.size == 0 or np.isnan(target):
        return 0.0
    clean = values[~np.isnan(values)]
    if clean.size == 0:
        return 0.0
    return float((clean <= target).mean() * 100.0)


def body_based_percentiles(
    df: pd.DataFrame,
    metric_cols: list[str] | None = None,
    k_neighbors: int = 40,
    shrinkage_floor: int = 25,
) -> pd.DataFrame:
    # Compute "similar body type" percentiles using KNN in (height, weight) space.
    # Then blend local percentile with global percentile using sample-size shrinkage.
    metric_cols = metric_cols or METRIC_COLUMNS
    out = pd.DataFrame(index=df.index)

    h = pd.to_numeric(df["height_in"], errors="coerce").fillna(df["height_in"].median())
    w = pd.to_numeric(df["weight_lbs"], errors="coerce").fillna(df["weight_lbs"].median())

    body = np.column_stack([h.to_numpy(dtype=float), w.to_numpy(dtype=float)])
    mu = np.nanmean(body, axis=0)
    sigma = np.nanstd(body, axis=0)
    sigma = np.where(sigma == 0, 1.0, sigma)
    body_z = (body - mu) / sigma

    # N is typically small enough to use a dense pairwise distance matrix.
    dists = np.sqrt(((body_z[:, None, :] - body_z[None, :, :]) ** 2).sum(axis=2))
    neighbor_order = np.argsort(dists, axis=1)
    k = max(5, min(k_neighbors, len(df)))

    global_pcts = {m: _global_percentile(df[m]) for m in metric_cols if m in df.columns}

    for m in metric_cols:
        if m not in df.columns:
            out[f"{m}_PCTILE"] = 0.0
            continue

        vals = pd.to_numeric(df[m], errors="coerce").to_numpy(dtype=float)
        gp = global_pcts[m].to_numpy(dtype=float)
        local_blended = np.zeros(len(df), dtype=float)

        for i in range(len(df)):
            neigh_idx = neighbor_order[i, :k]
            neigh_vals = vals[neigh_idx]
            local = _row_percentile(neigh_vals, vals[i])
            n_valid = int(np.sum(~np.isnan(neigh_vals)))
            alpha = min(1.0, n_valid / float(max(1, shrinkage_floor)))
            local_blended[i] = alpha * local + (1.0 - alpha) * gp[i]

        out[f"{m}_PCTILE"] = np.clip(local_blended, 0.0, 100.0)

    return out
