import pandas as pd
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = BACKEND_DIR / "app" / "cache" / "rookie_snapshot.csv"
OUT_PATH = BACKEND_DIR / "docs" / "data" / "rookie_height_stream.csv"

REQUIRED_COLS = ["rookie_season", "height_in", "position", "minutes"]


def require_columns(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Snapshot missing required columns: {missing}")


def build_rookie_height_stream_long(snapshot_path: Path = SNAPSHOT_PATH, out_path: Path = OUT_PATH) -> pd.DataFrame:
    print(f"Loading snapshot from {snapshot_path}")
    df = pd.read_csv(snapshot_path)
    require_columns(df)

    df["height_bucket"] = pd.to_numeric(df["height_in"], errors="coerce").fillna(-1)
    df["minutes"] = pd.to_numeric(df["minutes"], errors="coerce")
    df = df.dropna(subset=["position", "rookie_season"])

    rows = []
    for (season, height, pos), g in df.groupby(["rookie_season", "height_bucket", "position"]):
        rows.append(
            {
                "season": season,
                "height": height,
                "position": pos,
                "stat": "minutes",
                "value": g["minutes"].sum(),
            }
        )
        rows.append(
            {
                "season": season,
                "height": height,
                "position": pos,
                "stat": "count",
                "value": g.shape[0],
            }
        )
        if "draft_number" in g.columns:
            rows.append(
                {
                    "season": season,
                    "height": height,
                    "position": pos,
                    "stat": "avg_pick",
                    "value": pd.to_numeric(g["draft_number"], errors="coerce").mean(),
                }
            )

    out = pd.DataFrame(rows)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)
    print(f"Saved long height stream to {out_path} (rows={len(out)})")
    return out


if __name__ == "__main__":
    build_rookie_height_stream_long()
