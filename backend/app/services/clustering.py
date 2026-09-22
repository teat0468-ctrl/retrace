from dataclasses import dataclass

from app.services.event_comparison import compare_events


@dataclass
class EventCluster:
    cluster_id: int
    events: list
    representative: object


def cluster_events(events):

    clusters = []

    for event in events:

        best_cluster = None
        best_score = 0.0

        for cluster in clusters:

            representative = cluster.representative

            comparison = compare_events(
                event,
                representative,
            )

            # IMPORTANT:
            #
            # Only an explicit SAME EVENT relationship
            # is allowed to merge an event into a cluster.
            #
            # RELATED / UNKNOWN / DIFFERENT do not merge.

            if comparison.relationship != "SAME EVENT":
                continue

            if comparison.score > best_score:

                best_score = comparison.score
                best_cluster = cluster

        if best_cluster is None:

            cluster = EventCluster(
                cluster_id=len(clusters) + 1,
                events=[event],
                representative=event,
            )

            clusters.append(cluster)

        else:

            best_cluster.events.append(
                event
            )

    return clusters