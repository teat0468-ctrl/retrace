import re
from dataclasses import dataclass
from datetime import datetime


@dataclass
class EventCandidate:
    title: str
    description: str
    event_date: datetime | None

    entities: list[str]
    event_keywords: list[str]
    measurements: list[str]

    years: list[str]
    event_markers: list[str]

    source_id: int | None
    source_type: str | None
    search_purpose: str | None


STOP_WORDS = {
    "a",
    "an",
    "the",
    "on",
    "in",
    "of",
    "to",
    "for",
    "and",
    "with",
    "new",
    "massive",
    "huge",
    "giant",
    "recently",
    "just",
    "has",
    "have",
    "been",
    "this",
    "that",
    "here",
    "how",
    "why",
    "from",
    "after",
    "before",
    # Common sentence-starting words that look like proper nouns
    "By",
    "At",
    "In",
    "On",
    "If",
    "As",
    "It",
    "He",
    "She",
    "We",
    "Is",
}


EVENT_WORDS = {
    "discovers",
    "discovered",
    "discover",
    "finds",
    "found",
    "find",
    "launches",
    "launched",
    "launch",
    "announces",
    "announced",
    "opens",
    "opened",
    "arrested",
    "dies",
    "died",
    "killed",
    "wins",
    "won",
    "reports",
    "reported",
    "reveals",
    "revealed",
    "created",
    "creates",
    "formed",
    "forms",
    "impact",
    "crash",
    "crashed",
    "smashed",
    "slammed",
    "bans",
    "banned",
    "approves",
    "approved",
    "warns",
    "warning",
    "surges",
    "surged",
    "collapses",
    "collapsed",
    "explodes",
    "exploded",
    "sues",
    "sued",
    "charges",
    "charged",
    "links",
    "linked",
    "causes",
    "caused",
    "triggers",
    "triggered",
    "confirms",
    "confirmed",
    "denies",
    "denied",
    "claims",
    "shows",
    "suggests",
    "suggested",
    "proves",
    "proved",
    "debunked",
    "debunks",
}


# ------------------------------------------------------------------
# Domain-agnostic event markers
# These patterns fire for ANY topic, not just Moon craters.
# ------------------------------------------------------------------
EVENT_MARKER_PATTERNS = {
    # --- Newness / discovery ---
    "newly_discovered": [
        r"\bnewly[- ]discovered\b",
        r"\bnew discovery\b",
        r"\bfirst[- ]ever\b",
        r"\bfirst time\b",
        r"\bunprecedented\b",
    ],
    "newly_formed": [
        r"\bnewly[- ]formed\b",
        r"\bjust[- ]formed\b",
        r"\brecently[- ]formed\b",
    ],
    # --- Causality / impact ---
    "impact_event": [
        r"\bimpact\b",
        r"\bimpacted\b",
        r"\bslam(?:med)?\b",
        r"\bsmashed\b",
        r"\bexplod(?:ed|es)\b",
        r"\bblast(?:ed)?\b",
    ],
    # --- Science / research language ---
    "study_claim": [
        r"\bstudy\b",
        r"\bresearch(?:ers?)?\b",
        r"\bscientists?\b",
        r"\bfinds\b",
        r"\bsuggests?\b",
        r"\blinked to\b",
        r"\bassociated with\b",
    ],
    "debunked": [
        r"\bdebunked?\b",
        r"\bfact[- ]check(?:ed)?\b",
        r"\bmisleading\b",
        r"\bfalse claim\b",
        r"\bdisproved?\b",
        r"\brefuted?\b",
    ],
    "outdated_research": [
        r"\b(19|20)\d{2}\b.*\bstudy\b",
        r"\bold(?:er)? study\b",
        r"\boutdated\b",
        r"\boverturned\b",
    ],
    # --- Scale / significance ---
    "once_in_a_century": [
        r"\bonce[- ]in[- ]a[- ]century\b",
        r"\bonce[- ]in[- ]a[- ]lifetime\b",
        r"\bonce[- ]in[- ]\d+[- ]year\b",
        r"\brarest?\b",
    ],
    # --- Government / legal / policy ---
    "policy_change": [
        r"\bbanned?\b",
        r"\bapproved?\b",
        r"\blaw(?:suit)?\b",
        r"\bregulation\b",
        r"\bmandate\b",
        r"\bexecutive order\b",
        r"\bverdicts?\b",
        r"\bsentenced?\b",
    ],
    # --- Health / safety alerts ---
    "health_alert": [
        r"\bhealth risk\b",
        r"\bcancer\b",
        r"\bpandemic\b",
        r"\bvirus\b",
        r"\bvaccine\b",
        r"\boutbreak\b",
        r"\bepidemic\b",
        r"\bwarning\b",
    ],
    # --- Economic signals ---
    "economic_signal": [
        r"\brecession\b",
        r"\binflation\b",
        r"\bstock market\b",
        r"\bcrash\b",
        r"\bcollapse\b",
        r"\bbankruptcy\b",
        r"\bcollapsed?\b",
    ],
    # --- Detection / visibility delay ---
    "detection_delay": [
        r"\bundetected\b",
        r"\bhidden\b",
        r"\bwasn'?t there before\b",
        r"\boverlooked\b",
        r"\bignored\b",
        r"\byears? later\b",
        r"\bdecades? later\b",
    ],
    # --- Recycled / re-shared signals ---
    "reshared_old": [
        r"\bold (?:video|photo|image|story|article|clip)\b",
        r"\bfrom \d{4}\b",
        r"\boriginally\b",
        r"\breurfaced?\b",
        r"\bgoing viral again\b",
        r"\bcirculating again\b",
        r"\bsame (?:claim|story|video|photo)\b",
    ],
}


