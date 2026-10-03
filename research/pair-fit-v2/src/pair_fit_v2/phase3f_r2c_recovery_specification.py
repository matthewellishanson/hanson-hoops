"""Phase 3F-R2C exact-250 recovery specification and public-source evidence.

The only transport implemented here is one allowlisted, non-protected GET of
the official NBA Communications schedule-release page.  Recovery identities
are data only: this module cannot execute a TeamDashLineups request, construct
a final-test dataset, or perform a model operation.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from pair_fit_v2.direct_fetch import RESEARCH_HEADERS


VERSION = "phase3f-r2c.exact-250-recovery-specification.v1"
CLASSIFICATION = "PASS — Phase 3F-R2C exact-250 recovery specification frozen; ready for read-only audit"
EXPECTED_BRANCH = "research/pair-fit-v2"
EXPECTED_HEAD = "d233b71749104dcc494fbc979a4c83e86e1054ff"
PUBLIC_URL = "https://pr.nba.com/2025-26-nba-regular-season-schedule/"
PUBLIC_METHOD = "GET"
PUBLIC_SOURCE_NAMESPACE = Path("cache/phase3f-r2c-public-source")
PLANNING_NAMESPACE = Path("planning/phase3f-r2c")
FUTURE_PROTECTED_NAMESPACE = Path("cache/phase3f-r2c-protected-recovery")
PUBLIC_FILES = (
    "authorization-request.json",
    "attempt-1-start.json",
    "attempt-1-outcome.json",
    "response.html",
    "verified-source-summary.json",
)
PLANNING_FILES = ("recovery_plan.json", "artifact_hashes.json", "summary.json")
SEASON_START = date(2025, 10, 21)
SEASON_END = date(2026, 4, 12)
WINDOWS = (
    {"name": "early", "DateFrom": "2025-10-21", "DateTo": "2026-01-31"},
    {"name": "late", "DateFrom": "2026-02-01", "DateTo": "2026-04-12"},
)
ESTABLISHED_PARAMETER_DEFAULTS = {
    "GameID": "", "GameSegment": "", "LastNGames": "0", "LeagueID": "00",
    "Location": "", "Month": "0", "OpponentTeamID": "0", "Outcome": "",
    "PORound": "", "PaceAdjust": "N", "Period": "0", "PlusMinus": "N",
    "Rank": "N", "SeasonSegment": "", "ShotClockRange": "",
    "VsConference": "", "VsDivision": "",
}
R2B1_CONTRACT_IDENTITY = "sha256:3d179b91ae36ad5e8c4f0bc928496695c18c4629e2a90f557ecc1ad3ccedbbad"
R2B21_TRANSPORT_SHA256 = "20a557152730df7a90e9eba530d4a16de09ee4821c9fecf35bba8d206f9df234"
R2B21_TRANSPORT_PATH = Path("planning/phase3f-r2b.2.1/future_protected_transport_contract.json")
R2B2_REQUESTS_PATH = Path("planning/phase3f-r2b.2/request_inventory.json")
R2B2_EXACT_250_PATH = Path("planning/phase3f-r2b.2/exact_250_inventory.json")
R2B1_CONTRACT_PATH = Path("planning/phase3f-r2b.1/response_contract.json")
HISTORICAL_NAMESPACES = (
    Path("planning/phase3f-r2b"),
    Path("planning/phase3f-r2b.1"),
    Path("planning/phase3f-r2b.2"),
    Path("planning/phase3f-r2b.2.1"),
    Path("cache/phase3f-r2b"),
    Path("cache/phase3f-r2b.2"),
)
TEAM_SPECS = (
    {
        "team_id": "1610612754",
        "team_name": "Indiana Pacers",
        "base": {"ordinal": 35, "request_id": "teamdashlineups:1610612754:base", "bytes": 65800,
                 "raw_sha256": "d0ec683e2879e8e58022114935b248f62531f88248c1e6a1374abca6def76bc3",
                 "canonical_json_sha256": "0d55c4152259849055742855c5a156db935a2e12e77435a2b7b13d382ec945a5"},
        "advanced": {"ordinal": 36, "request_id": "teamdashlineups:1610612754:advanced", "bytes": 67740,
                     "raw_sha256": "45d6bf8a6fd7e1dcc1b47c5f3b52c278a1e0a8830a80a1a6b01d70e8e1a8faee",
                     "canonical_json_sha256": "605e83bb954be19b6b52a29822c3dd6bfaf4f33e7fb5b483b61625aab1871120"},
    },
    {
        "team_id": "1610612763",
        "team_name": "Memphis Grizzlies",
        "base": {"ordinal": 53, "request_id": "teamdashlineups:1610612763:base", "bytes": 66452,
                 "raw_sha256": "540373cff09b3b5027144ef28a750a412408b23a01c56c7af256e309e2600b29",
                 "canonical_json_sha256": "b562a30a8b188d73c6a66e5cd0851f028c0e1619245c01bb7fceb54d066eeccc"},
        "advanced": {"ordinal": 54, "request_id": "teamdashlineups:1610612763:advanced", "bytes": 68221,
                     "raw_sha256": "d7d59969325bc6731c057c7035f6629d2d28e079b6256c2fe87e83a386301fc6",
                     "canonical_json_sha256": "2a7937fc2a54f855b39fa2cd92df1035c8ad9072bb2b8ab4b3ebcccccc4edfa3"},
    },
)


class SpecificationError(RuntimeError):
    """Raised for a contract, evidence, or write-once violation."""


class SourceVerificationError(SpecificationError):
    """Raised when the one permitted public response is not authoritative."""


class PairPopulationError(SpecificationError):
    """Raised when pair-population input is malformed or contradictory."""

    def __init__(self, message: str, diagnostics: Mapping[str, int]):
        super().__init__(message)
        self.diagnostics = dict(diagnostics)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_json(path: Path) -> Any:
    def reject(token: str) -> None:
        raise ValueError(f"non-finite JSON token: {token}")
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=reject)


def _write_once(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(body)
    except FileExistsError as exc:
        raise SpecificationError(f"refusing to overwrite official artifact: {path}") from exc


def _require_absent_namespace(path: Path) -> None:
    if path.exists() or path.is_symlink():
        raise SpecificationError(f"official namespace already exists or is partial: {path}")


def validate_public_request(*, url: str, method: str = "GET", allow_redirects: bool = False,
                            automatic_retries: int = 0, attempt_number: int = 1,
                            fallback_urls: Sequence[str] = ()) -> None:
    if url != PUBLIC_URL:
        raise SpecificationError("public URL is not the exact allowlisted URL")
    if method != PUBLIC_METHOD:
        raise SpecificationError("only HTTP GET is permitted")
    if allow_redirects:
        raise SpecificationError("redirects are prohibited")
    if automatic_retries != 0:
        raise SpecificationError("automatic retries are prohibited")
    if attempt_number != 1:
        raise SpecificationError("a second public-source request is prohibited")
    if fallback_urls:
        raise SpecificationError("fallback or substitute URLs are prohibited")


class _SourceHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.title: list[str] = []
        self.in_title = False
        self.publication_date: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value for key, value in attrs if value is not None}
        if tag.lower() == "title":
            self.in_title = True
        if tag.lower() == "meta":
            identity = (values.get("property") or values.get("name") or values.get("itemprop") or "").lower()
            if identity in {"article:published_time", "date", "datepublished", "publish-date"}:
                self.publication_date = self.publication_date or values.get("content")
        if tag.lower() == "time" and self.publication_date is None:
            self.publication_date = values.get("datetime")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        self.text.append(data)
        if self.in_title:
            self.title.append(data)


def extract_verified_source(body: bytes, *, content_type: str) -> dict[str, Any]:
    lowered_type = content_type.lower()
    if not (lowered_type.startswith("text/") or "html" in lowered_type):
        raise SourceVerificationError("public response is not HTML/text")
    text = body.decode("utf-8", errors="replace")
    parser = _SourceHTMLParser()
    parser.feed(text)
    visible = re.sub(r"\s+", " ", " ".join(parser.text)).strip()
    start_match = re.search(r"[^.!?]{0,220}\b(?:Oct(?:ober)?\.?\s+21,\s+2025|October\s+21,\s+2025)[^.!?]{0,220}[.!?]", visible, re.I)
    end_match = re.search(r"[^.!?]{0,220}\bApril\s+12,\s+2026[^.!?]{0,220}[.!?]", visible, re.I)
    if start_match is None:
        raise SourceVerificationError("season-start boundary statement is absent")
    if end_match is None:
        raise SourceVerificationError("season-end boundary statement is absent")
    combined = f"{start_match.group(0)} {end_match.group(0)}".lower()
    if "regular season" not in combined or not any(word in combined for word in ("begin", "start", "tip", "open")):
        raise SourceVerificationError("start date is not identified as a regular-season boundary")
    if not any(word in combined for word in ("conclude", "end", "final")):
        raise SourceVerificationError("end date is not identified as a regular-season boundary")
    title = re.sub(r"\s+", " ", " ".join(parser.title)).strip()
    if not title or "nba" not in title.lower() or "2025-26" not in title:
        raise SourceVerificationError("unexpected official page identity")
    return {
        "page_title": title,
        "publication_date": parser.publication_date,
        "season_start": SEASON_START.isoformat(),
        "season_end": SEASON_END.isoformat(),
        "start_boundary_statement": start_match.group(0).strip(),
        "end_boundary_statement": end_match.group(0).strip(),
    }


def create_public_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    session.headers.update(RESEARCH_HEADERS)
    no_retry = Retry(total=0, connect=0, read=0, redirect=0, status=0, other=0)
    adapter = HTTPAdapter(max_retries=no_retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def acquire_public_source(output_dir: Path, *, session_factory: Callable[[], requests.Session] = create_public_session,
                          clock: Callable[[], str] = utc_now) -> dict[str, Any]:
    output_dir = Path(output_dir)
    _require_absent_namespace(output_dir)
    validate_public_request(url=PUBLIC_URL)
    authorization = {
        "version": VERSION, "authorized_attempts": 1, "automatic_retries": 0,
        "fallback_urls": [], "method": PUBLIC_METHOD, "redirects_allowed": False,
        "timeout_seconds": 30, "trust_env": False, "url": PUBLIC_URL,
        "purpose": "verify only the 2025-26 NBA regular-season start and end boundaries",
        "protected_pair_requests_authorized": 0,
    }
    started_at = clock()
    start = {"version": VERSION, "attempt_number": 1, "method": PUBLIC_METHOD,
             "url": PUBLIC_URL, "started_at": started_at}
    # Validate both records completely before the first official write.
    canonical_json(authorization)
    canonical_json(start)
    _write_once(output_dir / PUBLIC_FILES[0], canonical_json(authorization))
    _write_once(output_dir / PUBLIC_FILES[1], canonical_json(start))
    session = session_factory()
    response: requests.Response | None = None
    try:
        if session.trust_env:
            raise SpecificationError("public session must use trust_env=False")
        response = session.get(PUBLIC_URL, timeout=30, allow_redirects=False)
        body = response.content
        _write_once(output_dir / PUBLIC_FILES[3], body)
        redirected = bool(response.history or response.is_redirect or response.is_permanent_redirect or 300 <= response.status_code < 400)
        content_type = response.headers.get("Content-Type", "")
        if redirected or response.headers.get("Location"):
            raise SourceVerificationError("redirect response is prohibited")
        if response.status_code != 200:
            raise SourceVerificationError(f"expected HTTP 200, received {response.status_code}")
        extracted = extract_verified_source(body, content_type=content_type)
        completed_at = clock()
        outcome = {
            "version": VERSION, "attempt_number": 1, "state": "completed_verified",
            "completed_at": completed_at, "http_status": response.status_code,
            "redirected": False, "automatic_retries": 0, "byte_count": len(body),
            "raw_sha256": sha256_bytes(body), "content_type": content_type,
        }
        summary = {
            "version": VERSION, "official_url": PUBLIC_URL, **extracted,
            "retrieved_at": completed_at, "byte_count": len(body),
            "raw_sha256": sha256_bytes(body), "request_count": 1,
            "protected_request_count": 0, "recovery_request_count": 0,
        }
        canonical_json(outcome)
        canonical_json(summary)
        _write_once(output_dir / PUBLIC_FILES[2], canonical_json(outcome))
        _write_once(output_dir / PUBLIC_FILES[4], canonical_json(summary))
        return summary
    except Exception as exc:
        completed_at = clock()
        body = b"" if response is None else response.content
        outcome = {
            "version": VERSION, "attempt_number": 1, "state": "failed",
            "completed_at": completed_at, "http_status": None if response is None else response.status_code,
            "redirected": False if response is None else bool(response.history or response.is_redirect),
            "automatic_retries": 0, "byte_count": len(body),
            "raw_sha256": None if response is None else sha256_bytes(body),
            "failure": f"{type(exc).__name__}: {exc}",
        }
        if not (output_dir / PUBLIC_FILES[2]).exists():
            _write_once(output_dir / PUBLIC_FILES[2], canonical_json(outcome))
        raise
    finally:
        session.close()


def prove_window_coverage() -> dict[str, Any]:
    early_start = date.fromisoformat(WINDOWS[0]["DateFrom"])
    early_end = date.fromisoformat(WINDOWS[0]["DateTo"])
    late_start = date.fromisoformat(WINDOWS[1]["DateFrom"])
    late_end = date.fromisoformat(WINDOWS[1]["DateTo"])
    proof = {
        "both_within_verified_interval": SEASON_START <= early_start <= early_end <= SEASON_END and SEASON_START <= late_start <= late_end <= SEASON_END,
        "nonoverlapping": early_end < late_start,
        "contiguous": early_end + timedelta(days=1) == late_start,
        "complete_coverage": early_start == SEASON_START and late_end == SEASON_END and early_end + timedelta(days=1) == late_start,
        "verified_interval_day_count": (SEASON_END - SEASON_START).days + 1,
        "window_union_day_count": (early_end - early_start).days + 1 + (late_end - late_start).days + 1,
    }
    if not all(proof[key] for key in ("both_within_verified_interval", "nonoverlapping", "contiguous", "complete_coverage")):
        raise SpecificationError("complementary windows do not exactly cover the verified interval")
    if proof["verified_interval_day_count"] != proof["window_union_day_count"]:
        raise SpecificationError("window day counts do not reconcile")
    return proof


def _validate_trigger_metadata(project_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    exact = _read_json(project_root / R2B2_EXACT_250_PATH)
    if [item["team_id"] for item in exact["teams"]] != [item["team_id"] for item in TEAM_SPECS]:
        raise SpecificationError("Indiana and Memphis are not the exact unresolved inventory")
    requests_value = _read_json(project_root / R2B2_REQUESTS_PATH)
    selected = [item for item in requests_value if item["parameters"]["TeamID"] in {team["team_id"] for team in TEAM_SPECS}]
    if len(selected) != 4:
        raise SpecificationError("expected four triggering full-season identities")
    for team in TEAM_SPECS:
        recorded = next(item for item in exact["teams"] if item["team_id"] == team["team_id"])
        if recorded["structural_disposition"] != "exact_250_unresolved":
            raise SpecificationError("trigger team is no longer exact_250_unresolved")
        for measure_key in ("base", "advanced"):
            expected = team[measure_key]
            actual = next(item for item in recorded["triggering_identities"] if item["measure"].lower() == measure_key)
            for key in ("ordinal", "request_id", "raw_sha256", "canonical_json_sha256"):
                if actual[key] != expected[key]:
                    raise SpecificationError(f"trigger mismatch for {team['team_name']} {measure_key}: {key}")
            request = next(item for item in selected if item["request_id"] == expected["request_id"])
            if request["ordinal"] != expected["ordinal"]:
                raise SpecificationError("trigger request ordinal mismatch")
    return exact["teams"], selected


def build_recovery_identities(full_season_requests: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    source_by_id = {item["request_id"]: item for item in full_season_requests}
    identities: list[dict[str, Any]] = []
    ordinal = 0
    for team in TEAM_SPECS:
        triggers = {"Base": team["base"], "Advanced": team["advanced"]}
        for window in WINDOWS:
            for measure in ("Base", "Advanced"):
                ordinal += 1
                source = source_by_id[triggers[measure]["request_id"]]
                parameters = dict(source["parameters"])
                parameters["DateFrom"] = window["DateFrom"]
                parameters["DateTo"] = window["DateTo"]
                request_id = (
                    f"teamdashlineups:{team['team_id']}:2025-26:regular-season:"
                    f"{window['DateFrom']}:{window['DateTo']}:{measure.lower()}"
                )
                namespace = (FUTURE_PROTECTED_NAMESPACE / f"{ordinal:02d}-{team['team_id']}-{window['name']}-{measure.lower()}").as_posix()
                identity = {
                    "ordinal": ordinal, "request_id": request_id, "team_id": team["team_id"],
                    "team_name": team["team_name"], "endpoint": "teamdashlineups",
                    "endpoint_identity": "TeamDashLineups", "season": "2025-26",
                    "season_type": "Regular Season", "window": dict(window), "measure": measure,
                    "parameters": parameters,
                    "triggering_full_season_identities": {
                        "Base": dict(team["base"]), "Advanced": dict(team["advanced"]),
                    },
                    "corrected_response_contract_identity": R2B1_CONTRACT_IDENTITY,
                    "future_protected_transport_contract": {
                        "path": R2B21_TRANSPORT_PATH.as_posix(), "sha256": R2B21_TRANSPORT_SHA256,
                    },
                    "future_output_namespace": namespace,
                    "specification_status": "frozen_not_authorized",
                }
                identity["canonical_request_identity_sha256"] = sha256_bytes(canonical_json(identity))
                identities.append(identity)
    validate_recovery_inventory(identities)
    return identities


def validate_recovery_inventory(identities: Sequence[Mapping[str, Any]]) -> None:
    if len(identities) != 8:
        raise SpecificationError("recovery inventory must contain exactly eight identities; a ninth is rejected")
    expected_teams = ["1610612754"] * 4 + ["1610612763"] * 4
    expected_windows = ["early", "early", "late", "late"] * 2
    expected_measures = ["Base", "Advanced", "Base", "Advanced"] * 2
    for index, identity in enumerate(identities, start=1):
        parameters = identity["parameters"]
        team = next(item for item in TEAM_SPECS if item["team_id"] == expected_teams[index - 1])
        window = next(item for item in WINDOWS if item["name"] == expected_windows[index - 1])
        measure = expected_measures[index - 1]
        expected_request_id = (
            f"teamdashlineups:{team['team_id']}:2025-26:regular-season:"
            f"{window['DateFrom']}:{window['DateTo']}:{measure.lower()}"
        )
        expected_namespace = (
            FUTURE_PROTECTED_NAMESPACE /
            f"{index:02d}-{team['team_id']}-{window['name']}-{measure.lower()}"
        ).as_posix()
        if identity["ordinal"] != index or identity["team_id"] != team["team_id"]:
            raise SpecificationError("recovery ordinal or team is not allowlisted")
        if identity.get("team_name") != team["team_name"]:
            raise SpecificationError("recovery team name is not allowlisted")
        if identity["window"] != window or identity["measure"] != measure:
            raise SpecificationError("recovery window or measure is not allowlisted")
        if identity.get("season") != "2025-26" or identity.get("season_type") != "Regular Season":
            raise SpecificationError("recovery season or season type is not allowlisted")
        if identity.get("request_id") != expected_request_id:
            raise SpecificationError("recovery request ID is not deterministic")
        if identity.get("future_output_namespace") != expected_namespace:
            raise SpecificationError("future output namespace binding mismatch")
        if identity["endpoint"] != "teamdashlineups" or identity["endpoint_identity"] != "TeamDashLineups":
            raise SpecificationError("recovery endpoint is not allowlisted")
        required = {"Season": "2025-26", "SeasonType": "Regular Season", "GroupQuantity": "2",
                    "PerMode": "Totals", "MeasureType": identity["measure"], "TeamID": identity["team_id"],
                    "DateFrom": identity["window"]["DateFrom"], "DateTo": identity["window"]["DateTo"]}
        expected_parameters = {**ESTABLISHED_PARAMETER_DEFAULTS, **required}
        if parameters != expected_parameters:
            raise SpecificationError("recovery parameters drifted from the exact allowlist")
        if identity["corrected_response_contract_identity"] != R2B1_CONTRACT_IDENTITY:
            raise SpecificationError("response-contract binding mismatch")
        if identity["future_protected_transport_contract"]["sha256"] != R2B21_TRANSPORT_SHA256:
            raise SpecificationError("transport-contract binding mismatch")
        triggers = identity["triggering_full_season_identities"]
        expected_triggers = {"Base": team["base"], "Advanced": team["advanced"]}
        if triggers != expected_triggers:
            raise SpecificationError("trigger hashes are required")
        if identity.get("specification_status") != "frozen_not_authorized":
            raise SpecificationError("recovery identity must remain unauthorized")
        hashed = dict(identity)
        recorded_hash = hashed.pop("canonical_request_identity_sha256", None)
        if recorded_hash != sha256_bytes(canonical_json(hashed)):
            raise SpecificationError("canonical recovery identity hash mismatch")


def canonical_pair_key(player_ids: Sequence[int | str]) -> tuple[int, int]:
    if isinstance(player_ids, (str, bytes)) or len(player_ids) != 2:
        raise PairPopulationError("pair must contain exactly two player IDs", {"malformed": 1, "same_player": 0})
    values: list[int] = []
    for item in player_ids:
        if isinstance(item, bool):
            raise PairPopulationError("player IDs must be positive integers", {"malformed": 1, "same_player": 0})
        text = str(item)
        if not re.fullmatch(r"[1-9][0-9]*", text):
            raise PairPopulationError("player IDs must be positive integers", {"malformed": 1, "same_player": 0})
        values.append(int(text))
    if values[0] == values[1]:
        raise PairPopulationError("pair cannot contain the same player twice", {"malformed": 0, "same_player": 1})
    return tuple(sorted(values))  # type: ignore[return-value]


def canonical_pair_population(rows: Iterable[Sequence[int | str]]) -> set[tuple[int, int]]:
    keys: set[tuple[int, int]] = set()
    duplicate = malformed = same_player = 0
    for row in rows:
        try:
            key = canonical_pair_key(row)
        except PairPopulationError as exc:
            malformed += exc.diagnostics.get("malformed", 0)
            same_player += exc.diagnostics.get("same_player", 0)
            continue
        if key in keys:
            duplicate += 1
        keys.add(key)
    diagnostics = {"duplicate": duplicate, "malformed": malformed, "same_player": same_player}
    if any(diagnostics.values()):
        raise PairPopulationError("pair population contains rejected rows", diagnostics)
    return keys


def classify_disposition(record: Mapping[str, Any]) -> str:
    if record.get("recovered_only_count", 0) > 0 and record.get("recovered_only_keys_valid", True):
        return "proven_non_exhaustive"
    required_true = (
        "all_four_authenticated_and_structurally_valid", "every_window_below_250",
        "base_advanced_equal_within_each_window", "complete_complementary_coverage",
    )
    required_zero = (
        "recovered_only_count", "full_season_only_count", "duplicate_count",
        "malformed_count", "same_player_count", "base_only_count", "advanced_only_count",
    )
    if all(record.get(key) is True for key in required_true) and all(record.get(key, 0) == 0 for key in required_zero):
        return "operationally_resolved_no_observed_omission"
    return "recovery_unresolved"


def whole_team_exclusion_implication(disposition: str) -> bool:
    return disposition == "proven_non_exhaustive"


def fingerprint_namespace(project_root: Path, relative_root: Path) -> dict[str, Any]:
    root = project_root / relative_root
    if not root.is_dir():
        raise SpecificationError(f"missing historical namespace: {relative_root.as_posix()}")
    files = []
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.as_posix()):
        stat = path.stat()
        files.append({
            "path": path.relative_to(project_root).as_posix(), "bytes": stat.st_size,
            "sha256": sha256_bytes(path.read_bytes()), "mtime_ns": stat.st_mtime_ns,
        })
    inventory_bytes = canonical_json(files)
    return {"namespace": relative_root.as_posix(), "file_count": len(files),
            "byte_count": sum(item["bytes"] for item in files),
            "inventory_sha256": sha256_bytes(inventory_bytes), "files": files}


def _source_evidence(project_root: Path) -> dict[str, Any]:
    root = project_root / PUBLIC_SOURCE_NAMESPACE
    if not root.is_dir() or tuple(sorted(item.name for item in root.iterdir() if item.is_file())) != tuple(sorted(PUBLIC_FILES)):
        raise SpecificationError("public-source namespace is missing, partial, or conflicting")
    summary = _read_json(root / "verified-source-summary.json")
    body = (root / "response.html").read_bytes()
    if summary["official_url"] != PUBLIC_URL or summary["season_start"] != SEASON_START.isoformat() or summary["season_end"] != SEASON_END.isoformat():
        raise SpecificationError("public-source summary does not authenticate exact boundaries")
    if summary["raw_sha256"] != sha256_bytes(body) or summary["byte_count"] != len(body):
        raise SpecificationError("public-source body fingerprint mismatch")
    return {"summary": summary, "artifacts": {
        name: {"bytes": (root / name).stat().st_size, "sha256": sha256_bytes((root / name).read_bytes())}
        for name in PUBLIC_FILES
    }}


def build_specification(project_root: Path, output_dir: Path) -> dict[str, bytes]:
    project_root = Path(project_root)
    output_dir = Path(output_dir)
    _require_absent_namespace(output_dir)
    source = _source_evidence(project_root)
    exact_teams, full_season = _validate_trigger_metadata(project_root)
    contract = _read_json(project_root / R2B1_CONTRACT_PATH)
    if contract.get("correction_contract_identity") != R2B1_CONTRACT_IDENTITY:
        raise SpecificationError("corrected response-contract identity mismatch")
    transport_path = project_root / R2B21_TRANSPORT_PATH
    if sha256_bytes(transport_path.read_bytes()) != R2B21_TRANSPORT_SHA256:
        raise SpecificationError("future protected-transport-contract hash mismatch")
    identities = build_recovery_identities(full_season)
    fingerprints = [fingerprint_namespace(project_root, root) for root in HISTORICAL_NAMESPACES]
    plan = {
        "version": VERSION, "classification": CLASSIFICATION,
        "prior_blocked_r2c_attempt": {"stopped_during_preflight": True, "deliverable_created": False,
                                      "generated_namespace_created": False, "request_identity_created": False,
                                      "working_tree_change_created": False},
        "public_season_boundary_source": source,
        "verified_regular_season": {"season": "2025-26", "season_type": "Regular Season",
                                    "start": SEASON_START.isoformat(), "end": SEASON_END.isoformat()},
        "complementary_windows": {"windows": [dict(item) for item in WINDOWS], "coverage_proof": prove_window_coverage()},
        "future_recovery_identities": identities,
        "triggering_exact_250_teams": exact_teams,
        "governing_contracts": {"corrected_r2b1_response_contract_identity": R2B1_CONTRACT_IDENTITY,
                                "r2b21_future_protected_transport_contract_path": R2B21_TRANSPORT_PATH.as_posix(),
                                "r2b21_future_protected_transport_contract_sha256": R2B21_TRANSPORT_SHA256},
        "future_transport_requirements": {
            "separately_authorized_checkpoint_required": True, "phase_local_authorization_consistency": True,
            "exact_namespace_binding": True, "executing_source_pinning": True, "sequential_order": True,
            "minimum_monotonic_completion_to_next_start_seconds": 1.0, "timeout_seconds": 30,
            "redirects_allowed": False, "trust_env": False, "automatic_retries": 0,
            "attempts_per_identity": 1, "immutable_start_and_outcome_records": True,
            "verification_before_promotion": True, "quarantine_and_immediate_stop_on_failure": True,
            "restart_safe_refusal_states": ["incomplete", "conflicting", "failed", "quarantined"],
        },
        "population_reconciliation": {
            "scope": "pair-population-only", "identity_fields": "exactly two distinct positive player IDs",
            "canonical_order": "numeric ascending", "player_names_used_for_identity": False,
            "reject": ["malformed", "duplicate", "same-player", "Base-only", "Advanced-only"],
            "preserve_zero_possession_rows": True,
            "team_comparison": "union early and late canonical pair-key sets, then compare with authenticated full-season pair-key set",
            "required_report_fields": ["full-season count", "early count", "late count", "union count",
                "keys shared by full season and union", "full-season-only keys", "recovered-only keys",
                "duplicate count", "malformed count", "Base-only count", "Advanced-only count",
                "whether every window response is below 250 rows"],
            "window_possessions": "may be summed only as nonoverlapping exposure metadata",
            "rating_aggregation": False, "full_season_target_reconstruction": False,
            "rating_values_affect_retention": False,
        },
        "dispositions": {
            "proven_non_exhaustive": {
                "condition": "at least one valid recovered-only pair key exists",
                "eventual_implication": "whole-team exclusion unless a separately authorized definition-supported direct source supplies omitted full-season targets",
                "applied_during_r2c": False,
            },
            "operationally_resolved_no_observed_omission": {
                "conditions": ["all four recovery responses authenticated and structurally valid",
                    "every individual window response has fewer than 250 canonical pair rows",
                    "Base and Advanced pair-key sets match exactly within each window",
                    "the two windows cover the full verified regular-season interval",
                    "window union exactly equals full-season pair-key set", "recovered-only count is zero",
                    "full-season-only count is zero", "duplicate, malformed, Base-only, and Advanced-only counts are zero"],
                "meaning": "no omission observed under the predeclared complementary-window design; operationally resolved for final-test readiness",
                "limitation": "not proof of universal or mathematical endpoint exhaustiveness; never call proven exhaustive",
            },
            "recovery_unresolved": {
                "condition": "any required classification condition is absent or any conflicting state exists",
                "meaning": "readiness gate cannot pass; do not automatically exclude or retain; stop for a new audited decision",
            },
        },
        "historical_preservation_before_state": fingerprints,
        "explicit_prohibitions": ["protected pair acquisition", "recovery execution", "final-test construction",
            "model fitting", "prediction", "metrics", "serialization", "database", "API", "frontend", "deployment",
            "rating aggregation", "target reconstruction", "automatic exclusion during R2C"],
    }
    summary = {
        "version": VERSION, "classification": CLASSIFICATION,
        "public_source_requests": 1, "protected_requests": 0, "recovery_requests": 0,
        "final_test_rows_constructed": 0, "model_operations": 0,
        "unresolved_teams": ["Indiana Pacers", "Memphis Grizzlies"],
        "unresolved_until": "the eight frozen requests are separately authorized, acquired, reconciled, and audited",
        "final_test_readiness_gates": "retain their pending state",
        "operational_resolution_limitation": "no-observed-omission is not proof of universal or mathematical endpoint exhaustiveness",
    }
    recovery_body = canonical_json(plan)
    summary_body = canonical_json(summary)
    manifest = {
        "version": VERSION, "rule": "nonrecursive SHA-256 over exact bytes of recovery_plan.json and summary.json; manifest excludes itself to avoid circularity",
        "artifact_inventory": list(PLANNING_FILES),
        "artifacts": {
            "recovery_plan.json": {"bytes": len(recovery_body), "sha256": sha256_bytes(recovery_body)},
            "summary.json": {"bytes": len(summary_body), "sha256": sha256_bytes(summary_body)},
        },
    }
    result = {"recovery_plan.json": recovery_body, "artifact_hashes.json": canonical_json(manifest), "summary.json": summary_body}
    if tuple(result) != PLANNING_FILES:
        raise SpecificationError("generated planning inventory mismatch")
    return result


def write_specification(project_root: Path, output_dir: Path) -> dict[str, Any]:
    artifacts = build_specification(project_root, output_dir)
    # The full artifact set is validated in memory before the namespace exists.
    for body in artifacts.values():
        json.loads(body.decode("utf-8"), parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
    _require_absent_namespace(Path(output_dir))
    for name, body in artifacts.items():
        _write_once(Path(output_dir) / name, body)
    return {"classification": CLASSIFICATION, "artifacts": {
        name: {"bytes": len(body), "sha256": sha256_bytes(body)} for name, body in artifacts.items()
    }}
