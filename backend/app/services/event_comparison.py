from dataclasses import dataclass

from app.services.event_fingerprint import (
    EventFingerprint,
    NormalizedMeasurement,
    build_event_fingerprint,
)


@dataclass
class EventComparison:
    relationship: str

    score: float

    topic_score: float
    entity_score: float
    keyword_score: float

    measurement_match: bool
    year_match: bool

    marker_overlap: set[str]

    reasons: list[str]


def jaccard(set_a: set, set_b: set) -> float:
    if not set_a or not set_b:
        return 0.0

    intersection = set_a & set_b
    union = set_a | set_b

    return len(intersection) / len(union)


def measurements_match(
    measurements_a: list[NormalizedMeasurement],
    measurements_b: list[NormalizedMeasurement],
    tolerance: float = 0.03,
) -> bool:

    for measurement_a in measurements_a:

        for measurement_b in measurements_b:

            if measurement_a.meters == 0:
                continue

            difference = abs(
                measurement_a.meters
                - measurement_b.meters
            )

            relative_difference = (
                difference
                / measurement_a.meters
            )

            if relative_difference <= tolerance:
                return True

    return False


def compare_event_fingerprints(
    fingerprint_a: EventFingerprint,
    fingerprint_b: EventFingerprint,
) -> EventComparison:

    entity_score = jaccard(
        fingerprint_a.entities,
        fingerprint_b.entities,
    )

    keyword_score = jaccard(
        fingerprint_a.keywords,
        fingerprint_b.keywords,
    )

    marker_overlap = (
        fingerprint_a.event_markers
        & fingerprint_b.event_markers
    )

    measurement_match = measurements_match(
        fingerprint_a.measurements,
        fingerprint_b.measurements,
    )

    year_match = bool(
        fingerprint_a.years
        & fingerprint_b.years
    )

    # Topic similarity is intentionally modest.
    #
    # NASA + Moon + crater should tell us
    # that two stories concern the same topic,
    # but NOT that they describe the same event.

    topic_score = (
        entity_score * 0.60
        + keyword_score * 0.40
    )

    score = topic_score

    reasons = []

    if entity_score > 0:
        reasons.append(
            f"Entity overlap: {entity_score:.2f}"
        )

    if keyword_score > 0:
        reasons.append(
            f"Keyword overlap: {keyword_score:.2f}"
        )

    if measurement_match:
        score += 0.25

        reasons.append(
            "Measurements are approximately equivalent."
        )

    if year_match:
        score += 0.15

        reasons.append(
            "The same year is mentioned."
        )

    if marker_overlap:
        score += 0.10

        reasons.append(
            "Event markers overlap: "
            + ", ".join(sorted(marker_overlap))
        )

    score = min(score, 1.0)

    # --------------------------------------------------
    # Relationship determination
    # --------------------------------------------------

    # Strong event-specific evidence.
    if measurement_match and topic_score >= 0.50:
        relationship = "SAME EVENT"

    elif (
        topic_score >= 0.60
        and (
            year_match
            or bool(marker_overlap)
            or entity_score >= 0.75
        )
    ):
        relationship = "LIKELY SAME STORY"

    elif topic_score >= 0.75:
        relationship = "LIKELY SAME STORY"

    elif topic_score >= 0.35:
        relationship = "RELATED"

    else:
        relationship = "DIFFERENT"

    return EventComparison(
        relationship=relationship,

        score=round(score, 3),

        topic_score=round(
            topic_score,
            3,
        ),

        entity_score=round(
            entity_score,
            3,
        ),

        keyword_score=round(
            keyword_score,
            3,
        ),

        measurement_match=measurement_match,

        year_match=year_match,

        marker_overlap=marker_overlap,

        reasons=reasons,
    )


def compare_events(
    event_a,
    event_b,
) -> EventComparison:

    fingerprint_a = build_event_fingerprint(
        event_a
    )

    fingerprint_b = build_event_fingerprint(
        event_b
    )

    return compare_event_fingerprints(
        fingerprint_a,
        fingerprint_b,
    )