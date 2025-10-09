# app/utils/cache.py
import time
from typing import Any, Tuple

class TTLCache:
    def __init__(self, ttl_seconds: int = 3600, maxsize: int = 2000):
        self.ttl = ttl_seconds
        self.maxsize = maxsize
        self._data: dict[Tuple[Any, ...], tuple[float, Any]] = {}

    def get(self, key):
        rec = self._data.get(key)
        if not rec:
            return None
        ts, val = rec
        if time.time() - ts > self.ttl:
            self._data.pop(key, None)
            return None
        return val

    def set(self, key, val):
        if len(self._data) >= self.maxsize:
            # simple drop-oldest
            oldest = min(self._data.items(), key=lambda kv: kv[1][0])[0]
            self._data.pop(oldest, None)
        self._data[key] = (time.time(), val)

    def get_or_set(self, key, maker):
        val = self.get(key)
        if val is not None:
            return val
        val = maker()
        self.set(key, val)
        return val

cache = TTLCache(ttl_seconds=3600, maxsize=4000)  # 1 hour, season data is stable