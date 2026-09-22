import re


def normalize_word(word: str) -> str:
    word = word.lower()

    replacements = {
        "discovers": "discover",
        "discovered": "discover",
        "discover": "discover",

        "finds": "find",
        "found": "find",
        "find": "find",

        "craters": "crater",
        "crater": "crater",

        "impacts": "impact",
        "impact": "impact",

        "formed": "form",
        "forms": "form",

        "created": "create",
        "creates": "create",
    }

    return replacements.get(word, word)


def build_fingerprint(event) -> dict:
    keywords = {
        normalize_word(word)
        for word in event.event_keywords
    }

    entities = {
        entity.lower()
        for entity in event.entities
    }

    measurements = {
        measurement.lower()
        for measurement in event.measurements
    }

    text = event.title.lower()

    years = set(
        re.findall(
            r"\b(?:19|20)\d{2}\b",
            text,
        )
    )

    numbers = set(
        re.findall(
            r"\b\d+(?:\.\d+)?\b",
            text,
        )
    )

    # Event-specific phrases.
    anchors = set()

    anchor_patterns = [
        r"\b\d+(?:\.\d+)?\s*(?:meter|meters|metre|metres)\b",
        r"\b\d+(?:\.\d+)?\s*(?:km|kilometer|kilometers|kilometre|kilometres)\b",
        r"\b(?:19|20)\d{2}\b",
        r"\broman colosseum\b",
        r"\blro\b",
        r"\b2024 impact\b",
        r"\bnewly formed\b",
        r"\bnewly discovered\b",
        r"\bformed by an impact\b",
        r"\bafter an impact\b",
        r"\btwo years later\b",
    ]

    for pattern in anchor_patterns:
        matches = re.findall(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        for match in matches:
            anchors.add(match.lower().strip())

    return {
        "keywords": keywords,
        "entities": entities,
        "measurements": measurements,
        "years": years,
        "numbers": numbers,
        "anchors": anchors,
    }


def jaccard_similarity(set_a: set, set_b: set) -> float:
    if not set_a or not set_b:
        return 0.0

    intersection = set_a & set_b
    union = set_a | set_b

    return len(intersection) / len(union)


def compare_events(event_a, event_b) -> dict:
    fp_a = build_fingerprint(event_a)
    fp_b = build_fingerprint(event_b)

    keyword_score = jaccard_similarity(
        fp_a["keywords"],
        fp_b["keywords"],
    )

    entity_score = jaccard_similarity(
        fp_a["entities"],
        fp_b["entities"],
    )

    anchor_score = jaccard_similarity(
        fp_a["anchors"],
        fp_b["anchors"],
    )

    year_overlap = bool(
        fp_a["years"] & fp_b["years"]
    )

    measurement_overlap = bool(
        fp_a["measurements"]
        & fp_b["measurements"]
    )

    number_overlap = bool(
        fp_a["numbers"]
        & fp_b["numbers"]
    )

    # ---------------------------------------------------------
    # EVENT IDENTITY
    # ---------------------------------------------------------

    # Strong event-specific evidence.
    strong_anchor_match = (
        anchor_score >= 0.30
        or year_overlap
        or measurement_overlap
        or number_overlap
    )

    # If both stories have event-specific anchors but
    # none of them overlap, treat that as contradictory
    # evidence rather than simply ignoring it.
    both_have_anchors = (
        bool(fp_a["anchors"])
        and bool(fp_b["anchors"])
    )

    anchor_conflict = (
        both_have_anchors
        and anchor_score == 0.0
    )

    # Base topic similarity.
    topic_score = (
        keyword_score * 0.55
        + entity_score * 0.45
    )

    # Same-event decision.
    same_event = False

    if not anchor_conflict:

        # Strong topic + event-specific evidence.
        if (
            topic_score >= 0.55
            and strong_anchor_match
        ):
            same_event = True

        # Very strong topic similarity can still produce
        # a candidate even without explicit anchors.
        elif topic_score >= 0.80:
            same_event = True

    # Final score.
    score = (
        topic_score * 0.65
        + anchor_score * 0.35
    )

    return {
        "score": round(score, 3),

        "keyword_score": round(
            keyword_score,
            3,
        ),

        "entity_score": round(
            entity_score,
            3,
        ),

        "anchor_score": round(
            anchor_score,
            3,
        ),

        "year_overlap": year_overlap,

        "measurement_overlap": measurement_overlap,

        "number_overlap": number_overlap,

        "anchor_conflict": anchor_conflict,

        "same_event_candidate": same_event,
    }