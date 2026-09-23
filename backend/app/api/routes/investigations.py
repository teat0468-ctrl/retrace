from datetime import datetime
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.services.event_relationships import build_event_relationships
from app.db.database import SessionLocal
from app.db.tables import Investigation, Source, Event, TrendSignal
from app.services.trends import get_trends
from app.services.verdict import generate_verdict
from app.services.events import extract_events
from app.services.event_comparison import compare_events
from app.services.what_changed import compare_event_details
from app.services.event_identity import compare_event_identity
from app.services.anchor_frequency import calculate_anchor_frequencies
from app.services.anchor_frequency import calculate_anchor_stats
from app.services.event_matcher import classify_event_match
from app.services.event_clustering import cluster_events
from app.services.evidence import (
    collect_evidence,
    deduplicate_evidence,
)
from app.services.investigation import (
    analyze_claim,
    build_search_plan,
)


router = APIRouter(
    prefix="/investigations",
    tags=["Investigations"],
)


class InvestigationCreate(BaseModel):
    claim: str = Field(min_length=3, max_length=5000)


class InvestigationResponse(BaseModel):
    id: int
    claim: str
    status: str
    created_at: datetime

    model_config = {
        "from_attributes": True
    }


class SearchPlanItem(BaseModel):
    query: str
    engine: str
    purpose: str


class ClaimAnalysisResponse(BaseModel):
    original_claim: str
    normalized_claim: str
    claim_type: str
    entities: list[str]
    keywords: list[str]


class EvidenceResponse(BaseModel):
    title: str | None
    url: str | None
    publisher: str | None
    published_at: datetime | None
    source_type: str
    purpose: str


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


@router.post(
    "",
    response_model=InvestigationResponse,
)
def create_investigation(
    data: InvestigationCreate,
    db: Session = Depends(get_db),
):
    investigation = Investigation(
        claim=data.claim.strip(),
        status="created",
        created_at=datetime.utcnow(),
    )

    db.add(investigation)
    db.commit()
    db.refresh(investigation)

    return investigation


@router.get(
    "/{investigation_id}",
    response_model=InvestigationResponse,
)
def get_investigation(
    investigation_id: int,
    db: Session = Depends(get_db),
):
    investigation = (
        db.query(Investigation)
        .filter(Investigation.id == investigation_id)
        .first()
    )

    if investigation is None:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found",
        )

    return investigation


@router.get(
    "/{investigation_id}/analyze",
    response_model=ClaimAnalysisResponse,
)
def analyze_investigation(
    investigation_id: int,
    db: Session = Depends(get_db),
):
    investigation = (
        db.query(Investigation)
        .filter(Investigation.id == investigation_id)
        .first()
    )

    if investigation is None:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found",
        )

    return analyze_claim(investigation.claim)


@router.get(
    "/{investigation_id}/search-plan",
    response_model=list[SearchPlanItem],
)
def get_search_plan(
    investigation_id: int,
    db: Session = Depends(get_db),
):
    investigation = (
        db.query(Investigation)
        .filter(Investigation.id == investigation_id)
        .first()
    )

    if investigation is None:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found",
        )

    return build_search_plan(investigation.claim)


@router.get(
    "/{investigation_id}/collect-evidence",
    response_model=list[EvidenceResponse],
)
def collect_investigation_evidence(
    investigation_id: int,
    db: Session = Depends(get_db),
):
    investigation = (
        db.query(Investigation)
        .filter(Investigation.id == investigation_id)
        .first()
    )

    if investigation is None:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found",
        )

    search_plan = build_search_plan(investigation.claim)

    evidence = collect_evidence(search_plan)

    return deduplicate_evidence(evidence)


@router.post(
    "/{investigation_id}/collect",
    response_model=list[EvidenceResponse],
)
def collect_and_store_evidence(
    investigation_id: int,
    db: Session = Depends(get_db),
):
    investigation = (
        db.query(Investigation)
        .filter(Investigation.id == investigation_id)
        .first()
    )

    if investigation is None:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found",
        )

    # Remove previously collected sources for this investigation.
    # The SerpApi responses remain safely cached on disk.
    db.query(Source).filter(
        Source.investigation_id == investigation_id
    ).delete(
        synchronize_session=False
    )

    db.commit()

    search_plan = build_search_plan(investigation.claim)

    evidence = collect_evidence(search_plan)
    evidence = deduplicate_evidence(evidence)

    stored_sources = []

    for item in evidence:
        source = Source(
            investigation_id=investigation.id,
            title=item.get("title") or "Untitled",
            url=item.get("url"),
            publisher=item.get("publisher"),
            published_at=item.get("published_at"),
            source_type=item.get("source_type"),
            search_purpose=item.get("purpose"),
            relevance=None,
        )

        db.add(source)
        stored_sources.append(source)

    investigation.status = "evidence_collected"

    db.commit()

    for source in stored_sources:
        db.refresh(source)

    return [
        {
            "title": source.title,
            "url": source.url,
            "publisher": source.publisher,
            "published_at": source.published_at,
            "source_type": source.source_type,
            "purpose": "stored",
        }
        for source in stored_sources
    ]

