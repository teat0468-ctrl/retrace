from datetime import datetime, timedelta, timezone
import re
from typing import Any
from urllib.parse import urlparse

from app.services.investigation import SearchQuery
from app.services.search import serpapi_search


# Domains that never produce useful evidence for news investigations
BLOCKED_DOMAINS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "play.google.com",
    "apps.apple.com",
    "itunes.apple.com",
    "open.spotify.com",
    "soundcloud.com",
    "tiktok.com",
    "www.tiktok.com",
    "pinterest.com",
    "www.pinterest.com",
    "amazon.com",
    "www.amazon.com",
    "www.amazon.in",
    "flipkart.com",
    "www.flipkart.com",
}


def _is_blocked_url(url: str | None) -> bool:
    if not url:
        return True
    try:
        host = urlparse(url).hostname or ""
        return host.lower() in BLOCKED_DOMAINS
    except Exception:
        return False


def _extract_date_from_snippet(snippet: str | None):
    """Try to pull a date out of the beginning of a snippet like 'Jun 10, 2026 — ...'"""
    if not snippet:
        return None
    # SerpAPI often prepends dates like "Sep 17, 2026 — "
    match = re.match(
        r"^([A-Z][a-z]{2,8}\s+\d{1,2},\s+\d{4})",
        snippet,
    )
    if match:
        return _parse_date(match.group(1))
    return None


def _parse_date(value: str | None):
    if not value:
        return None

    value = value.strip()

    # ISO 8601 format from SerpApi, e.g.
    # 2026-09-17T08:12:32Z
    try:
        iso_value = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(iso_value)

        # Store as naive UTC datetime because SQLite DateTime
        # is currently being used without timezone support.
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)

        return parsed

    except ValueError:
        pass

    formats = [
        "%b %d, %Y",
        "%B %d, %Y",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue

    match = re.match(
        r"(\d+)\s+(minute|minutes|hour|hours|day|days|week|weeks)\s+ago",
        value.lower(),
    )

    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        now = datetime.now()

        if unit.startswith("minute"):
            return now - timedelta(minutes=amount)

        if unit.startswith("hour"):
            return now - timedelta(hours=amount)

        if unit.startswith("day"):
            return now - timedelta(days=amount)

        if unit.startswith("week"):
            return now - timedelta(weeks=amount)

    if value.lower() == "yesterday":
        return datetime.now() - timedelta(days=1)

    return None


def _source_type(purpose: str) -> str:
    if purpose in {"current_news", "new_event_check"}:
        return "news"

    if purpose in {"historical_search", "historical_context"}:
        return "historical"

    if purpose in {"scholar_research", "patent_research"}:
        return "academic"

    return "search"


def _extract_news_results(data: dict[str, Any], purpose: str):
    results = []

    for item in data.get("news_results", []):
        source = item.get("source")

        if isinstance(source, dict):
            publisher = source.get("name")
        else:
            publisher = source

        results.append(
            {
                "title": item.get("title"),
                "url": item.get("link"),
                "snippet": item.get("snippet"),
                "publisher": publisher,
                "published_at": _parse_date(
                    item.get("iso_date") or item.get("date")
                ),
                "source_type": _source_type(purpose),
                "purpose": purpose,
            }
        )

    return results


def _extract_google_results(data: dict[str, Any], purpose: str):
    results = []
    
    search_info = data.get("search_information", {})
    if "Empty" in search_info.get("organic_results_state", ""):
        return results

    for item in data.get("organic_results", []):
        url = item.get("link")

        # Skip garbage domains
        if _is_blocked_url(url):
            continue

        # Try SerpAPI's date field first, then snippet extraction
        published_at = _parse_date(item.get("date"))
        if published_at is None:
            published_at = _extract_date_from_snippet(item.get("snippet"))

        results.append(
            {
                "title": item.get("title"),
                "snippet": item.get("snippet"),
                "url": url,
                "publisher": item.get("source"),
                "published_at": published_at,
                "source_type": _source_type(purpose),
                "purpose": purpose,
            }
        )

    return results


def _extract_scholar_results(data: dict[str, Any], purpose: str):
    results = []

    for item in data.get("organic_results", []):
        publication_info = item.get("publication_info", {})
        summary = publication_info.get("summary", "")
        
        match = re.search(r"\b(19|20)\d{2}\b", summary)
        published_at = None
        if match:
            year = int(match.group(0))
            published_at = datetime(year, 1, 1)

        results.append(
            {
                "title": item.get("title"),
                "snippet": item.get("snippet"),
                "url": item.get("link"),
                "publisher": summary,
                "published_at": published_at,
                "source_type": _source_type(purpose),
                "purpose": purpose,
            }
        )

    return results


def _extract_patents_results(data: dict[str, Any], purpose: str):
    results = []

    for item in data.get("organic_results", []):
        published_at = _parse_date(item.get("publication_date"))
        if published_at is None:
            published_at = _parse_date(item.get("filing_date"))

        results.append(
            {
                "title": item.get("title"),
                "snippet": item.get("snippet"),
                "url": item.get("patent_link") or item.get("pdf") or item.get("link"),
                "publisher": item.get("assignee") or item.get("inventor") or "Patent Office",
                "published_at": published_at,
                "source_type": _source_type(purpose),
                "purpose": purpose,
            }
        )

    return results


def collect_evidence(search_plan: list[SearchQuery]):
    evidence = []

    for search_item in search_plan:
        engine_name = search_item.engine
        params = {
            "q": search_item.query,
            "num": 10,
        }

        if engine_name == "google_patents":
            engine_name = "google"
            params["tbm"] = "pts"

        data = serpapi_search(
            engine=engine_name,
            params=params,
        )

        if search_item.engine == "google_news":
            results = _extract_news_results(
                data,
                search_item.purpose,
            )
        elif search_item.engine == "google":
            results = _extract_google_results(
                data,
                search_item.purpose,
            )
        elif search_item.engine == "google_scholar":
            results = _extract_scholar_results(
                data,
                search_item.purpose,
            )
        elif search_item.engine == "google_patents":
            results = _extract_patents_results(
                data,
                search_item.purpose,
            )
        else:
            results = []

        evidence.extend(results)

    return evidence


def deduplicate_evidence(evidence: list[dict]) -> list[dict]:
    seen_urls = set()
    unique = []

    for item in evidence:
        url = item.get("url")

        if not url:
            continue

        if url in seen_urls:
            continue

        # Final safety net: block garbage domains
        if _is_blocked_url(url):
            continue

        seen_urls.add(url)
        unique.append(item)

    return unique
