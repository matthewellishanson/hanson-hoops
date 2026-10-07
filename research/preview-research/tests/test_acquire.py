from __future__ import annotations

from pathlib import Path

import pytest
import requests

from preview_research.acquire import AcquisitionError, acquire_dataset, import_csv, verify_endpoint_parameters
from preview_research.datasets import DATASETS
from preview_research.storage import ResearchStore, read_json


class FailingSession:
    def get(self, *_args, **_kwargs):
        raise requests.ReadTimeout("synthetic secret-bearing transport detail")


def test_installed_nba_api_signature_is_verified_without_network() -> None:
    spec = DATASETS["player_base_totals"]
    parameters, audit = verify_endpoint_parameters(spec, spec.nba_kwargs("2025-26", "Regular Season"))
    assert parameters["Season"] == "2025-26"
    assert parameters["SeasonType"] == "Regular Season"
    assert parameters["PerMode"] == "Totals"
    assert audit["nba_api_version"] == "1.10.1"


def test_failed_acquisition_records_unavailable_and_creates_no_table(tmp_path: Path) -> None:
    store = ResearchStore(tmp_path)
    with pytest.raises(AcquisitionError, match="No dataset was created"):
        acquire_dataset(
            "player_base_totals", "2025-26", "Regular Season",
            store=store, session=FailingSession(),
        )
    paths = store.paths("player_base_totals", "2025-26", "Regular Season")
    metadata = read_json(paths.raw_dir / "metadata.json")
    assert metadata["status"] == "unavailable"
    assert metadata["error_type"] == "ReadTimeout"
    assert not paths.processed_csv.exists()
    assert "synthetic" not in (paths.raw_dir / "metadata.json").read_text(encoding="utf-8")


def test_manual_import_copies_raw_source_and_keeps_provider_separate(tmp_path: Path) -> None:
    source = tmp_path / "outside.csv"
    source.write_text("Player,Tm,FG%\nExample,AAA,0.5\n", encoding="utf-8")
    store = ResearchStore(tmp_path / "project")
    frame, metadata = import_csv(
        source, "br_standard", "2025-26", "Regular Season",
        provider="basketball_reference", source="Basketball Reference Standard",
        source_url="https://example.test/source", grain="player x team stint x season",
        keys=["Player", "Tm"], row_scope="team_stint", store=store,
    )
    paths = store.paths("br_standard", "2025-26", "Regular Season", provider="basketball_reference")
    assert (paths.raw_dir / "source.csv").read_text(encoding="utf-8") == source.read_text(encoding="utf-8")
    assert frame.loc[0, "SOURCE_PROVIDER"] == "basketball_reference"
    assert metadata["row_scope"] == "team_stint"
