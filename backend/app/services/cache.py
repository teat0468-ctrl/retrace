import hashlib
import json
from pathlib import Path


CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _cache_key(engine: str, params: dict) -> str:
    clean_params = {
        key: value
        for key, value in params.items()
        if key != "api_key"
    }

    raw = json.dumps(
        {
            "engine": engine,
            "params": clean_params,
        },
        sort_keys=True,
    )

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_cached(engine: str, params: dict):
    cache_file = CACHE_DIR / f"{_cache_key(engine, params)}.json"

    if not cache_file.exists():
        return None

    with cache_file.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_cache(engine: str, params: dict, data: dict):
    cache_file = CACHE_DIR / f"{_cache_key(engine, params)}.json"

    with cache_file.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)

    return cache_file
