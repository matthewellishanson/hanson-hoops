from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from .acquire import acquire_many, import_csv, import_nba_response
from .benchmarks import record_benchmark
from .config import ALLOWED_SEASON_TYPES, DEFAULT_SEASONS, DEFAULT_SEASON_TYPE
from .datasets import DATASETS, DERIVED_DATASETS
from .query import compare_entity, export_result, filter_rows, join_compatible, load_dataset, year_over_year
from .storage import ResearchStore
from .transform import build_shooting


def _csv_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _add_selection(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--season", action="append", dest="seasons", choices=DEFAULT_SEASONS)
    parser.add_argument("--season-type", default=DEFAULT_SEASON_TYPE, choices=ALLOWED_SEASON_TYPES)
    parser.add_argument("--team-id")
    parser.add_argument("--provider")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="preview-research",
        description="Cache-first NBA preview research. Query commands never use the network.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    listing = commands.add_parser("list-datasets", help="List supported NBA datasets")
    listing.set_defaults(handler=_list_datasets)

    acquire = commands.add_parser("acquire", help="Acquire broad NBA tables or one team on/off table")
    acquire.add_argument("--dataset", action="append", dest="datasets", choices=sorted(DATASETS), required=True)
    acquire.add_argument("--season", action="append", dest="seasons", choices=DEFAULT_SEASONS)
    acquire.add_argument("--season-type", default=DEFAULT_SEASON_TYPE, choices=ALLOWED_SEASON_TYPES)
    acquire.add_argument("--team-id")
    acquire.add_argument("--timeout", type=float, default=30)
    acquire.add_argument("--delay", type=float, default=1.0)
    acquire.add_argument("--force", action="store_true")
    acquire.set_defaults(handler=_acquire)

    imported = commands.add_parser("import-csv", help="Copy and register a manual public-source CSV")
    imported.add_argument("path", type=Path)
    imported.add_argument("--dataset", required=True)
    imported.add_argument("--season", required=True, choices=DEFAULT_SEASONS)
    imported.add_argument("--season-type", default=DEFAULT_SEASON_TYPE, choices=ALLOWED_SEASON_TYPES)
    imported.add_argument("--provider", required=True, help="e.g. basketball_reference")
    imported.add_argument("--source", required=True, help="Human-readable publication/table name")
    imported.add_argument("--source-url")
    imported.add_argument("--grain", required=True, help="e.g. player x team stint x season")
    imported.add_argument("--key", action="append", dest="keys", required=True)
    imported.add_argument("--row-scope", required=True, choices=("combined", "team_stint", "team", "other"))
    imported.set_defaults(handler=_import)

    imported_json = commands.add_parser("import-nba-json", help="Register and process a saved NBA endpoint JSON response")
    imported_json.add_argument("path", type=Path)
    imported_json.add_argument("--dataset", required=True, choices=sorted(DATASETS))
    imported_json.add_argument("--season", required=True, choices=DEFAULT_SEASONS)
    imported_json.add_argument("--season-type", default=DEFAULT_SEASON_TYPE, choices=ALLOWED_SEASON_TYPES)
    imported_json.add_argument("--team-id")
    imported_json.add_argument("--source", required=True)
    imported_json.add_argument("--source-metadata", type=Path)
    imported_json.set_defaults(handler=_import_nba_json)

    build = commands.add_parser("build-shooting", help="Build chart-ready shooting metrics from saved NBA tables")
    build.add_argument("--entity", choices=("player", "team"), required=True)
    build.add_argument("--season", action="append", dest="seasons", choices=DEFAULT_SEASONS)
    build.add_argument("--season-type", default=DEFAULT_SEASON_TYPE, choices=ALLOWED_SEASON_TYPES)
    build.set_defaults(handler=_build_shooting)

    query = commands.add_parser("query", help="Filter, sort, view, and export a cached table")
    _add_selection(query)
    query.add_argument("--where", action="append", default=[], help="Numeric condition such as MIN>=500")
    query.add_argument("--player")
    query.add_argument("--team")
    query.add_argument("--sort")
    query.add_argument("--descending", action="store_true")
    query.add_argument("--limit", type=int)
    query.add_argument("--columns", type=_csv_list)
    query.add_argument("--export", type=Path)
    query.add_argument("--note", default="")
    query.set_defaults(handler=_query)

    compare = commands.add_parser("compare", help="Compare one player or team across cached seasons")
    _add_selection(compare)
    compare.add_argument("--entity", required=True, help="Stable ID or exact player/team name")
    compare.add_argument("--id-column")
    compare.add_argument("--metrics", required=True, type=_csv_list)
    compare.add_argument("--export", type=Path)
    compare.set_defaults(handler=_compare)

    join = commands.add_parser("join", help="One-to-one join of compatible cached tables")
    join.add_argument("--left-dataset", required=True)
    join.add_argument("--right-dataset", required=True)
    join.add_argument("--season", action="append", dest="seasons", choices=DEFAULT_SEASONS)
    join.add_argument("--season-type", default=DEFAULT_SEASON_TYPE, choices=ALLOWED_SEASON_TYPES)
    join.add_argument("--left-provider")
    join.add_argument("--right-provider")
    join.add_argument("--left-team-id")
    join.add_argument("--right-team-id")
    join.add_argument("--keys", type=_csv_list)
    join.add_argument("--how", choices=("inner", "left", "right", "outer"), default="inner")
    join.add_argument("--where", action="append", default=[])
    join.add_argument("--sort")
    join.add_argument("--descending", action="store_true")
    join.add_argument("--limit", type=int)
    join.add_argument("--columns", type=_csv_list)
    join.add_argument("--export", type=Path)
    join.set_defaults(handler=_join)

    yoy = commands.add_parser("yoy", help="Calculate within-entity year-over-year arithmetic changes")
    _add_selection(yoy)
    yoy.add_argument("--metric", required=True)
    yoy.add_argument("--id-column")
    yoy.add_argument("--where", action="append", default=[])
    yoy.add_argument("--sort")
    yoy.add_argument("--descending", action="store_true")
    yoy.add_argument("--limit", type=int)
    yoy.add_argument("--columns", type=_csv_list)
    yoy.add_argument("--export", type=Path)
    yoy.set_defaults(handler=_yoy)

    coverage = commands.add_parser("coverage", help="Show local cache and validation coverage")
    coverage.set_defaults(handler=_coverage)

    benchmark = commands.add_parser("benchmark", help="Record an independent published benchmark check")
    _add_selection(benchmark)
    benchmark.add_argument("--column", required=True)
    benchmark.add_argument("--entity-column", required=True)
    benchmark.add_argument("--entity", required=True)
    benchmark.add_argument("--expected", required=True, type=float)
    benchmark.add_argument("--tolerance", default=0.0001, type=float)
    benchmark.add_argument("--source", required=True)
    benchmark.add_argument("--source-url", required=True)
    benchmark.set_defaults(handler=_benchmark)
    return parser


def _seasons(args: argparse.Namespace) -> list[str]:
    return args.seasons or list(DEFAULT_SEASONS)


def _display(frame: pd.DataFrame) -> None:
    if frame.empty:
        print("No matching rows.")
    else:
        with pd.option_context("display.max_rows", 40, "display.max_columns", 50, "display.width", 220):
            print(frame.to_string(index=False))


def _list_datasets(_args: argparse.Namespace) -> int:
    rows = []
    for spec in DATASETS.values():
        rows.append({
            "dataset": spec.name,
            "source": "NBA",
            "grain": spec.grain,
            "measure": spec.measure_type,
            "mode": spec.per_mode,
            "team_id_required": spec.team_required,
        })
    for name, spec in DERIVED_DATASETS.items():
        rows.append({"dataset": name, "source": "derived", "grain": spec["grain"], "measure": "shooting", "mode": "totals", "team_id_required": False})
    _display(pd.DataFrame(rows))
    return 0


def _acquire(args: argparse.Namespace) -> int:
    if "player_on_off" in args.datasets and not args.team_id:
        raise ValueError("player_on_off requires --team-id; team-specific requests are never silently combined")
    if args.team_id and any(dataset != "player_on_off" for dataset in args.datasets):
        raise ValueError("--team-id is currently reserved for player_on_off acquisitions")
    outcomes = acquire_many(
        args.datasets, _seasons(args), args.season_type, team_id=args.team_id,
        timeout=args.timeout, force=args.force, delay_seconds=args.delay,
    )
    _display(pd.DataFrame(outcomes))
    return 1 if any(item["status"] == "unavailable" for item in outcomes) else 0


def _import(args: argparse.Namespace) -> int:
    frame, metadata = import_csv(
        args.path, args.dataset, args.season, args.season_type,
        provider=args.provider, source=args.source, source_url=args.source_url,
        grain=args.grain, keys=args.keys, row_scope=args.row_scope,
    )
    print(json.dumps({"rows": len(frame), "status": metadata["validation_status"], "dataset": args.dataset}, indent=2))
    return 0


def _import_nba_json(args: argparse.Namespace) -> int:
    frame, metadata = import_nba_response(
        args.path, args.dataset, args.season, args.season_type,
        source=args.source, source_metadata_path=args.source_metadata,
        team_id=args.team_id,
    )
    print(json.dumps({"rows": len(frame), "status": metadata["validation_status"], "dataset": args.dataset}, indent=2))
    return 0


def _build_shooting(args: argparse.Namespace) -> int:
    outcomes = []
    for season in _seasons(args):
        frame, metadata = build_shooting(args.entity, season, args.season_type)
        outcomes.append({"dataset": metadata["dataset"], "season": season, "rows": len(frame), "status": metadata["validation_status"]})
    _display(pd.DataFrame(outcomes))
    return 0


def _load(args: argparse.Namespace):
    return load_dataset(
        args.dataset, _seasons(args), season_type=args.season_type,
        team_id=args.team_id, provider=args.provider,
    )


def _query(args: argparse.Namespace) -> int:
    result = filter_rows(
        _load(args), conditions=args.where, player=args.player, team=args.team,
        sort_by=args.sort, descending=args.descending, limit=args.limit,
        columns=args.columns,
    )
    _display(result.frame)
    if args.export:
        csv_path, note_path = export_result(result, args.export, notes=args.note)
        print(f"Exported {csv_path}")
        print(f"Wrote {note_path}")
    return 0


def _compare(args: argparse.Namespace) -> int:
    result = compare_entity(_load(args), args.entity, metrics=args.metrics, id_column=args.id_column)
    _display(result.frame)
    if args.export:
        csv_path, note_path = export_result(result, args.export)
        print(f"Exported {csv_path}")
        print(f"Wrote {note_path}")
    return 0


def _join(args: argparse.Namespace) -> int:
    seasons = _seasons(args)
    left = load_dataset(
        args.left_dataset, seasons, season_type=args.season_type,
        team_id=args.left_team_id, provider=args.left_provider,
    )
    right = load_dataset(
        args.right_dataset, seasons, season_type=args.season_type,
        team_id=args.right_team_id, provider=args.right_provider,
    )
    result = join_compatible(left, right, keys=args.keys, how=args.how)
    result = filter_rows(
        result, conditions=args.where, sort_by=args.sort,
        descending=args.descending, limit=args.limit, columns=args.columns,
    )
    _display(result.frame)
    if args.export:
        csv_path, note_path = export_result(result, args.export)
        print(f"Exported {csv_path}")
        print(f"Wrote {note_path}")
    return 0


def _yoy(args: argparse.Namespace) -> int:
    result = year_over_year(_load(args), args.metric, id_column=args.id_column)
    result = filter_rows(
        result, conditions=args.where, sort_by=args.sort,
        descending=args.descending, limit=args.limit, columns=args.columns,
    )
    _display(result.frame)
    if args.export:
        csv_path, note_path = export_result(result, args.export)
        print(f"Exported {csv_path}")
        print(f"Wrote {note_path}")
    return 0


def _coverage(_args: argparse.Namespace) -> int:
    store = ResearchStore()
    actual = store.coverage()
    rows = []
    for season in DEFAULT_SEASONS:
        for dataset in [*DATASETS, *DERIVED_DATASETS]:
            matches = actual[(actual["season"] == season) & (actual["dataset"] == dataset)] if not actual.empty else actual
            if matches.empty:
                rows.append({"season": season, "dataset": dataset, "status": "not_acquired", "benchmark": "not_checked", "rows": None, "team_id": None})
            else:
                rows.extend(matches[["season", "dataset", "status", "benchmark", "rows", "team_id"]].to_dict(orient="records"))
    _display(pd.DataFrame(rows))
    return 0


def _benchmark(args: argparse.Namespace) -> int:
    seasons = _seasons(args)
    if len(seasons) != 1:
        raise ValueError("benchmark requires exactly one --season")
    provider = args.provider or ("derived" if args.dataset in DERIVED_DATASETS else "nba")
    check = record_benchmark(
        args.dataset, seasons[0], args.season_type, column=args.column,
        entity_column=args.entity_column, entity=args.entity, expected=args.expected,
        tolerance=args.tolerance, source=args.source, source_url=args.source_url,
        team_id=args.team_id, provider=provider,
    )
    print(json.dumps(check, indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except (FileNotFoundError, KeyError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