def normalize_text(text: str) -> str:
    text = text.lower()

    text = re.sub(
        r"[^a-z0-9\s-]",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def extract_entities(text: str) -> list[str]:
    """
    Generic proper-noun extraction via regex.
    Finds sequences of Capitalized words (up to 4 tokens), filters
    common stop-words and short tokens.
    """
    entities = []

    # Match sequences of 1–4 capitalized words
    matches = re.findall(
        r"\b[A-Z][a-zA-Z0-9]*(?:\s+[A-Z][a-zA-Z0-9]*){0,3}",
        text,
    )

    stop_lower = {w.lower() for w in STOP_WORDS}

    for match in matches:
        cleaned = match.strip()

        # Skip very short tokens and anything in stop-words
        if len(cleaned) < 3:
            continue

        if cleaned.lower() in stop_lower:
            continue

        if cleaned not in entities:
            entities.append(cleaned)

    return entities[:12]


def extract_event_keywords(title: str) -> list[str]:
    text = normalize_text(title)

    words = text.split()

    stop_lower = {w.lower() for w in STOP_WORDS}

    keywords = []

    for word in words:
        if len(word) < 3:
            continue

        if word in stop_lower:
            continue

        if word not in keywords:
            keywords.append(word)

    return keywords[:20]


def extract_measurements(text: str) -> list[str]:
    patterns = [
        r"\b\d+(?:\.\d+)?\s*(?:-?\s*)?(?:meter|meters|metre|metres)\b",
        r"\b\d+(?:\.\d+)?\s*(?:km|kilometer|kilometers|kilometre|kilometres)\b",
        r"\b\d+(?:\.\d+)?\s*(?:feet|foot)\b",
        r"\b\d+(?:\.\d+)?\s*(?:mile|miles)\b",
        # Percentages
        r"\b\d+(?:\.\d+)?%\b",
        # Large numbers (billions, millions, thousands)
        r"\b\d+(?:\.\d+)?\s*(?:billion|million|trillion|thousand)\b",
        # Currency
        r"\$\d+(?:\.\d+)?\s*(?:billion|million|trillion|thousand)?\b",
    ]

    measurements = []

    for pattern in patterns:

        matches = re.findall(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        for match in matches:

            cleaned = match.strip().lower()

            if cleaned not in measurements:
                measurements.append(cleaned)

    return measurements


def extract_years(text: str) -> list[str]:

    years = re.findall(
        r"\b(?:19|20)\d{2}\b",
        text,
    )

    return list(dict.fromkeys(years))


def extract_event_markers(text: str) -> list[str]:
    """
    Domain-agnostic marker extraction.
    Tests the raw text (not lowercased stripped) against all patterns
    with IGNORECASE so we catch natural prose.
    """
    markers = []

    for marker, patterns in EVENT_MARKER_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, flags=re.IGNORECASE):
                markers.append(marker)
                break

    return markers


def looks_like_event(title: str) -> bool:

    text = normalize_text(title)

    return any(
        re.search(
            rf"\b{re.escape(word)}\b",
            text,
        )
        for word in EVENT_WORDS
    )


def extract_event_from_source(
    source,
    source_id: int | None = None,
):

    title = source.title or ""

    if not looks_like_event(title):
        return None

    return EventCandidate(
        title=title,
        description=title,
        event_date=source.published_at,
        entities=extract_entities(title),
        event_keywords=extract_event_keywords(title),
        measurements=extract_measurements(title),
        years=extract_years(title),
        event_markers=extract_event_markers(title),
        source_id=source_id,
        source_type=source.source_type,
        search_purpose=source.search_purpose,
    )


def extract_events(sources):

    events = []

    for source in sources:

        event = extract_event_from_source(
            source,
            source.id,
        )

        if event is not None:
            events.append(event)

    return events