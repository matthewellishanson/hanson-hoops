import pandas as pd
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[2]
LONG_PATH = BACKEND_DIR / "docs" / "data" / "rookie_height_stream.csv"
OUT_PATH = BACKEND_DIR / "docs" / "data" / "rookie_height_stream_wide.csv"


def build_rookie_height_stream_wide(long_path: Path = LONG_PATH, out_path: Path = OUT_PATH) -> pd.DataFrame:
    print(f"Loading long-format height stream from {long_path}")
    df = pd.read_csv(long_path)
    if df.empty:
        raise ValueError("Long height stream is empty")

    wide = (
        df.pivot_table(
            index=["season", "height", "position"],
            columns="stat",
            values="value",
            aggfunc="first",
        )
        .reset_index()
    )

    wide = wide.rename(
        columns={
            "height": "height_in",
            "position": "position_group",
            "avg_pick": "draft_number",
        }
    )

    for col in ["minutes", "count", "draft_number"]:
        if col in wide.columns:
            wide[col] = pd.to_numeric(wide[col], errors="coerce")

    wide = wide.sort_values(["season", "height_in", "position_group"])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    wide.to_csv(out_path, index=False)
    print(f"Saved wide height stream to {out_path} (rows={len(wide)})")
    return wide


if __name__ == "__main__":
    build_rookie_height_stream_wide()
