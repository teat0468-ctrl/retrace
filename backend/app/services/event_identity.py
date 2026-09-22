from dataclasses import dataclass

from app.services.anchor_frequency import (
    calculate_anchor_weight,
    event_anchors,
)
from app.services.event_identity_rules import event_compatibility

@dataclass
class EventIdentityComparison:
    score: float
    shared_anchors: list[str]
    strong_anchors: list[str]
    supporting_anchors: list[str]
    topic_anchors: list[str]
    reasons: list[str]
    measurement_match: bool
    shared_entities: list[str]
    shared_years: list[str]
    shared_markers: list[str]


def anchor_strength(
    anchor: str,
    frequency,
    total_events: int,
) -> str:
    """
    Determine how useful an anchor is for identifying
    a specific event.

    Frequency is important because common anchors such as
    NASA and Moon should not identify an event by themselves.
    """

    weight = calculate_anchor_weight(
        anchor,
        frequency,
        total_events,
    )

    category = anchor.split(":", 1)[0]

    # Measurements are inherently useful identity clues.
    if category == "measurement":
        return "strong"

    # Very rare named entities are useful.
    if category == "entity" and weight >= 4.0:
        return "strong"

    # A rare year can be useful.
    if category == "year" and weight >= 3.5:
        return "strong"

    # Rare event markers can support identity.
    if category == "marker" and weight >= 4.0:
        return "supporting"

    # Moderately distinctive anchors.
    if weight >= 2.5:
        return "supporting"

    # Everything common becomes topic-level.
    return "topic"


def compare_event_identity(
    event_a,
    event_b,
    frequency,
    total_events,
) -> EventIdentityComparison:

    anchors_a = event_anchors(event_a)
    anchors_b = event_anchors(event_b)

    shared_anchors = []
    strong_anchors = []
    supporting_anchors = []
    topic_anchors = []

    for category in anchors_a:

        overlap = (
            anchors_a[category]
            & anchors_b.get(category, set())
        )

        for anchor in overlap:

            shared_anchors.append(anchor)

            strength = anchor_strength(
                anchor,
                frequency,
                total_events,
            )

            if strength == "strong":
                strong_anchors.append(anchor)

            elif strength == "supporting":
                supporting_anchors.append(anchor)

            else:
                topic_anchors.append(anchor)

    # ---------------------------------------------------------
    # Identity + compatibility
    # ---------------------------------------------------------

    compatibility = event_compatibility(
        event_a,
        event_b,
    )

    measurement_match = compatibility["measurement_match"]
    shared_entities = compatibility["shared_entities"]
    shared_years = compatibility["shared_years"]
    shared_markers = compatibility["shared_markers"]

    score = 0.0

    # ---------------------------------------------------------
    # Measurements are our strongest current identity signal.
    # ---------------------------------------------------------

    if measurement_match:
        score += 0.75

    # ---------------------------------------------------------
    # Rare identity anchors.
    # ---------------------------------------------------------

    if strong_anchors:
        score += 0.15

    # ---------------------------------------------------------
    # Supporting evidence.
    # ---------------------------------------------------------

    if supporting_anchors:
        score += 0.05

    # ---------------------------------------------------------
    # Compatibility bonuses.
    # ---------------------------------------------------------

    if measurement_match and shared_entities:
        score += 0.05

    score = min(score, 1.0)
    reasons = []

    if strong_anchors:
        reasons.append(
            "Strong identity evidence: "
            + ", ".join(sorted(strong_anchors))
        )

    if supporting_anchors:
        reasons.append(
            "Supporting evidence: "
            + ", ".join(sorted(supporting_anchors))
        )

    if topic_anchors:
        reasons.append(
            "Shared topic only: "
            + ", ".join(sorted(topic_anchors))
        )

    return EventIdentityComparison(
        score=round(score, 4),
        shared_anchors=sorted(shared_anchors),
        strong_anchors=sorted(strong_anchors),
        supporting_anchors=sorted(supporting_anchors),
        topic_anchors=sorted(topic_anchors),
        measurement_match=measurement_match,
        shared_entities=shared_entities,
        shared_years=shared_years,
        shared_markers=shared_markers,
        reasons=reasons,
    )