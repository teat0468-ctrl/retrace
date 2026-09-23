from dataclasses import dataclass


@dataclass
class ChangeSignal:
    category: str
    label: str
    description: str
    source_event_index: int
    target_event_index: int
    severity: str


def _set(event, attribute):
    value = getattr(event, attribute, None)
    return set(value or [])


# Human-readable labels for each domain-agnostic marker
MARKER_LABELS = {
    "newly_discovered": "newly discovered",
    "newly_formed": "newly formed",
    "impact_event": "impact/explosion event",
    "study_claim": "scientific/research claim",
    "debunked": "debunked or fact-checked",
    "outdated_research": "outdated research cited",
    "once_in_a_century": "once-in-a-century significance",
    "policy_change": "policy/legal change",
    "health_alert": "health alert",
    "economic_signal": "economic signal",
    "detection_delay": "detection or visibility delay",
    "reshared_old": "re-shared old content",
}

# Pairs that represent a meaningful claim shift
CONTESTED_MARKER_PAIRS = [
    # A story flips from "discovered" to "formed" (different factual claim)
    ("newly_discovered", "newly_formed"),
    # A story flips from health alert to debunked
    ("health_alert", "debunked"),
    # A story that was a study claim is now marked debunked
    ("study_claim", "debunked"),
]


def compare_event_details(source, target, source_index, target_index):
    changes = []

    source_markers = _set(source, "event_markers")
    target_markers = _set(target, "event_markers")

    source_measurements = _set(source, "measurements")
    target_measurements = _set(target, "measurements")

    source_years = _set(source, "years")
    target_years = _set(target, "years")

    # ---------------------------------------------------------
    # 1. New event markers introduced in the later headline
    # ---------------------------------------------------------

    added_markers = target_markers - source_markers

    for marker in added_markers:
        label = MARKER_LABELS.get(marker, marker.replace("_", " "))

        changes.append(
            ChangeSignal(
                category="new_detail",
                label=label,
                description=(
                    f'The later headline introduces the detail '
                    f'"{label}".'
                ),
                source_event_index=source_index,
                target_event_index=target_index,
                severity="medium",
            )
        )

    # ---------------------------------------------------------
    # 2. Markers removed in the later headline
    # ---------------------------------------------------------

    removed_markers = source_markers - target_markers

    for marker in removed_markers:
        label = MARKER_LABELS.get(marker, marker.replace("_", " "))

        changes.append(
            ChangeSignal(
                category="omitted_detail",
                label=label,
                description=(
                    f'The later headline no longer mentions '
                    f'"{label}".'
                ),
                source_event_index=source_index,
                target_event_index=target_index,
                severity="low",
            )
        )

    # ---------------------------------------------------------
    # 3. Contested claim pairs — significant semantic flips
    # ---------------------------------------------------------

    for marker_a, marker_b in CONTESTED_MARKER_PAIRS:
        if marker_a in source_markers and marker_b in target_markers:
            label_a = MARKER_LABELS.get(marker_a, marker_a.replace("_", " "))
            label_b = MARKER_LABELS.get(marker_b, marker_b.replace("_", " "))
            changes.append(
                ChangeSignal(
                    category="claim_change",
                    label=f"{label_a} → {label_b}",
                    description=(
                        f"The narrative shifts from \"{label_a}\" "
                        f"to \"{label_b}\" — a significant factual change."
                    ),
                    source_event_index=source_index,
                    target_event_index=target_index,
                    severity="high",
                )
            )

        if marker_b in source_markers and marker_a in target_markers:
            label_a = MARKER_LABELS.get(marker_a, marker_a.replace("_", " "))
            label_b = MARKER_LABELS.get(marker_b, marker_b.replace("_", " "))
            changes.append(
                ChangeSignal(
                    category="claim_change",
                    label=f"{label_b} → {label_a}",
                    description=(
                        f"The narrative shifts from \"{label_b}\" "
                        f"to \"{label_a}\" — a significant factual change."
                    ),
                    source_event_index=source_index,
                    target_event_index=target_index,
                    severity="high",
                )
            )

    # ---------------------------------------------------------
    # 4. Measurements changed
    # ---------------------------------------------------------

    if source_measurements and target_measurements:
        if source_measurements != target_measurements:
            changes.append(
                ChangeSignal(
                    category="measurement",
                    label="measurement wording changed",
                    description=(
                        "The reported figures or measurements differ "
                        "between the two headlines."
                    ),
                    source_event_index=source_index,
                    target_event_index=target_index,
                    severity="medium",
                )
            )

    # ---------------------------------------------------------
    # 5. Year references introduced
    # ---------------------------------------------------------

    added_years = target_years - source_years

    for year in added_years:
        changes.append(
            ChangeSignal(
                category="date_detail",
                label=f"year {year} introduced",
                description=(
                    f"The later headline introduces the year {year}, "
                    f"suggesting a historical reference was added."
                ),
                source_event_index=source_index,
                target_event_index=target_index,
                severity="medium",
            )
        )

    # ---------------------------------------------------------
    # 6. Named Entities changed
    # ---------------------------------------------------------
    
    source_entities = _set(source, "entities")
    target_entities = _set(target, "entities")
    
    added_entities = target_entities - source_entities
    if added_entities:
        changes.append(
            ChangeSignal(
                category="new_entity",
                label="new entities mentioned",
                description=(
                    f"The later reporting introduces new entities: {', '.join(added_entities)}."
                ),
                source_event_index=source_index,
                target_event_index=target_index,
                severity="medium", # Triggers DEVELOPING
            )
        )
        
    removed_entities = source_entities - target_entities
    if removed_entities:
        changes.append(
            ChangeSignal(
                category="omitted_entity",
                label="entities dropped",
                description=(
                    f"The later reporting drops mention of: {', '.join(removed_entities)}."
                ),
                source_event_index=source_index,
                target_event_index=target_index,
                severity="low", # Triggers DEVELOPING
            )
        )

    return changes