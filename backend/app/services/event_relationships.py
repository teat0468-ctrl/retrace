from dataclasses import dataclass

from app.services.event_comparison import compare_events


@dataclass
class EventRelationship:
    source_event_index: int
    target_event_index: int

    relationship: str
    score: float

    reasons: list[str]


def build_event_relationships(events):

    relationships = []

    for i in range(len(events)):

        for j in range(i + 1, len(events)):

            event_a = events[i]
            event_b = events[j]

            comparison = compare_events(
                event_a,
                event_b,
            )

            relationships.append(
                EventRelationship(
                    source_event_index=i,
                    target_event_index=j,
                    relationship=comparison.relationship,
                    score=comparison.score,
                    reasons=comparison.reasons,
                )
            )

    return relationships