@router.post(
    "/{investigation_id}/extract-events",
)
def extract_investigation_events(
    investigation_id: int,
    db: Session = Depends(get_db),
):
    investigation = (
        db.query(Investigation)
        .filter(Investigation.id == investigation_id)
        .first()
    )

    if investigation is None:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found",
        )

    sources = (
        db.query(Source)
        .filter(Source.investigation_id == investigation_id)
        .all()
    )

    candidates = extract_events(sources)

    return [
        {
            "source_id": candidate.source_id,
            "title": candidate.title,
            "event_date": candidate.event_date,
            "entities": candidate.entities,
            "event_keywords": candidate.event_keywords,
            "measurements": candidate.measurements,
            "source_type": candidate.source_type,
            "search_purpose": candidate.search_purpose,
            "years": candidate.years,
            "event_markers": candidate.event_markers,   
        }
        for candidate in candidates
    ]

@router.post(
    "/{investigation_id}/cluster-events",
)
def cluster_investigation_events(
    investigation_id: int,
    db: Session = Depends(get_db),
):
    investigation = (
        db.query(Investigation)
        .filter(Investigation.id == investigation_id)
        .first()
    )

    if investigation is None:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found",
        )

    sources = (
        db.query(Source)
        .filter(Source.investigation_id == investigation_id)
        .all()
    )

    candidates = extract_events(sources)

    clusters = cluster_events(candidates)

    return [
        {
            "cluster_id": cluster.cluster_id,
            "event_count": len(cluster.events),
            "representative": {
                "title": cluster.representative.title,
                "source_id": cluster.representative.source_id,
                "event_date": cluster.representative.event_date,
                "entities": cluster.representative.entities,
                "event_keywords": cluster.representative.event_keywords,
                "measurements": cluster.representative.measurements,
            },
            "events": [
                {
                    "title": event.title,
                    "source_id": event.source_id,
                    "event_date": event.event_date,
                    "entities": event.entities,
                    "event_keywords": event.event_keywords,
                    "measurements": event.measurements,
                }
                for event in cluster.events
            ],
        }
        for cluster in clusters
    ]

@router.post(
    "/{investigation_id}/event-relationships",
)
def get_event_relationships(
    investigation_id: int,
    db: Session = Depends(get_db),
):
    investigation = (
        db.query(Investigation)
        .filter(
            Investigation.id == investigation_id
        )
        .first()
    )

    if investigation is None:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found",
        )

    sources = (
        db.query(Source)
        .filter(
            Source.investigation_id
            == investigation_id
        )
        .all()
    )

    candidates = extract_events(
        sources
    )

    relationships = build_event_relationships(
        candidates
    )

    return {
        "event_count": len(candidates),

        "relationship_count": len(
            relationships
        ),

        "events": [
            {
                "index": index,
                "source_id": event.source_id,
                "title": event.title,
                "event_date": event.event_date,
                "entities": event.entities,
                "event_markers": event.event_markers,
                "measurements": event.measurements,
            }
            for index, event in enumerate(
                candidates
            )
        ],

        "relationships": [
            {
                "source_event_index":
                    relationship.source_event_index,

                "target_event_index":
                    relationship.target_event_index,

                "relationship":
                    relationship.relationship,

                "score":
                    relationship.score,

                "reasons":
                    relationship.reasons,
            }
            for relationship in relationships
        ],
    }

