import pandas as pd
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
STREAM_PATH = BACKEND_DIR / "docs" / "data" / "rookie_height_stream_wide.csv"
SNAPSHOT_PATH = BACKEND_DIR / "app" / "cache" / "rookie_snapshot.csv"
OUT_PATH = STREAM_PATH

def add_usage_to_height_stream(stream_path: Path = STREAM_PATH, snapshot_path: Path = SNAPSHOT_PATH, out_path: Path = OUT_PATH) -> pd.DataFrame:
    print(f"Loading wide height stream from {stream_path}")
    stream = pd.read_csv(stream_path)

    print(f"Loading rookie snapshot from {snapshot_path}")
    snap = pd.read_csv(snapshot_path)

    snap = snap.rename(
        columns={
            "rookie_season": "season",
            "height_in": "height_in",
            "position": "position_group",
            "usg_pct": "usage",
        }
    )

    snap = snap.dropna(subset=["usage"])

    usage_by_group = (
        snap.groupby(["season", "height_in", "position_group"])["usage"]
        .mean()
        .reset_index()
    )

    print("Merging usage onto height stream...")
    merged = stream.merge(
        usage_by_group,
        on=["season", "height_in", "position_group"],
        how="left",
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(out_path, index=False)
    print(f"Saved usage-enriched height stream to {out_path}")
    return merged


if __name__ == "__main__":
    add_usage_to_height_stream()
