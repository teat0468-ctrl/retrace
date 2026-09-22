from app.core.config import SERPAPI_KEY
from app.services.search import serpapi_search


def get_trends(
    query: str,
    date_range: str = "today 5-y",
    geo: str = "",
):
    """Fetch Google Trends TIMESERIES data.

    date_range: SerpAPI date string. Default is 5 years so we can detect
                topics that spiked years ago and are re-emerging now.
    geo:        ISO-3166 country code, or empty string for worldwide.
    """
    params = {
        "q": query,
        "date": date_range,
        "data_type": "TIMESERIES",
    }
    # geo="" means worldwide; only pass the key when a specific country is wanted
    if geo:
        params["geo"] = geo
    return serpapi_search(
        engine="google_trends",
        params=params,
    )