@router.post(
    "/{investigation_id}/debug-event-matches",
)
def debug_event_matches(
    investigation_id: int,
    db: Session = Depends(get_db),
):
    investigation = (
        db.query(Investigation)
        .filter(
            Investigation.id == investigation_id
        )
        .first()
    )

    if investigation is None:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found",
        )

    sources = (
        db.query(Source)
        .filter(
            Source.investigation_id == investigation_id
        )
        .all()
    )

    candidates = extract_events(sources)

    matches = []

    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            comparison = compare_events(
                candidates[i],
                candidates[j],
            )

            if comparison.relationship in {"SAME EVENT", "LIKELY SAME STORY",}:
                matches.append(
                    {
                        "source_event_index": i,
                        "target_event_index": j,
                        "source_title": candidates[i].title,
                        "target_title": candidates[j].title,
                        "source_date": candidates[i].event_date,
                        "target_date": candidates[j].event_date,
                        "relationship": comparison.relationship,
                        "score": comparison.score,
                        "topic_score": comparison.topic_score,
                        "measurement_match": comparison.measurement_match,
                        "year_match": comparison.year_match,
                        "marker_overlap": list(
                            comparison.marker_overlap
                        ),
                        "reasons": comparison.reasons,
                    }
                )

    matches.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return {
        "event_count": len(candidates),
        "same_event_count": len(matches),
        "matches": matches,
    }

@router.post(
    "/{investigation_id}/what-changed",
)
def get_what_changed(
    investigation_id: int,
    db: Session = Depends(get_db),
):
    investigation = (
        db.query(Investigation)
        .filter(
            Investigation.id == investigation_id
        )
        .first()
    )

    if investigation is None:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found",
        )

    sources = (
        db.query(Source)
        .filter(
            Source.investigation_id == investigation_id
        )
        .all()
    )

    candidates = extract_events(sources)

    changes = []

    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):

            comparison = compare_events(
                candidates[i],
                candidates[j],
            )

            if comparison.relationship != "SAME EVENT":
                continue

            event_changes = compare_event_details(
                candidates[i],
                candidates[j],
                i,
                j,
            )

            changes.extend(event_changes)

    return {
        "event_count": len(candidates),
        "change_count": len(changes),
        "changes": [
            {
                "category": change.category,
                "label": change.label,
                "description": change.description,
                "source_event_index": change.source_event_index,
                "target_event_index": change.target_event_index,
                "severity": change.severity,
            }
            for change in changes
        ],
    }

@router.post("/{investigation_id}/anchor-frequency")
def get_anchor_frequency(
    investigation_id: int,
    db: Session = Depends(get_db),
):
    investigation = (
        db.query(Investigation)
        .filter(Investigation.id == investigation_id)
        .first()
    )

    if investigation is None:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found",
        )

    sources = (
        db.query(Source)
        .filter(Source.investigation_id == investigation_id)
        .all()
    )

    events = extract_events(sources)

    stats = calculate_anchor_stats(events)

    return {
        "event_count": len(events),
        "anchor_count": len(stats),
        "anchors": [
            {
                "anchor": item.anchor,
                "count": item.count,
                "weight": round(item.weight, 4),
            }
            for item in stats
        ],
    }


@router.post("/{investigation_id}/debug-event-identity")
def debug_event_identity(
    investigation_id: int,
    db: Session = Depends(get_db),
):
    investigation = (
        db.query(Investigation)
        .filter(Investigation.id == investigation_id)
        .first()
    )

    if investigation is None:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found",
        )

    sources = (
        db.query(Source)
        .filter(Source.investigation_id == investigation_id)
        .all()
    )

    events = extract_events(sources)

    frequency = calculate_anchor_frequencies(events)

    comparisons = []

    for i in range(len(events)):
        for j in range(i + 1, len(events)):

            comparison = compare_event_identity(
                events[i],
                events[j],
                frequency,
                len(events),
            )

            # Only expose meaningful overlaps.
            if not comparison.strong_anchors and not comparison.supporting_anchors:
                continue

            comparisons.append({
                "source_event_index": i,
                "target_event_index": j,
                "score": comparison.score,
                "shared_anchors": comparison.shared_anchors,
                "strong_anchors": comparison.strong_anchors,
                "supporting_anchors": comparison.supporting_anchors,
                "topic_anchors": comparison.topic_anchors,
                "source_title": events[i].title,
                "target_title": events[j].title,
            })

    comparisons.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return {
        "event_count": len(events),
        "comparison_count": len(comparisons),
        "top_matches": comparisons[:100],
    }

