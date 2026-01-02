import pandas as pd
from pathlib import Path

OUT = Path("docs/data/rookie_shooting_stream.csv")

df = pd.read_csv("app/cache/rookie_snapshot.csv")

# Ensure numeric
for c in ["games","fga","fgm","fg3a","fg3m","fta","ftm"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")

df = df[df["games"] > 0].copy()

# Per-game at player level
df["fg_att_pg"]  = df["fga"]  / df["games"]
df["fg_mk_pg"]   = df["fgm"]  / df["games"]
df["fg_pct"]     = df["fg_pct"]

df["fg3_att_pg"] = df["fg3a"] / df["games"]
df["fg3_mk_pg"]  = df["fg3m"] / df["games"]
df["fg3_pct"]    = df["fg3_pct"]

df["ft_att_pg"]  = df["fta"]  / df["games"]
df["ft_mk_pg"]   = df["ftm"]  / df["games"]
df["ft_pct"]     = df["ft_pct"]

records = []

def build(df, shot, att, mk, pct):
    g = df.groupby(["rookie_season","position"])
    out = g[[att,mk,pct]].mean().reset_index()

    out = out.rename(columns={
        "rookie_season":"season",
        "position":"position_group",
        att:"attempts",
        mk:"makes",
        pct:"pct"
    })

    out = out.melt(
        id_vars=["season","position_group"],
        value_vars=["attempts","makes","pct"],
        var_name="metric",
        value_name="value"
    )

    out["shot_type"] = shot
    return out

records.append(build(df,"fg","fg_att_pg","fg_mk_pg","fg_pct"))
records.append(build(df,"3p","fg3_att_pg","fg3_mk_pg","fg3_pct"))
records.append(build(df,"ft","ft_att_pg","ft_mk_pg","ft_pct"))

final = pd.concat(records, ignore_index=True)
final = final.sort_values(["shot_type","position_group","season","metric"])

final.to_csv(OUT, index=False)
print("Saved →", OUT)
