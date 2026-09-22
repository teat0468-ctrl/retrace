import requests

from app.core.config import SERPAPI_KEY
from app.services.cache import get_cached, save_cache


SERPAPI_URL = "https://serpapi.com/search.json"


def serpapi_search(
    engine: str,
    params: dict,
    use_cache: bool = True,
):
    request_params = {
        **params,
        "engine": engine,
        "api_key": SERPAPI_KEY,
    }

    if use_cache:
        cached = get_cached(engine, request_params)

        if cached is not None:
            return cached

    response = requests.get(
        SERPAPI_URL,
        params=request_params,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    if use_cache:
        save_cache(engine, request_params, data)

    return data


def search_google_news(query: str, num_results: int = 10):
    return serpapi_search(
        engine="google_news",
        params={
            "q": query,
            "num": num_results,
        },
    )


def search_google(query: str, num_results: int = 10):
    return serpapi_search(
        engine="google",
        params={
            "q": query,
            "num": num_results,
        },
    )


def search_google_scholar(query: str, num_results: int = 10):
    return serpapi_search(
        engine="google_scholar",
        params={
            "q": query,
            "num": num_results,
        },
    )

