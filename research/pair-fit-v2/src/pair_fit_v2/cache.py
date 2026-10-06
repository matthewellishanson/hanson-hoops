from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JsonCache:
    """Minimal on-disk JSON cache used by the Phase 0 research scaffold."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.root / f"{key}.json"

    def write(self, key: str, payload: Any) -> Path:
        path = self._path(key)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path

    def read(self, key: str) -> Any | None:
        path = self._path(key)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