@router.post("/{investigation_id}/debug-event-matcher")
def debug_event_matcher(
    investigation_id: int,
    db: Session = Depends(get_db),
):
    investigation = (
        db.query(Investigation)
        .filter(Investigation.id == investigation_id)
        .first()
    )

    if investigation is None:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found",
        )

    sources = (
        db.query(Source)
        .filter(Source.investigation_id == investigation_id)
        .all()
    )

    events = extract_events(sources)

    frequency = calculate_anchor_frequencies(events)

    matches = []

    for i in range(len(events)):
        for j in range(i + 1, len(events)):

            match = classify_event_match(
                event_a=events[i],
                event_b=events[j],
                frequency=frequency,
                total_events=len(events),
            )

            if match.relationship == "DIFFERENT":
                continue

            matches.append({
                "source_event_index": i,
                "target_event_index": j,

                "relationship": match.relationship,
                "score": match.score,

                "measurement_match": match.measurement_match,

                "strong_anchors": match.strong_anchors,
                "supporting_anchors": match.supporting_anchors,

                "shared_entities": match.shared_entities,
                "shared_years": match.shared_years,
                "shared_markers": match.shared_markers,

                "reasons": match.reasons,

                "source_title": events[i].title,
                "target_title": events[j].title,
            })

    matches.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    relationship_counts = {}

    for match in matches:
        relationship = match["relationship"]

        relationship_counts[relationship] = (
            relationship_counts.get(relationship, 0) + 1
        )

    return {
        "event_count": len(events),
        "match_count": len(matches),
        "relationship_counts": relationship_counts,
        "top_matches": matches[:100],
    }

@router.post("/{investigation_id}/debug-event-clusters")
def debug_event_clusters(
    investigation_id: int,
    db: Session = Depends(get_db),
):
    investigation = (
        db.query(Investigation)
        .filter(Investigation.id == investigation_id)
        .first()
    )

    if investigation is None:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found",
        )

    sources = (
        db.query(Source)
        .filter(Source.investigation_id == investigation_id)
        .all()
    )

    events = extract_events(sources)

    clusters = cluster_events(events)

    response_clusters = []

    for cluster in clusters:

        cluster_events_data = []

        for event_index in cluster.event_indices:

            event = events[event_index]

            cluster_events_data.append({
                "event_index": event_index,
                "title": event.title,
                "event_date": (
                    event.event_date.isoformat()
                    if event.event_date
                    else None
                ),
                "entities": event.entities,
                "measurements": event.measurements,
                "years": event.years,
                "event_markers": event.event_markers,
                "source_id": event.source_id,
            })

        response_clusters.append({
            "cluster_id": cluster.cluster_id,
            "event_count": len(cluster.event_indices),
            "events": cluster_events_data,
        })

    return {
        "event_count": len(events),
        "cluster_count": len(clusters),
        "clusters": response_clusters,
    }

@router.post("/{investigation_id}/trends")
def fetch_investigation_trends(
    investigation_id: int,
    db: Session = Depends(get_db),
):
    investigation = (
        db.query(Investigation)
        .filter(Investigation.id == investigation_id)
        .first()
    )

    if investigation is None:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found",
        )

    analysis = analyze_claim(investigation.claim)
    topic = analysis.trends_topic

    db.query(TrendSignal).filter(
        TrendSignal.investigation_id == investigation_id
    ).delete(
        synchronize_session=False
    )
    db.commit()

    trends_data = get_trends(query=topic)
    timeline_data = trends_data.get("interest_over_time", {}).get("timeline_data", [])

    trend_signal = TrendSignal(
        investigation_id=investigation.id,
        query=topic,
        timeline=json.dumps(timeline_data),
    )
    db.add(trend_signal)
    db.commit()
    db.refresh(trend_signal)

    return {
        "query": topic,
        "timeline_points": len(timeline_data)
    }

@router.get("/{investigation_id}/verdict")
def get_investigation_verdict(
    investigation_id: int,
    db: Session = Depends(get_db),
):
    investigation = (
        db.query(Investigation)
        .filter(Investigation.id == investigation_id)
        .first()
    )

    if investigation is None:
        raise HTTPException(
            status_code=404,
            detail="Investigation not found",
        )

    sources = db.query(Source).filter(Source.investigation_id == investigation_id).all()
    events = extract_events(sources)
    trends = db.query(TrendSignal).filter(TrendSignal.investigation_id == investigation_id).all()

    verdict_data = generate_verdict(investigation, events, trends, sources)
    
    # Attach a simplified list of sources as proof
    verdict_data["evidence"] = [
        {
            "title": s.title,
            "url": s.url,
            "publisher": s.publisher,
            "published_at": s.published_at.isoformat() if s.published_at else None
        }
        for s in sources[:10] # send top 10 as proof
    ]
    
    return verdict_data