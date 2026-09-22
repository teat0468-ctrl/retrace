from dataclasses import dataclass

from app.services.event_identity import compare_event_identity
from app.services.event_identity_rules import event_compatibility


@dataclass
class EventMatch:
    relationship: str
    score: float
    reasons: list[str]

    strong_identity: bool
    measurement_match: bool

    shared_entities: list[str]
    shared_years: list[str]
    shared_markers: list[str]

    strong_anchors: list[str]
    supporting_anchors: list[str]


def classify_event_match(
    event_a,
    event_b,
    frequency,
    total_events,
) -> EventMatch:

    identity = compare_event_identity(
        event_a=event_a,
        event_b=event_b,
        frequency=frequency,
        total_events=total_events,
    )

    compatibility = event_compatibility(
        event_a,
        event_b,
    )

    measurement_match = compatibility["measurement_match"]
    shared_entities = compatibility["shared_entities"]
    shared_years = compatibility["shared_years"]
    shared_markers = compatibility["shared_markers"]

    strong_anchors = identity.strong_anchors
    supporting_anchors = identity.supporting_anchors

    reasons = []

    # ---------------------------------------------------------
    # 1. Exact distinctive measurement + shared entities
    # ---------------------------------------------------------

    if measurement_match and shared_entities:

        measurement_anchors = [
            anchor
            for anchor in strong_anchors
            if anchor.startswith("measurement:")
        ]

        if measurement_anchors:

            # If both titles contain the same normalized
            # measurement, this is strong event identity.
            exact_measurement_match = (
                any(
                    anchor.startswith("measurement:")
                    for anchor in identity.shared_anchors
                )
            )

            if exact_measurement_match:

                return EventMatch(
                    relationship="SAME EVENT",
                    score=0.95,
                    reasons=[
                        "The sources share the same normalized "
                        "measurement and compatible entities."
                    ],
                    strong_identity=True,
                    measurement_match=True,
                    shared_entities=shared_entities,
                    shared_years=shared_years,
                    shared_markers=shared_markers,
                    strong_anchors=strong_anchors,
                    supporting_anchors=supporting_anchors,
                )

    # ---------------------------------------------------------
    # 2. Multiple independent strong anchors
    # ---------------------------------------------------------

    independent_strong_anchors = set()

    for anchor in strong_anchors:

        # Avoid counting duplicate representations of
        # the same underlying clue.
        if anchor.startswith("entity:"):
            independent_strong_anchors.add(
                anchor.replace("entity:", "identity:")
            )

        elif anchor.startswith("measurement:"):
            independent_strong_anchors.add(
                anchor.replace("measurement:", "measurement:")
            )

        elif anchor.startswith("year:"):
            independent_strong_anchors.add(
                anchor.replace("year:", "year:")
            )

    if (
        len(independent_strong_anchors) >= 2
        and shared_entities
    ):

        return EventMatch(
            relationship="SAME EVENT",
            score=0.90,
            reasons=[
                "Multiple independent distinctive identity "
                "signals are shared with compatible entities."
            ],
            strong_identity=True,
            measurement_match=measurement_match,
            shared_entities=shared_entities,
            shared_years=shared_years,
            shared_markers=shared_markers,
            strong_anchors=strong_anchors,
            supporting_anchors=supporting_anchors,
        )

    # ---------------------------------------------------------
    # 3. Converted measurement + contextual evidence
    # ---------------------------------------------------------

    if measurement_match and shared_entities:

        context_signals = 0

        if shared_years:
            context_signals += 1

        if shared_markers:
            context_signals += 1

        if len(shared_entities) >= 2:
            context_signals += 1

        if context_signals >= 1:

            return EventMatch(
                relationship="LIKELY SAME STORY",
                score=0.78,
                reasons=[
                    "The reported measurements are approximately "
                    "equivalent and the sources share supporting "
                    "event context."
                ],
                strong_identity=False,
                measurement_match=True,
                shared_entities=shared_entities,
                shared_years=shared_years,
                shared_markers=shared_markers,
                strong_anchors=strong_anchors,
                supporting_anchors=supporting_anchors,
            )

    # ---------------------------------------------------------
    # 4. Distinctive year + event marker + entity
    # ---------------------------------------------------------

    if (
        shared_years
        and shared_markers
        and shared_entities
    ):

        return EventMatch(
            relationship="LIKELY SAME STORY",
            score=0.75,
            reasons=[
                "The sources share a specific year, "
                "event characteristic, and compatible entities."
            ],
            strong_identity=True,
            measurement_match=False,
            shared_entities=shared_entities,
            shared_years=shared_years,
            shared_markers=shared_markers,
            strong_anchors=strong_anchors,
            supporting_anchors=supporting_anchors,
        )

    # ---------------------------------------------------------
    # 5. Two or more useful supporting signals
    # ---------------------------------------------------------

    supporting_signal_count = 0

    if shared_markers:
        supporting_signal_count += 1

    if shared_years:
        supporting_signal_count += 1

    if len(shared_entities) >= 2:
        supporting_signal_count += 1

    if (
        supporting_signal_count >= 2
        and shared_entities
    ):

        return EventMatch(
            relationship="RELATED",
            score=0.35,
            reasons=[
                "The sources share multiple contextual signals, "
                "but not enough identity evidence."
            ],
            strong_identity=False,
            measurement_match=measurement_match,
            shared_entities=shared_entities,
            shared_years=shared_years,
            shared_markers=shared_markers,
            strong_anchors=strong_anchors,
            supporting_anchors=supporting_anchors,
        )

    # ---------------------------------------------------------
    # 6. Broad topic overlap is not useful relationship evidence
    # ---------------------------------------------------------

    return EventMatch(
        relationship="DIFFERENT",
        score=0.0,
        reasons=[
            "No sufficiently distinctive event identity evidence."
        ],
        strong_identity=False,
        measurement_match=False,
        shared_entities=[],
        shared_years=[],
        shared_markers=[],
        strong_anchors=[],
        supporting_anchors=[],
    )