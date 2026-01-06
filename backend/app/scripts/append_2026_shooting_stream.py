import pandas as pd

BASE = "docs/data/rookie_shooting_stream.csv"
SNAP = "docs/data/rookie_snapshot.csv"
OUT = BASE

print("Loading base...")
base = pd.read_csv(BASE)

# Remove any existing 2026 rows (idempotent)
base = base[base["season"] != 2026].copy()

print("Loading snapshot...")
snap = pd.read_csv(SNAP)

# --- Select 2026 rookies safely ---
rookies_2026 = snap.query("rookie_season == 2026 and games > 0").copy()

# Ensure position exists and fill missing so groupby won't drop rows
if "position" not in rookies_2026.columns:
    rookies_2026["position"] = "All"
else:
    rookies_2026["position"] = rookies_2026["position"].fillna("All")

print("2026 rookies found:", len(rookies_2026))

# --- Compute per-game shooting ---
for c in ["fga","fgm","fg3a","fg3m","fta","ftm","fg_pct","fg3_pct","ft_pct"]:
    rookies_2026[c] = pd.to_numeric(rookies_2026[c], errors="coerce")

rookies_2026["fg_att_pg"]  = rookies_2026.fga  / rookies_2026.games
rookies_2026["fg_mk_pg"]   = rookies_2026.fgm  / rookies_2026.games
rookies_2026["fg3_att_pg"] = rookies_2026.fg3a / rookies_2026.games
rookies_2026["fg3_mk_pg"]  = rookies_2026.fg3m / rookies_2026.games
rookies_2026["ft_att_pg"]  = rookies_2026.fta  / rookies_2026.games
rookies_2026["ft_mk_pg"]   = rookies_2026.ftm  / rookies_2026.games

# --- Build long-format shooting stream ---
def build(df, shot, att, mk, pct):
    out = (
        df.groupby(["rookie_season","position"], dropna=False)[[att,mk,pct]]
          .mean()
          .reset_index()
          .rename(columns={
              "rookie_season":"season",
              "position":"position_group",
              att:"attempts",
              mk:"makes",
              pct:"pct"
          })
          .melt(
              id_vars=["season","position_group"],
              value_vars=["attempts","makes","pct"],
              var_name="metric",
              value_name="value"
          )
    )
    out["shot_type"] = shot
    return out

append = pd.concat([
    build(rookies_2026,"fg","fg_att_pg","fg_mk_pg","fg_pct"),
    build(rookies_2026,"3p","fg3_att_pg","fg3_mk_pg","fg3_pct"),
    build(rookies_2026,"ft","ft_att_pg","ft_mk_pg","ft_pct"),
], ignore_index=True)

final = pd.concat([base, append], ignore_index=True)
final.to_csv(OUT, index=False)

print("Saved:", OUT)
print("2026 rows:", final.query("season == 2026").shape[0])
