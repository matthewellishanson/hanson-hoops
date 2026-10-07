from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    endpoint: str
    endpoint_class: str
    result_sets: tuple[str, ...]
    entity: str
    grain: str
    keys: tuple[str, ...]
    measure_type: str
    per_mode: str
    required_columns: tuple[str, ...]
    expected_min_rows: int
    expected_max_rows: int
    team_required: bool = False
    multi_level_headers: bool = False

    def nba_kwargs(self, season: str, season_type: str, team_id: str | None = None) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "season": season,
            "season_type_all_star": season_type,
            "league_id_nullable": "00",
            "timeout": 30,
            "get_request": False,
        }
        if self.endpoint == "leaguedashplayershotlocations":
            kwargs.update(
                distance_range="By Zone",
                measure_type_simple=self.measure_type,
                per_mode_detailed=self.per_mode,
            )
        else:
            kwargs.update(
                measure_type_detailed_defense=self.measure_type,
                per_mode_detailed=self.per_mode,
            )
        if self.team_required:
            if not team_id:
                raise ValueError(f"{self.name} requires an explicit team_id")
            kwargs["team_id"] = int(team_id)
        return kwargs


PLAYER_BASE_REQUIRED = (
    "PLAYER_ID", "PLAYER_NAME", "GP", "MIN", "FGM", "FGA", "FG_PCT",
    "FG3M", "FG3A", "FG3_PCT", "FTM", "FTA", "FT_PCT", "PTS",
)
TEAM_BASE_REQUIRED = (
    "TEAM_ID", "TEAM_NAME", "GP", "MIN", "FGM", "FGA", "FG_PCT",
    "FG3M", "FG3A", "FG3_PCT", "FTM", "FTA", "FT_PCT", "PTS",
)
ADVANCED_REQUIRED = ("GP", "MIN", "OFF_RATING", "DEF_RATING", "NET_RATING", "EFG_PCT", "TS_PCT", "PACE", "POSS")


DATASETS: dict[str, DatasetSpec] = {
    "player_base_totals": DatasetSpec(
        "player_base_totals", "leaguedashplayerstats", "LeagueDashPlayerStats",
        ("LeagueDashPlayerStats",), "player", "combined player x season",
        ("PLAYER_ID",), "Base", "Totals", PLAYER_BASE_REQUIRED, 400, 750,
    ),
    "player_base_per_game": DatasetSpec(
        "player_base_per_game", "leaguedashplayerstats", "LeagueDashPlayerStats",
        ("LeagueDashPlayerStats",), "player", "combined player x season",
        ("PLAYER_ID",), "Base", "PerGame", PLAYER_BASE_REQUIRED, 400, 750,
    ),
    "player_advanced": DatasetSpec(
        "player_advanced", "leaguedashplayerstats", "LeagueDashPlayerStats",
        ("LeagueDashPlayerStats",), "player", "combined player x season",
        ("PLAYER_ID",), "Advanced", "Totals", ("PLAYER_ID", "PLAYER_NAME") + ADVANCED_REQUIRED, 400, 750,
    ),
    "player_per100": DatasetSpec(
        "player_per100", "leaguedashplayerstats", "LeagueDashPlayerStats",
        ("LeagueDashPlayerStats",), "player", "combined player x season",
        ("PLAYER_ID",), "Base", "Per100Possessions", PLAYER_BASE_REQUIRED, 400, 750,
    ),
    "team_base_totals": DatasetSpec(
        "team_base_totals", "leaguedashteamstats", "LeagueDashTeamStats",
        ("LeagueDashTeamStats",), "team", "team x season", ("TEAM_ID",),
        "Base", "Totals", TEAM_BASE_REQUIRED, 30, 30,
    ),
    "team_base_per_game": DatasetSpec(
        "team_base_per_game", "leaguedashteamstats", "LeagueDashTeamStats",
        ("LeagueDashTeamStats",), "team", "team x season", ("TEAM_ID",),
        "Base", "PerGame", TEAM_BASE_REQUIRED, 30, 30,
    ),
    "team_advanced": DatasetSpec(
        "team_advanced", "leaguedashteamstats", "LeagueDashTeamStats",
        ("LeagueDashTeamStats",), "team", "team x season", ("TEAM_ID",),
        "Advanced", "Totals", ("TEAM_ID", "TEAM_NAME") + ADVANCED_REQUIRED, 30, 30,
    ),
    "team_per100": DatasetSpec(
        "team_per100", "leaguedashteamstats", "LeagueDashTeamStats",
        ("LeagueDashTeamStats",), "team", "team x season", ("TEAM_ID",),
        "Base", "Per100Possessions", TEAM_BASE_REQUIRED, 30, 30,
    ),
    "player_shot_zones": DatasetSpec(
        "player_shot_zones", "leaguedashplayershotlocations", "LeagueDashPlayerShotLocations",
        ("ShotLocations",), "player", "combined player x season", ("PLAYER_ID",),
        "Base", "Totals", ("PLAYER_ID", "PLAYER_NAME"), 300, 750, multi_level_headers=True,
    ),
    "player_on_off": DatasetSpec(
        "player_on_off", "teamplayeronoffsummary", "TeamPlayerOnOffSummary",
        ("PlayersOnCourtTeamPlayerOnOffSummary", "PlayersOffCourtTeamPlayerOnOffSummary"),
        "player_team", "player x team x season x on/off state",
        ("TEAM_ID", "VS_PLAYER_ID", "ON_OFF"), "Advanced", "Totals",
        ("TEAM_ID", "VS_PLAYER_ID", "VS_PLAYER_NAME", "MIN", "OFF_RATING", "DEF_RATING", "NET_RATING", "ON_OFF"),
        10, 80, team_required=True,
    ),
}


DERIVED_DATASETS = {
    "player_shooting": {
        "entity": "player",
        "grain": "combined player x season",
        "keys": ("PLAYER_ID",),
    },
    "team_shooting": {
        "entity": "team",
        "grain": "team x season",
        "keys": ("TEAM_ID",),
    },
}


def get_spec(name: str) -> DatasetSpec:
    try:
        return DATASETS[name]
    except KeyError as exc:
        choices = ", ".join(sorted(DATASETS))
        raise ValueError(f"Unknown acquired dataset {name!r}. Choose one of: {choices}") from exc
