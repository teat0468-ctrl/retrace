from app.services.event_fingerprint import build_event_fingerprint
from app.services.event_comparison import measurements_match


def same_measurement(event_a, event_b) -> bool:
    fingerprint_a = build_event_fingerprint(event_a)
    fingerprint_b = build_event_fingerprint(event_b)

    return measurements_match(
        fingerprint_a.measurements,
        fingerprint_b.measurements,
    )


def shared_entities(event_a, event_b) -> set[str]:
    fingerprint_a = build_event_fingerprint(event_a)
    fingerprint_b = build_event_fingerprint(event_b)

    return (
        fingerprint_a.entities
        & fingerprint_b.entities
    )


def shared_years(event_a, event_b) -> set[str]:
    fingerprint_a = build_event_fingerprint(event_a)
    fingerprint_b = build_event_fingerprint(event_b)

    return (
        fingerprint_a.years
        & fingerprint_b.years
    )


def shared_markers(event_a, event_b) -> set[str]:
    fingerprint_a = build_event_fingerprint(event_a)
    fingerprint_b = build_event_fingerprint(event_b)

    return (
        fingerprint_a.event_markers
        & fingerprint_b.event_markers
    )


def event_compatibility(
    event_a,
    event_b,
) -> dict:

    measurement_match = same_measurement(
        event_a,
        event_b,
    )

    entities = shared_entities(
        event_a,
        event_b,
    )

    years = shared_years(
        event_a,
        event_b,
    )

    markers = shared_markers(
        event_a,
        event_b,
    )

    return {
        "measurement_match": measurement_match,
        "shared_entities": sorted(entities),
        "shared_years": sorted(years),
        "shared_markers": sorted(markers),
    }