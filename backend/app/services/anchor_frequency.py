from collections import Counter
from dataclasses import dataclass
import math

from app.services.event_fingerprint import build_event_fingerprint


@dataclass
class AnchorStats:
    anchor: str
    category: str
    count: int
    weight: float


def event_anchors(event) -> dict[str, set[str]]:
    """
    Build identity anchors grouped by category.

    Categories allow us to prevent the same underlying clue
    from being counted multiple times.
    """

    fingerprint = build_event_fingerprint(event)

    anchors = {
        "entity": set(),
        "year": set(),
        "marker": set(),
        "measurement": set(),
    }

    for entity in fingerprint.entities:
        anchors["entity"].add(
            f"entity:{entity}"
        )

    for year in fingerprint.years:
        anchors["year"].add(
            f"year:{year}"
        )

    for marker in fingerprint.event_markers:
        anchors["marker"].add(
            f"marker:{marker}"
        )

    for measurement in fingerprint.measurements:
        meters = round(measurement.meters, 2)

        anchors["measurement"].add(
            f"measurement:{meters}m"
        )

    return anchors


def calculate_anchor_frequencies(events) -> Counter:
    """
    Count how many different events contain each anchor.
    """

    frequency = Counter()

    for event in events:
        categorized = event_anchors(event)

        for category_anchors in categorized.values():
            for anchor in category_anchors:
                frequency[anchor] += 1

    return frequency


def calculate_anchor_weight(
    anchor: str,
    frequency: Counter,
    total_events: int,
) -> float:

    if total_events <= 0:
        return 0.0

    count = frequency.get(anchor, 0)

    if count <= 0:
        return 0.0

    return math.log(
        (total_events + 1) / (count + 1)
    ) + 1.0


def get_anchor_category(anchor: str) -> str:

    if ":" not in anchor:
        return "unknown"

    return anchor.split(":", 1)[0]


def calculate_anchor_stats(events) -> list[AnchorStats]:

    frequency = calculate_anchor_frequencies(events)

    total_events = len(events)

    stats = []

    for anchor, count in frequency.items():

        weight = calculate_anchor_weight(
            anchor=anchor,
            frequency=frequency,
            total_events=total_events,
        )

        stats.append(
            AnchorStats(
                anchor=anchor,
                category=get_anchor_category(anchor),
                count=count,
                weight=weight,
            )
        )

    stats.sort(
        key=lambda item: (
            -item.weight,
            item.count,
            item.anchor,
        )
    )

    return stats