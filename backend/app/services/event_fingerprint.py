import re
from dataclasses import dataclass


@dataclass
class NormalizedMeasurement:
    original: str
    value: float
    unit: str
    meters: float


@dataclass
class EventFingerprint:
    entities: set[str]
    keywords: set[str]

    years: set[str]
    numbers: set[str]

    measurements: list[NormalizedMeasurement]

    event_markers: set[str]

    title: str


def normalize_word(word: str) -> str:
    word = word.lower().strip()

    word = word.replace("’", "'")

    word = re.sub(
        r"^[^a-z0-9]+|[^a-z0-9]+$",
        "",
        word,
    )

    replacements = {
        "discovers": "discover",
        "discovered": "discover",
        "discovering": "discover",

        "finds": "find",
        "found": "find",
        "finding": "find",

        "craters": "crater",

        "impacts": "impact",

        "formed": "form",
        "forms": "form",

        "created": "create",
        "creates": "create",
    }

    return replacements.get(word, word)


def normalize_keywords(keywords: list[str]) -> set[str]:
    result = set()

    for word in keywords:
        normalized = normalize_word(word)

        # Measurements belong to the measurement layer.
        if re.search(
            r"\d+(?:\.\d+)?\s*[-]?\s*"
            r"(?:meter|meters|metre|metres|km|kilometer|kilometers|"
            r"kilometre|kilometres|feet|foot|mile|miles)",
            normalized,
            flags=re.IGNORECASE,
        ):
            continue

        if len(normalized) >= 3:
            result.add(normalized)

    return result


def normalize_entities(entities: list[str]) -> set[str]:
    return {
        entity.strip().lower()
        for entity in entities
        if entity.strip()
    }


def extract_years(title: str) -> set[str]:
    return set(
        re.findall(
            r"\b(?:19|20)\d{2}\b",
            title,
        )
    )


def extract_numbers(title: str) -> set[str]:
    return set(
        re.findall(
            r"\b\d+(?:\.\d+)?\b",
            title,
        )
    )


def normalize_measurement(
    value: float,
    unit: str,
    original: str,
) -> NormalizedMeasurement:

    unit = unit.lower()

    if unit in {"meter", "meters", "metre", "metres"}:
        meters = value

    elif unit in {"km", "kilometer", "kilometers", "kilometre", "kilometres"}:
        meters = value * 1000

    elif unit in {"foot", "feet"}:
        meters = value * 0.3048

    elif unit in {"mile", "miles"}:
        meters = value * 1609.344

    else:
        meters = value

    return NormalizedMeasurement(
        original=original,
        value=value,
        unit=unit,
        meters=meters,
    )


def extract_measurements(title: str) -> list[NormalizedMeasurement]:

    patterns = [
        r"\b\d+(?:\.\d+)?\s*[-]?\s*(?:meter|meters|metre|metres)(?:[-\s](?:diameter|deep|wide|long))?\b",

        r"\b\d+(?:\.\d+)?\s*[-]?\s*(?:km|kilometer|kilometers|kilometre|kilometres)(?:[-\s](?:diameter|deep|wide|long))?\b",

        r"\b\d+(?:\.\d+)?\s*[-]?\s*(?:feet|foot)(?:[-\s](?:diameter|deep|wide|long))?\b",

        r"\b\d+(?:\.\d+)?\s*[-]?\s*(?:mile|miles)(?:[-\s](?:diameter|deep|wide|long))?\b",
    ]

    measurements = []

    for pattern in patterns:

        matches = re.finditer(
            pattern,
            title,
            flags=re.IGNORECASE,
        )

        for match in matches:

            original = match.group(0)

            number_match = re.search(
                r"\d+(?:\.\d+)?",
                original,
            )

            unit_match = re.search(
                r"(meter|meters|metre|metres|km|kilometer|kilometers|kilometre|kilometres|feet|foot|mile|miles)",
                original,
                flags=re.IGNORECASE,
            )

            if not number_match or not unit_match:
                continue

            value = float(number_match.group(0))
            unit = unit_match.group(0)

            measurement = normalize_measurement(
                value=value,
                unit=unit,
                original=original,
            )

            measurements.append(measurement)

    return measurements


def build_event_fingerprint(event) -> EventFingerprint:

    title = event.title or ""

    return EventFingerprint(

        entities=normalize_entities(
            event.entities
        ),

        keywords=normalize_keywords(
            event.event_keywords
        ),

        years=extract_years(title),

        numbers=extract_numbers(title),

        measurements=extract_measurements(
            title
        ),

        event_markers=set(
            event.event_markers
        ),

        title=title,
    )