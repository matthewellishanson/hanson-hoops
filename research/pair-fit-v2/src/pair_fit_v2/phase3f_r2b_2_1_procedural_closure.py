"""Offline-only Phase 3F-R2B.2.1 procedural-closure specification.

This module verifies immutable checkpoint records, freezes bounded controls for
future protected transport, and writes deterministic JSON.  It deliberately
contains no HTTP client, endpoint URL, response acquisition, recovery request,
dataset construction, preprocessing, estimator, prediction, metric, or model
serialization capability.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


VERSION = "phase3f-r2b.2.1.procedural-closure.v1"
PHASE = "Phase 3F-R2B.2.1 - Protected-Acquisition Procedural Closure"
CLASSIFICATION = "PASS — Phase 3F-R2B.2.1 procedural closure complete; ready for read-only audit"
EXPECTED_BRANCH = "research/pair-fit-v2"
EXPECTED_HEAD = "1d98c20f41fe550deafa7e68cba611d7d66bf519"
R2B_STATUS = "FAILED — authorized protected acquisition attempt failed"
R2B1_CONTRACT_IDENTITY = "sha256:3d179b91ae36ad5e8c4f0bc928496695c18c4629e2a90f557ecc1ad3ccedbbad"
R2B2_GENERATED_CLASSIFICATION = (
    "CONDITIONAL PASS — acquisition complete; unresolved team evidence requires a separate checkpoint"
)
R2B2_RETAINED_CLASSIFICATION = (
    "CONDITIONAL PASS — acquisition evidence valid; narrow procedural correction required"
)
R2B2_AUTHORIZATION_SHA256 = "a3aed05f8bbda444d52b6019227f1831e9ec466541ff3cdb9e8297a701120c8c"
R2B2_AUTHORIZATION_BYTES = 78_108
R2B2_PLANNING = Path("planning/phase3f-r2b.2")
R2B2_EVIDENCE = Path("cache/phase3f-r2b.2/protected-final-target")
OUTPUT_NAMESPACE = Path("planning/phase3f-r2b.2.1")
ATLANTA_BODY = Path(
    "cache/phase3f-r2b/protected-final-target/1610612737-01-base/attempt-1-response.bin"
)
ATLANTA_BYTES = 51_905
ATLANTA_SHA256 = "e2134b18de903b79b1bcce8d628cf041ae18a50ccab00018d3b29b7daa63aff0"
ATLANTA_CANONICAL_SHA256 = "bac19c1df5f1a25de0e558c62410457917bb25ffb9130833e346444ae8c30f8d"

R2B2_ARTIFACTS = {
    "artifact_hashes.json": (1_926, "257651c2a5fe49ba292542862eb757b1ed5551d7a05542053a10d2a49da8a7d4"),
    "atlanta_offline_revalidation.json": (2_314, "18333d79b079005cb9d4951ad2c1a976c426f4d9f9c554d3c87214c66263be86"),
    "attempt_inventory.json": (100_569, "e007784a92958d1155dc88e146d0375a2c85f64fc6fb5b21d3cf83a8259b9a10"),
    "authorization.json": (R2B2_AUTHORIZATION_BYTES, R2B2_AUTHORIZATION_SHA256),
    "exact_250_inventory.json": (1_824, "ea183ad78133e22aee99be371107a3296d814385b9887cea3dbe6b2773e3ae97"),
    "global_reconciliation.json": (1_069, "d13133806d08893989cc19ccf85d78dea0a4f784b939b376de0859f6eff3474c"),
    "input_fingerprints.json": (9_506, "9eb3efee8ff924e3e275fe5f25bd2cb5d02c1d3325f7e71d58386a47e4440931"),
    "official_invocation.json": (1_052, "bd284af99c0baa837d79843113d45df48ce0f6baba27cb14839a5304a43a1a81"),
    "request_inventory.json": (58_173, "0f974738708aa78160d75826cc34c54ba5caa0cf4f78c51f8aa71301b69fe00b"),
    "response_fingerprints.json": (17_334, "bcee8a66c142f33ab77cc092eca2618e24a2af8e7a6942925e486204f69c5ec2"),
    "response_verifications.json": (668_760, "38ebee18d62c26516d120d51bc4a63bd02053cf5da5718c8618b7a297dee1b3d"),
    "structural_dispositions.json": (3_652, "3e771861882d4c413c6b1a42cb1501e447456ed5f8e2f66bbe5de485dd28a922"),
    "summary.json": (904, "00523960b2ce0f0f5c8431b04d96c1678f2376ee19ffc1b455a8cd41b04e0657"),
    "team_reconciliation.json": (25_504, "46f6413aff956bcf40d857d68f518df0133c56dca1b23861255586882e6fd936"),
}

R2B2_REVIEWED_FILES = {
    "PHASE3F_R2B_2_PROTECTED_ACQUISITION_CONTINUATION_POLICY.md": (8_171, "59ae8d0639e7256acbc1ab5b9c088a06c9b2f1a0c8b42d9a471f6711f1acb00e"),
    "PHASE3F_R2B_2_PROTECTED_ACQUISITION_CONTINUATION_REPORT.md": (29_624, "835540617266896e6f2eecddcf40a21f503f25da4217e4013988a4f3740adb5a"),
    "src/pair_fit_v2/phase3f_r2b_2_protected_acquisition_continuation.py": (48_758, "c3e5e9238b353e3ea6b482f1e0d50582494daa69cf6e297ee3cf4fac36288b86"),
    "src/pair_fit_v2/phase3f_r2b_2_cli.py": (1_691, "b77db180e3090a46c22a1b9a440bfd879fea6c298c9a57296afa6787d2fa2d18"),
    "tests/test_phase3f_r2b_2_protected_acquisition_continuation.py": (19_568, "2b842362f928c39a4cf279ba71b977b398c502ddbb58af157f36ac0cfb5dfb52"),
}

R2B1_ARTIFACTS = {
    "planning/phase3f-r2b.1/artifact_hashes.json": (698, "3350bce351b7d64ea0d46a55d17d83024ea65c4ba008aa652a672ff25cd0d79f"),
    "planning/phase3f-r2b.1/continuation_plan.json": (64_103, "8b30afae8e1035144153ea96d2510cc78e3b4572b03b28558edd73a0c1a56f18"),
    "planning/phase3f-r2b.1/input_fingerprints.json": (29_250, "dfc1115d139e153ee7011b1eb934355a4403b72b26579bc0e41782bc25c78267"),
    "planning/phase3f-r2b.1/response_contract.json": (11_940, "ecc3ecf1d547401539af8f8f640002fc3887de3dd64f1e80af1d41d62d04c49e"),
    "planning/phase3f-r2b.1/summary.json": (1_055, "d238fa41de8a15bc75e4d831c5498bdb2664f809af8b22335174c1dbe1a291da"),
}

FAILED_R2B_RECORDS = {
    "planning/phase3f-r2b/authorization.json": (71_656, "12249e6acca554507501e887c9afeb4f3cad0079fb40ab2738bea3d308ade856"),
    "planning/phase3f-r2b/official_invocation.json": (935, "936708826bbfaf729a1ad8c9ed7dcbbf2e8bce13b11e3e9a08403fe665b524fe"),
    "cache/phase3f-r2b/protected-final-target/1610612737-01-base/attempt-1-start.json": (281, "90553e18945c075aa285207d01821266930d3e9fcb79b84b9386b82bf741f9c9"),
    ATLANTA_BODY.as_posix(): (ATLANTA_BYTES, ATLANTA_SHA256),
    "cache/phase3f-r2b/protected-final-target/1610612737-01-base/attempt-1-outcome.json": (594, "c799c52fbb449c126edb669d5abcf003ae3703895f2734a7bd0d2a1c6db6d9cf"),
    "cache/phase3f-r2b/protected-final-target/1610612737-01-base/quarantine.json": (346, "affc98a8a1cba3158764085cc5811977c31f4a088f9dda5a412b65004f97986f"),
}

INDIANA = {
    "team": "Indiana Pacers",
    "team_id": "1610612754",
    "base": {
        "ordinal": 35,
        "rows": 250,
        "raw_sha256": "d0ec683e2879e8e58022114935b248f62531f88248c1e6a1374abca6def76bc3",
        "canonical_json_sha256": "0d55c4152259849055742855c5a156db935a2e12e77435a2b7b13d382ec945a5",
    },
    "advanced": {
        "ordinal": 36,
        "rows": 250,
        "raw_sha256": "45d6bf8a6fd7e1dcc1b47c5f3b52c278a1e0a8830a80a1a6b01d70e8e1a8faee",
        "canonical_json_sha256": "605e83bb954be19b6b52a29822c3dd6bfaf4f33e7fb5b483b61625aab1871120",
    },
}
MEMPHIS = {
    "team": "Memphis Grizzlies",
    "team_id": "1610612763",
    "base": {
        "ordinal": 53,
        "rows": 250,
        "raw_sha256": "540373cff09b3b5027144ef28a750a412408b23a01c56c7af256e309e2600b29",
        "canonical_json_sha256": "b562a30a8b188d73c6a66e5cd0851f028c0e1619245c01bb7fceb54d066eeccc",
    },
    "advanced": {
        "ordinal": 54,
        "rows": 250,
        "raw_sha256": "d7d59969325bc6731c057c7035f6629d2d28e079b6256c2fe87e83a386301fc6",
        "canonical_json_sha256": "2a7937fc2a54f855b39fa2cd92df1035c8ad9072bb2b8ab4b3ebcccccc4edfa3",
    },
}

OUTPUT_FILES = (
    "procedural_closure.json",
    "future_protected_transport_contract.json",
    "input_fingerprints.json",
    "summary.json",
    "artifact_hashes.json",
)


class ClosureError(RuntimeError):
    """A pinned input, future contract, path, source, or pacing rule failed."""


def serialize_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def strict_json_bytes(value: bytes) -> Any:
    def reject_constant(token: str) -> None:
        raise ValueError(f"non-finite JSON constant: {token}")

    return json.loads(value.decode("utf-8", errors="strict"), parse_constant=reject_constant)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_json(path: Path) -> Any:
    return strict_json_bytes(path.read_bytes())


def fingerprint(path: Path) -> dict[str, Any]:
    body = path.read_bytes()
    return {"bytes": len(body), "sha256": sha256_bytes(body)}


def write_once(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(content)
    except FileExistsError as exc:
        raise ClosureError(f"write-once output already exists: {path}") from exc


def _git(project_root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments], cwd=project_root, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def _verify_exact(project_root: Path, relative: str, expected: tuple[int, str]) -> dict[str, Any]:
    observed = fingerprint(project_root / relative)
    if observed != {"bytes": expected[0], "sha256": expected[1]}:
        raise ClosureError(f"pinned input differs: {relative}")
    return observed


def request_identity(request: Mapping[str, Any]) -> str:
    return sha256_bytes(
        canonical_json_bytes(
            {"endpoint": request.get("endpoint"), "parameters": request.get("parameters")}
        )
    )


def _seconds(value: str) -> float:
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).timestamp()


def _pacing_findings(attempts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    ordered = sorted(attempts, key=lambda item: item["ordinal"])
    completion_to_start = [
        _seconds(ordered[index]["started_at"]) - _seconds(ordered[index - 1]["completed_at"])
        for index in range(1, len(ordered))
    ]
    start_to_start = [
        _seconds(ordered[index]["started_at"]) - _seconds(ordered[index - 1]["started_at"])
        for index in range(1, len(ordered))
    ]
    completion_to_completion = [
        _seconds(ordered[index]["completed_at"]) - _seconds(ordered[index - 1]["completed_at"])
        for index in range(1, len(ordered))
    ]
    record = {
        "utc_completion_to_next_start": {
            "count": len(completion_to_start),
            "minimum_seconds": round(min(completion_to_start), 6),
            "maximum_seconds": round(max(completion_to_start), 6),
            "average_seconds": round(sum(completion_to_start) / len(completion_to_start), 6),
            "below_one_second_count": sum(value < 1.0 for value in completion_to_start),
        },
        "utc_start_to_next_start_minimum_seconds": round(min(start_to_start), 6),
        "utc_completion_to_next_completion_minimum_seconds": round(
            min(completion_to_completion), 6
        ),
        "absolute_monotonic_values_persisted": False,
        "sleep_records_persisted": False,
        "genuine_spacing_violation_established": False,
        "exact_completion_to_start_compliance": "strongly supported but not proved",
        "scientific_materiality": "nil",
    }
    expected = {
        "utc_completion_to_next_start": {
            "count": 58,
            "minimum_seconds": 0.986753,
            "maximum_seconds": 1.011286,
            "average_seconds": 1.002996,
            "below_one_second_count": 3,
        },
        "utc_start_to_next_start_minimum_seconds": 1.248367,
        "utc_completion_to_next_completion_minimum_seconds": 1.247101,
        "absolute_monotonic_values_persisted": False,
        "sleep_records_persisted": False,
        "genuine_spacing_violation_established": False,
        "exact_completion_to_start_compliance": "strongly supported but not proved",
        "scientific_materiality": "nil",
    }
    if record != expected:
        raise ClosureError("historical pacing findings differ from the audited record")
    return record


def verify_inputs(project_root: Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    if _git(root, "branch", "--show-current") != EXPECTED_BRANCH:
        raise ClosureError("unexpected branch")
    if _git(root, "rev-parse", "HEAD") != EXPECTED_HEAD:
        raise ClosureError("unexpected committed HEAD")

    inherited: dict[str, dict[str, Any]] = {}
    for relative, expected in {**R2B1_ARTIFACTS, **FAILED_R2B_RECORDS}.items():
        inherited[relative] = _verify_exact(root, relative, expected)
    reviewed = {
        relative: _verify_exact(root, relative, expected)
        for relative, expected in R2B2_REVIEWED_FILES.items()
    }
    artifacts = {
        name: _verify_exact(root, (R2B2_PLANNING / name).as_posix(), expected)
        for name, expected in R2B2_ARTIFACTS.items()
    }
    allowed_phase_namespaces = {
        root / "planning/phase3f-r2b.2",
        root / "planning/phase3f-r2b.2.1",
        root / "cache/phase3f-r2b.2",
    }
    unexpected_phase_namespaces = [
        path
        for parent in (root / "planning", root / "cache")
        for path in parent.iterdir()
        if path.is_dir()
        and path.name.startswith("phase3f-r2b.2")
        and path not in allowed_phase_namespaces
    ]
    if unexpected_phase_namespaces:
        raise ClosureError("unexpected R2B.2 recovery or alternate namespace exists")

    authorization = _read_json(root / R2B2_PLANNING / "authorization.json")
    requests = authorization.get("network_authorized_requests")
    if not isinstance(requests, list) or len(requests) != 59:
        raise ClosureError("R2B.2 authorization request count differs")
    if [item.get("ordinal") for item in requests] != list(range(2, 61)):
        raise ClosureError("R2B.2 authorization ordinals differ")
    if not all(item.get("currently_network_authorized") is False for item in requests):
        raise ClosureError("expected stale nested false flags are absent")
    if not all(
        item.get("may_become_eligible_only_in_later_separately_authorized_phase") is True
        for item in requests
    ):
        raise ClosureError("expected stale nested later-eligibility flags are absent")
    if any(item.get("canonical_identity_sha256") != request_identity(item) for item in requests):
        raise ClosureError("R2B.2 request identity drift detected")

    invocation = _read_json(root / R2B2_PLANNING / "official_invocation.json")
    if invocation.get("source_inventory") is not None:
        raise ClosureError("historical invocation unexpectedly contains a source inventory")
    source_path = root / "src/pair_fit_v2/phase3f_r2b_2_protected_acquisition_continuation.py"
    invocation_time = _seconds(invocation["recorded_at"])
    if source_path.stat().st_mtime <= invocation_time:
        raise ClosureError("current source last-write time is not later than the invocation")

    summary = _read_json(root / R2B2_PLANNING / "summary.json")
    if summary.get("classification") != R2B2_GENERATED_CLASSIFICATION:
        raise ClosureError("historical R2B.2 generated classification differs")
    if (
        summary.get("atlanta_network_attempt_count") != 0
        or summary.get("network_attempt_count") != 59
        or summary.get("completed_verified_request_count") != 59
        or summary.get("recovery_request_count") != 0
        or summary.get("final_test_dataset_constructed") is not False
        or summary.get("profile_join_occurred") is not False
        or summary.get("preprocessing_occurred") is not False
        or summary.get("estimator_or_prediction_or_metric_occurred") is not False
        or summary.get("model_artifact_created") is not False
    ):
        raise ClosureError("R2B.2 phase-boundary summary differs")

    global_record = _read_json(root / R2B2_PLANNING / "global_reconciliation.json")
    required_global = {
        "offline_revalidated_identities": 1,
        "new_completed_verified_requests": 59,
        "total_available_base_responses": 30,
        "total_available_advanced_responses": 30,
        "total_raw_base_rows": 5403,
        "total_raw_advanced_rows": 5403,
        "unique_team_canonical_pair_population": 5403,
        "failed_or_quarantined_continuation_identities": 0,
    }
    if any(global_record.get(key) != value for key, value in required_global.items()):
        raise ClosureError("R2B.2 global structural counts differ")
    if global_record.get("base_advanced_mismatch_teams") != []:
        raise ClosureError("R2B.2 key equality differs")
    if global_record.get("exact_250_unresolved_teams") != [INDIANA["team_id"], MEMPHIS["team_id"]]:
        raise ClosureError("R2B.2 exact-250 team inventory differs")

    teams = _read_json(root / R2B2_PLANNING / "team_reconciliation.json")
    if not isinstance(teams, list) or len(teams) != 30:
        raise ClosureError("R2B.2 team reconciliation count differs")
    if any(
        item.get("base_canonical_pair_count") != item.get("advanced_canonical_pair_count")
        or item.get("base_only_keys") != []
        or item.get("advanced_only_keys") != []
        for item in teams
    ):
        raise ClosureError("R2B.2 Base/Advanced key sets differ")
    by_team = {item["team_id"]: item for item in teams}
    for frozen_team in (INDIANA, MEMPHIS):
        item = by_team.get(frozen_team["team_id"])
        if (
            item is None
            or item.get("base_row_count") != 250
            or item.get("advanced_row_count") != 250
            or item.get("structural_disposition") != "exact_250_unresolved"
        ):
            raise ClosureError(f"exact-250 state differs: {frozen_team['team_id']}")

    attempts = _read_json(root / R2B2_PLANNING / "attempt_inventory.json")
    if not isinstance(attempts, list) or len(attempts) != 59:
        raise ClosureError("R2B.2 attempt inventory differs")
    body_inventory = []
    for attempt in attempts:
        if (
            attempt.get("state") != "completed_verified"
            or attempt.get("attempt_number") != 1
            or attempt.get("http_status") != 200
            or attempt.get("automatic_retries") != 0
            or attempt.get("redirected") is not False
        ):
            raise ClosureError(f"R2B.2 attempt state differs: {attempt.get('ordinal')}")
        records = attempt.get("records", {})
        response_record = records.get("response")
        verified_record = records.get("verified_body")
        if not isinstance(response_record, Mapping) or not isinstance(verified_record, Mapping):
            raise ClosureError("R2B.2 response record missing")
        raw_path = root / R2B2_EVIDENCE / response_record["path"]
        promoted_path = root / R2B2_EVIDENCE / verified_record["path"]
        raw = fingerprint(raw_path)
        promoted = fingerprint(promoted_path)
        expected = {"bytes": attempt["byte_count"], "sha256": attempt["raw_sha256"]}
        if raw != expected or promoted != expected:
            raise ClosureError(f"opaque response identity differs: {attempt['ordinal']}")
        body_inventory.append(
            {
                "ordinal": attempt["ordinal"],
                "request_id": attempt["request_id"],
                "relative_path": (R2B2_EVIDENCE / response_record["path"]).as_posix(),
                **raw,
            }
        )
    atlanta = _verify_exact(root, ATLANTA_BODY.as_posix(), (ATLANTA_BYTES, ATLANTA_SHA256))
    pacing = _pacing_findings(attempts)
    return {
        "failed_r2b_and_r2b1": dict(sorted(inherited.items())),
        "r2b2_reviewed_files": dict(sorted(reviewed.items())),
        "r2b2_artifacts": dict(sorted(artifacts.items())),
        "protected_response_bodies": body_inventory,
        "atlanta_body": {"path": ATLANTA_BODY.as_posix(), **atlanta},
        "r2b2_current_source_observation": {
            "path": source_path.relative_to(root).as_posix(),
            **fingerprint(source_path),
            "filesystem_last_write_utc": datetime.fromtimestamp(
                source_path.stat().st_mtime, timezone.utc
            ).isoformat().replace("+00:00", "Z"),
            "invocation_recorded_at": invocation["recorded_at"],
            "historical_executing_hash_persisted": False,
        },
        "historical_pacing": pacing,
        "unexpected_recovery_or_alternate_namespaces": [],
    }


PHASE_LOCAL_AUTHORIZATION_FIELDS = (
    "authorization_phase",
    "network_authorized",
    "attempt_limit",
    "ordinal",
    "request_id",
    "canonical_request_identity",
)
STALE_AUTHORIZATION_FIELDS = (
    "currently_network_authorized",
    "may_become_eligible_only_in_later_separately_authorized_phase",
)


def normalize_future_request(
    request: Mapping[str, Any], authorization_phase: str, ordinal: int, attempt_limit: int = 1
) -> dict[str, Any]:
    request_id = request.get("request_id")
    if not isinstance(request_id, str) or not request_id:
        raise ClosureError("future request ID must be a nonempty string")
    return {
        "endpoint": request.get("endpoint"),
        "parameters": dict(request.get("parameters", {})),
        "authorization": {
            "authorization_phase": authorization_phase,
            "network_authorized": True,
            "attempt_limit": attempt_limit,
            "ordinal": ordinal,
            "request_id": request_id,
            "canonical_request_identity": request_identity(request),
        },
    }


def validate_future_authorization(document: Mapping[str, Any]) -> list[dict[str, Any]]:
    phase = document.get("authorization_phase")
    attempt_limit = document.get("attempt_limit_per_identity")
    requests = document.get("requests")
    inventory = document.get("authorized_inventory")
    if not isinstance(phase, str) or not phase or attempt_limit != 1:
        raise ClosureError("future top-level authorization is malformed")
    if not isinstance(requests, list) or not isinstance(inventory, list) or len(requests) != len(inventory):
        raise ClosureError("future top-level and per-request inventories disagree")
    normalized_inventory = []
    for request in requests:
        if not isinstance(request, Mapping):
            raise ClosureError("future request entry is malformed")
        if any(field in request for field in STALE_AUTHORIZATION_FIELDS):
            raise ClosureError("inherited authorization-status fields are prohibited")
        authorization = request.get("authorization")
        if not isinstance(authorization, Mapping) or set(authorization) != set(PHASE_LOCAL_AUTHORIZATION_FIELDS):
            raise ClosureError("future request lacks the exact phase-local authorization object")
        if (
            authorization.get("authorization_phase") != phase
            or authorization.get("network_authorized") is not True
            or authorization.get("attempt_limit") != attempt_limit
            or not isinstance(authorization.get("ordinal"), int)
            or authorization.get("ordinal") <= 0
            or authorization.get("request_id") != request.get("request_id", authorization.get("request_id"))
        ):
            raise ClosureError("top-level and per-request authorization status disagree")
        identity = request_identity(request)
        if authorization.get("canonical_request_identity") != identity:
            raise ClosureError("future canonical request identity disagrees")
        normalized_inventory.append(dict(authorization))
    if normalized_inventory != inventory:
        raise ClosureError("top-level authorized inventory disagrees with request entries")
    ordinals = [item["ordinal"] for item in normalized_inventory]
    request_ids = [item["request_id"] for item in normalized_inventory]
    identities = [item["canonical_request_identity"] for item in normalized_inventory]
    if len(set(ordinals)) != len(ordinals) or len(set(request_ids)) != len(request_ids) or len(set(identities)) != len(identities):
        raise ClosureError("future authorization contains duplicate identity or ordinal")
    return [dict(item) for item in requests]


def _has_alias_component(path: Path) -> bool:
    current = path
    while True:
        try:
            if current.exists() and (
                current.is_symlink()
                or (hasattr(current, "is_junction") and current.is_junction())
            ):
                return True
        except OSError:
            return True
        if current.parent == current:
            return False
        current = current.parent


def canonical_namespace_path(value: Path | str) -> str:
    supplied = Path(value)
    if not supplied.is_absolute():
        raise ClosureError("future protected namespace must be an absolute path")
    raw = os.path.normcase(str(supplied))
    normalized = os.path.normcase(os.path.normpath(str(supplied)))
    if raw != normalized:
        raise ClosureError("path-normalization aliases are prohibited")
    if _has_alias_component(supplied):
        raise ClosureError("symlink or junction namespace substitution is prohibited")
    resolved = supplied.resolve(strict=False)
    if os.path.normcase(str(resolved)) != normalized:
        raise ClosureError("resolved namespace differs from its lexical path")
    return str(resolved)


def validate_namespace_binding(
    authorization: Mapping[str, Any],
    *,
    planning_dir: Path | str,
    evidence_dir: Path | str,
    source_evidence: Path | str,
) -> dict[str, str]:
    expected = authorization.get("canonical_namespaces")
    if not isinstance(expected, Mapping):
        raise ClosureError("future authorization lacks canonical namespaces")
    observed = {
        "planning": canonical_namespace_path(planning_dir),
        "evidence": canonical_namespace_path(evidence_dir),
        "source_evidence": canonical_namespace_path(source_evidence),
    }
    if dict(expected) != observed:
        raise ClosureError("supplied namespace differs from the frozen authorization")
    return observed


def fingerprint_source_inventory(paths: Sequence[Path | str]) -> list[dict[str, Any]]:
    output = []
    for value in paths:
        path = Path(value).resolve(strict=True)
        if not path.is_file():
            raise ClosureError(f"transport-controlling source is not a file: {path}")
        output.append({"canonical_path": str(path), **fingerprint(path)})
    return sorted(output, key=lambda item: item["canonical_path"])


def validate_source_inventory(expected: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    observed = fingerprint_source_inventory([item["canonical_path"] for item in expected])
    if observed != [dict(item) for item in expected]:
        raise ClosureError("transport-controlling source identity mismatch")
    return observed


def future_invocation_record(
    authorization: Mapping[str, Any],
    *,
    planning_dir: Path | str,
    evidence_dir: Path | str,
    source_evidence: Path | str,
    source_inventory: Sequence[Mapping[str, Any]],
    command: Sequence[str],
    python_executable: str,
    working_directory: str,
    pythonpath: str,
) -> dict[str, Any]:
    validate_future_authorization(authorization)
    namespaces = validate_namespace_binding(
        authorization,
        planning_dir=planning_dir,
        evidence_dir=evidence_dir,
        source_evidence=source_evidence,
    )
    verified_sources = validate_source_inventory(source_inventory)
    return {
        "authorization_sha256": sha256_bytes(serialize_json(authorization)),
        "verified_canonical_namespaces": namespaces,
        "verified_source_inventory": verified_sources,
        "command": list(command),
        "python_executable": python_executable,
        "working_directory": working_directory,
        "pythonpath": pythonpath,
    }


PACING_FIELDS = (
    "utc_start",
    "utc_completion",
    "process_monotonic_start",
    "process_monotonic_completion",
    "previous_monotonic_completion",
    "required_minimum_gap_seconds",
    "calculated_pre_attempt_gap_seconds",
    "requested_sleep_duration_seconds",
    "observed_post_sleep_monotonic_gap_seconds",
    "pacing_disposition",
    "enforcement_clock",
    "utc_role",
)


def enforce_monotonic_pacing(
    previous_completion: float | None,
    required_gap: float,
    *,
    monotonic: Callable[[], float],
    sleeper: Callable[[float], None],
    utc_start: str,
) -> dict[str, Any]:
    if not math.isfinite(required_gap) or required_gap < 0:
        raise ClosureError("required pacing gap must be finite and nonnegative")
    before = monotonic()
    pre_gap = None if previous_completion is None else before - previous_completion
    sleep_duration = 0.0 if pre_gap is None else max(0.0, required_gap - pre_gap)
    if sleep_duration:
        sleeper(sleep_duration)
    start = monotonic()
    post_gap = None if previous_completion is None else start - previous_completion
    if post_gap is not None and post_gap < required_gap:
        raise ClosureError("verified post-sleep monotonic gap remains below the threshold")
    return {
        "utc_start": utc_start,
        "utc_completion": None,
        "process_monotonic_start": start,
        "process_monotonic_completion": None,
        "previous_monotonic_completion": previous_completion,
        "required_minimum_gap_seconds": required_gap,
        "calculated_pre_attempt_gap_seconds": pre_gap,
        "requested_sleep_duration_seconds": sleep_duration,
        "observed_post_sleep_monotonic_gap_seconds": post_gap,
        "pacing_disposition": "passed",
        "enforcement_clock": "process_monotonic",
        "utc_role": "audit_context_only",
    }


def complete_timing_record(
    pacing_record: Mapping[str, Any], *, utc_completion: str, monotonic_completion: float
) -> dict[str, Any]:
    record = dict(pacing_record)
    if set(record) != set(PACING_FIELDS) or record.get("pacing_disposition") != "passed":
        raise ClosureError("pacing record is malformed")
    start = record.get("process_monotonic_start")
    if not isinstance(start, (int, float)) or monotonic_completion < start:
        raise ClosureError("monotonic completion precedes start")
    record["utc_completion"] = utc_completion
    record["process_monotonic_completion"] = monotonic_completion
    return record


def _procedural_closure(inputs: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "version": VERSION,
        "phase": PHASE,
        "classification": CLASSIFICATION,
        "historical_status": {
            "original_r2b": R2B_STATUS,
            "r2b1_authoritative_contract": R2B1_CONTRACT_IDENTITY,
            "r2b2_generated_classification_unchanged": R2B2_GENERATED_CLASSIFICATION,
            "r2b2_retained_audit_classification": R2B2_RETAINED_CLASSIFICATION,
            "r2b2_protected_evidence_valid": True,
            "r2b2_reacquisition_required": False,
            "r2b2_evidence_later_scientific_use_eligible_after_team_dispositions": True,
            "final_test_readiness_established": False,
            "model_execution_authorized": False,
        },
        "procedural_issues": {
            "contradictory_authorization_flags": {
                "top_level_authorized_identity_count": 59,
                "authorized_ordinals": [2, 60],
                "stale_nested_fields": {
                    "currently_network_authorized": False,
                    "may_become_eligible_only_in_later_separately_authorized_phase": True,
                },
                "affected_request_count": 59,
                "identity_parameter_or_order_drift": False,
                "finding": "machine-contract ambiguity, not evidence of an unauthorized endpoint or extra request",
                "historical_authorization_rewritten": False,
            },
            "namespace_binding": {
                "historical_cli_accepted_caller_selected_directories": True,
                "historical_exact_authorized_path_equality_proved": False,
                "alternate_execution_claimed": False,
            },
            "executing_source_identity": {
                "historical_source_bytes_pinned_by_authorization": False,
                "historical_source_inventory_in_invocation": False,
                "current_implementation_written_after_recorded_invocation": True,
                "historical_executing_hash_inferred_or_fabricated": False,
                "current_source_observation": inputs["r2b2_current_source_observation"],
            },
            "pacing_provenance": inputs["historical_pacing"],
        },
        "protected_evidence": {
            "response_bodies_intact": 60,
            "corrected_contract_satisfied": 60,
            "base_responses": 30,
            "advanced_responses": 30,
            "base_rows": 5403,
            "advanced_rows": 5403,
            "all_team_key_sets_equal": True,
            "recovery_requests": 0,
            "final_test_or_model_operations": 0,
        },
        "unresolved_teams": [
            {**INDIANA, "base_advanced_key_equality": True, "disposition": "exact_250_unresolved"},
            {**MEMPHIS, "base_advanced_key_equality": True, "disposition": "exact_250_unresolved"},
        ],
        "phase_boundary": {
            "network_authorization_count": 0,
            "transport_capability": False,
            "recovery_request_identities_created": 0,
            "protected_bodies_copied": 0,
            "row_level_data_written": 0,
            "final_test_rows_constructed": 0,
            "model_operations": 0,
        },
    }


def _future_contract() -> dict[str, Any]:
    return {
        "version": VERSION,
        "applies_to": "every later protected acquisition, including possible Indiana/Memphis recovery",
        "network_authorization_count": 0,
        "phase_local_request_authorization": {
            "required_fields": list(PHASE_LOCAL_AUTHORIZATION_FIELDS),
            "network_authorized_value_for_transport": True,
            "attempt_limit": 1,
            "inherited_status_fields_prohibited": list(STALE_AUTHORIZATION_FIELDS),
            "historical_metadata_exception": "allowed only inside an explicitly namespaced historical_metadata object",
            "reject_disagreement_across": [
                "top-level authorized inventory",
                "per-request authorization status",
                "attempt limit",
                "ordinal",
                "request identity",
                "canonical identity",
            ],
        },
        "namespace_binding": {
            "authorization_requires_exact_resolved_canonical_paths": [
                "planning namespace",
                "raw/attempt evidence namespace",
                "source-evidence reference",
            ],
            "cli_must_resolve_and_exactly_match": True,
            "relative_aliases_rejected": True,
            "symlink_or_junction_substitution_rejected_where_detectable": True,
            "alternate_root_or_normalization_ambiguity_rejected": True,
            "populated_partial_conflicting_failed_or_quarantined_state": "apply frozen restart behavior",
            "second_invocation_in_alternate_namespace": "reject before transport",
        },
        "executing_source_identity": {
            "pin_before_authorization": [
                "acquisition implementation module",
                "CLI module",
                "applicable policy or machine contract",
                "project-local modules directly controlling request identity, transport, verification, promotion, restart, or pacing",
            ],
            "fingerprint_fields": ["canonical_path", "bytes", "sha256"],
            "recompute_and_refuse_mismatch_at_invocation": True,
            "invocation_record_requires": [
                "verified source inventory",
                "exact command",
                "Python executable",
                "working directory",
                "PYTHONPATH",
            ],
            "post_execution_byte_identity_report_required": True,
            "scope": "transport-controlling project source only",
        },
        "monotonic_pacing": {
            "required_fields": list(PACING_FIELDS),
            "enforcement_clock": "time.monotonic or equivalent",
            "utc_role": "audit context only",
            "sleep_required_remainder": True,
            "recompute_after_sleep": True,
            "refuse_if_verified_gap_below_threshold": True,
            "persist_before_or_atomically_with_next_start": True,
            "sequential": True,
        },
        "restart_and_transport": {
            "one_attempt_per_identity": True,
            "automatic_retries": 0,
            "fail_stop": True,
            "historical_authorizations_modified": False,
            "r2b2_reacquisition_required": False,
        },
        "possible_future_recovery_specification_must_freeze": [
            "affected teams",
            "triggering full-season hashes",
            "exact season-boundary dates",
            "exact complementary nonoverlapping windows",
            "Base and Advanced request identities for each window",
            "corrected R2B.1 response contract",
            "authorization-consistency rules",
            "exact namespace binding",
            "executing-source hashes",
            "monotonic pacing records",
            "one attempt per identity",
            "zero retries",
            "fail-stop behavior",
            "no rating aggregation",
            "population-set reconciliation only",
        ],
        "not_selected_or_created_here": {
            "recovery_dates": True,
            "recovery_request_identities": True,
            "recovery_authorization": True,
            "final_test_population": True,
        },
    }


def build_procedural_closure(project_root: Path, output_dir: Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    destination = Path(output_dir)
    if not destination.is_absolute():
        destination = (root / destination).resolve()
    if destination.exists():
        raise ClosureError(f"write-once output namespace already exists: {destination}")
    inputs = verify_inputs(root)
    closure = _procedural_closure(inputs)
    future = _future_contract()
    summary = {
        "version": VERSION,
        "phase": PHASE,
        "classification": CLASSIFICATION,
        "original_r2b_status": R2B_STATUS,
        "r2b1_contract_identity": R2B1_CONTRACT_IDENTITY,
        "r2b2_retained_classification": R2B2_RETAINED_CLASSIFICATION,
        "verified_protected_response_count": 60,
        "unresolved_team_ids": [INDIANA["team_id"], MEMPHIS["team_id"]],
        "procedural_issue_count": 4,
        "future_control_family_count": 4,
        "network_requests": 0,
        "network_authorization_count": 0,
        "protected_bodies_copied": 0,
        "recovery_request_identities_created": 0,
        "final_test_rows_constructed": 0,
        "model_operations": 0,
        "ready_for": "read-only audit only",
    }
    values = {
        "procedural_closure.json": closure,
        "future_protected_transport_contract.json": future,
        "input_fingerprints.json": inputs,
        "summary.json": summary,
    }
    destination.mkdir(parents=True, exist_ok=False)
    try:
        for name, value in values.items():
            write_once(destination / name, serialize_json(value))
        manifest = {
            "version": VERSION,
            "artifact_inventory": list(OUTPUT_FILES),
            "sha256": {
                name: sha256_bytes((destination / name).read_bytes()) for name in values
            },
            "note": "artifact_hashes.json excludes itself to avoid a circular hash",
        }
        write_once(destination / "artifact_hashes.json", serialize_json(manifest))
    except Exception:
        # Preserve any partial write-once state for investigation.
        raise
    return summary


def import_canary() -> dict[str, Any]:
    """Return capability-boundary metadata without reading or writing checkpoint state."""

    return {
        "version": VERSION,
        "classification": CLASSIFICATION,
        "network_capability": False,
        "output_files": list(OUTPUT_FILES),
        "python_executable": sys.executable,
    }
