import json
from fastapi import Response

def with_cache_headers(data: dict, seconds: int = 900) -> Response:
    resp = Response(content=json.dumps(data), media_type="application/json")
    resp.headers["Cache-Control"] = f"public, max-age={seconds}"
    return resp