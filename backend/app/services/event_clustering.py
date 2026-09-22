from dataclasses import dataclass

from app.services.event_matcher import classify_event_match
from app.services.anchor_frequency import calculate_anchor_frequencies


@dataclass
class EventCluster:
    cluster_id: int
    event_indices: list[int]


class UnionFind:
    def __init__(self, size: int):
        self.parent = list(range(size))
        self.rank = [0] * size

    def find(self, x: int) -> int:
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])

        return self.parent[x]

    def union(self, a: int, b: int):
        root_a = self.find(a)
        root_b = self.find(b)

        if root_a == root_b:
            return

        if self.rank[root_a] < self.rank[root_b]:
            self.parent[root_a] = root_b

        elif self.rank[root_a] > self.rank[root_b]:
            self.parent[root_b] = root_a

        else:
            self.parent[root_b] = root_a
            self.rank[root_a] += 1


def cluster_events(events):
    if not events:
        return []

    frequency = calculate_anchor_frequencies(events)

    union_find = UnionFind(len(events))

    strong_edges = []

    for i in range(len(events)):
        for j in range(i + 1, len(events)):

            match = classify_event_match(
                event_a=events[i],
                event_b=events[j],
                frequency=frequency,
                total_events=len(events),
            )

            if match.relationship in {
                "SAME EVENT",
                "LIKELY SAME STORY",
            }:
                union_find.union(i, j)

                strong_edges.append({
                    "source_event_index": i,
                    "target_event_index": j,
                    "relationship": match.relationship,
                    "score": match.score,
                })

    groups = {}

    for event_index in range(len(events)):
        root = union_find.find(event_index)

        if root not in groups:
            groups[root] = []

        groups[root].append(event_index)

    clusters = []

    for cluster_id, event_indices in enumerate(
        groups.values(),
        start=1,
    ):
        clusters.append(
            EventCluster(
                cluster_id=cluster_id,
                event_indices=event_indices,
            )
        )

    clusters.sort(
        key=lambda cluster: len(cluster.event_indices),
        reverse=True,
    )

    return clusters