import pandas as pd
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = BACKEND_DIR / "app" / "cache" / "rookie_snapshot.csv"
OUT_PATH = BACKEND_DIR / "docs" / "data" / "rookie_shooting_stream.csv"

REQUIRED_COLS = [
    "rookie_season",
    "position",
    "games",
    "fga",
    "fgm",
    "fg_pct",
    "fg3a",
    "fg3m",
    "fg3_pct",
    "fta",
    "ftm",
    "ft_pct",
]
NUMERIC_COLS = [
    "rookie_season",
    "games",
    "fga",
    "fgm",
    "fg_pct",
    "fg3a",
    "fg3m",
    "fg3_pct",
    "fta",
    "ftm",
    "ft_pct",
]


def require_columns(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Snapshot missing required columns: {missing}")


def build_rookie_shooting_stream(snapshot_path: Path = SNAPSHOT_PATH, out_path: Path = OUT_PATH) -> pd.DataFrame:
    print(f"Loading snapshot from {snapshot_path}")
    df = pd.read_csv(snapshot_path)
    require_columns(df)

    # Keep positions as strings and fill missing to avoid frontend nulls
    df["position"] = df["position"].fillna("Unknown").astype(str)

    for c in NUMERIC_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df[df.games > 0].copy()
    if df.empty:
        raise ValueError("No rows with games > 0 found in snapshot")

    df["fg_att_pg"] = df.fga / df.games
    df["fg_mk_pg"] = df.fgm / df.games
    df["fg3_att_pg"] = df.fg3a / df.games
    df["fg3_mk_pg"] = df.fg3m / df.games
    df["ft_att_pg"] = df.fta / df.games
    df["ft_mk_pg"] = df.ftm / df.games

    def build(df_in, shot, att, mk, pct):
        out = (
            df_in.groupby(["rookie_season", "position"], dropna=False)[[att, mk, pct]]
            .mean()
            .reset_index()
            .rename(
                columns={
                    "rookie_season": "season",
                    "position": "position_group",
                    att: "attempts",
                    mk: "makes",
                    pct: "pct",
                }
            )
            .melt(
                id_vars=["season", "position_group"],
                value_vars=["attempts", "makes", "pct"],
                var_name="metric",
                value_name="value",
            )
        )
        out["shot_type"] = shot
        return out

    final = pd.concat(
        [
            build(df, "fg", "fg_att_pg", "fg_mk_pg", "fg_pct"),
            build(df, "3p", "fg3_att_pg", "fg3_mk_pg", "fg3_pct"),
            build(df, "ft", "ft_att_pg", "ft_mk_pg", "ft_pct"),
        ],
        ignore_index=True,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(out_path, index=False)
    print(f"Saved shooting stream to {out_path} (rows={len(final)})")
    return final


if __name__ == "__main__":
    build_rookie_shooting_stream()
