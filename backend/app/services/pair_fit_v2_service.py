"""Verified, load-once access to the audited Pair Fit v2 package."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from threading import Lock
from typing import Any


MODEL_VERSION = "pair-fit-v2.0.0"
EXPECTED_PACKAGE_HASHES = {
    "artifact_manifest.json": "71c2859cc06525bec989575eaf438afa70ab6c6862aa72599e29b6944cae1140",
    "metadata.json": "ebfb87d38266dcc6099e8ea7019c60109aa39058ddea737ab89e18cd61eb92e3",
    "model.json": "55a1386abb1abaadd78b29e8addafe1912f419c01586d239c81325ffc3f69302",
    "player_profiles.csv": "eb4534668fd3ddf57477e2989885d2dff5753506393463a4bedc6a31ad8c6265",
}


class PairFitPackageError(RuntimeError):
    """Raised when the production package cannot be trusted or loaded."""


def repository_root() -> Path:
    """Resolve the checkout root from this module, independent of process CWD."""
    return Path(__file__).resolve().parents[3]


def production_package_path() -> Path:
    return repository_root() / "research" / "pair-fit-v2" / "production" / MODEL_VERSION


def research_source_path() -> Path:
    return repository_root() / "research" / "pair-fit-v2" / "src"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_production_package(artifact_dir: Path | None = None) -> dict[str, Any]:
    """Verify exact inventory, the manifest, byte sizes, and frozen hashes."""
    package = Path(artifact_dir or production_package_path()).resolve()
    if not package.is_dir():
        raise PairFitPackageError(f"Pair Fit v2 package directory is missing: {package}")

    actual_inventory = {item.name for item in package.iterdir() if item.is_file()}
    expected_inventory = set(EXPECTED_PACKAGE_HASHES)
    if actual_inventory != expected_inventory:
        missing = sorted(expected_inventory - actual_inventory)
        unexpected = sorted(actual_inventory - expected_inventory)
        raise PairFitPackageError(
            f"Pair Fit v2 package inventory mismatch; missing={missing}, unexpected={unexpected}"
        )

    for name, expected_hash in EXPECTED_PACKAGE_HASHES.items():
        actual_hash = _sha256(package / name)
        if actual_hash != expected_hash:
            raise PairFitPackageError(
                f"Pair Fit v2 package hash mismatch for {name}: expected {expected_hash}, got {actual_hash}"
            )

    try:
        manifest = json.loads((package / "artifact_manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PairFitPackageError(f"Pair Fit v2 manifest is unreadable: {exc}") from exc

    if manifest.get("model_version") != MODEL_VERSION:
        raise PairFitPackageError("Pair Fit v2 manifest model version mismatch")
    manifest_files = manifest.get("files")
    expected_payloads = expected_inventory - {"artifact_manifest.json"}
    if not isinstance(manifest_files, dict) or set(manifest_files) != expected_payloads:
        raise PairFitPackageError("Pair Fit v2 manifest payload inventory mismatch")

    for name in sorted(expected_payloads):
        entry = manifest_files.get(name)
        path = package / name
        if not isinstance(entry, dict):
            raise PairFitPackageError(f"Pair Fit v2 manifest entry is invalid for {name}")
        if entry.get("sha256") != EXPECTED_PACKAGE_HASHES[name]:
            raise PairFitPackageError(f"Pair Fit v2 manifest hash entry mismatch for {name}")
        if entry.get("bytes") != path.stat().st_size:
            raise PairFitPackageError(f"Pair Fit v2 manifest byte count mismatch for {name}")

    return manifest


_predictor: Any | None = None
_predictor_lock = Lock()
_predictor_load_count = 0


def get_pair_fit_predictor() -> Any:
    """Return the process-wide predictor, loading and verifying it exactly once."""
    global _predictor, _predictor_load_count
    if _predictor is not None:
        return _predictor
    with _predictor_lock:
        if _predictor is not None:
            return _predictor

        package = production_package_path()
        verify_production_package(package)
        source = research_source_path()
        if not source.is_dir():
            raise PairFitPackageError(f"Pair Fit v2 inference source directory is missing: {source}")

        # The research project is intentionally not an installable distribution. Add
        # only its src root, resolved from this application file, so app startup works
        # the same from the repository root and from backend/.
        source_text = str(source)
        if source_text not in sys.path:
            sys.path.insert(0, source_text)
        try:
            from pair_fit_v2.inference import PairFitPredictor

            predictor = PairFitPredictor(package)
        except Exception as exc:
            raise PairFitPackageError(f"Pair Fit v2 predictor could not be loaded: {exc}") from exc

        _predictor = predictor
        _predictor_load_count += 1
        return _predictor


def predictor_load_count() -> int:
    """Expose the load count for runtime integrity tests and diagnostics."""
    return _predictor_load_count


def _reset_predictor_for_tests() -> None:
    global _predictor, _predictor_load_count
    with _predictor_lock:
        _predictor = None
        _predictor_load_count = 0
