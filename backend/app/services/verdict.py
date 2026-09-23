import json
from datetime import datetime
from app.services.event_clustering import cluster_events
from app.services.what_changed import compare_event_details


# ------------------------------------------------------------------
# Trends spike analysis
# ------------------------------------------------------------------

def analyze_trends_spikes(timeline_data: list[dict]) -> dict:
    """
    Splits a 5-year weekly Trends timeline (≈260 points) into two windows:

    - current   : last 8 data points (~2 months)
    - historical: everything before that

    A spike is flagged when:
      • Absolute: the window's max value >= 20 (out of 100)
      • Relative (current only): current mean > 1.5× historical mean,
        so a sudden re-ignition registers even if absolute values are
        moderate.

    The 'recycled' signal fires when historical_spike=True but
    current_spike=False (old topic not re-heating now), or when both
    are True (old topic being actively recirculated).
    """
    if not timeline_data or len(timeline_data) < 4:
        return {
            "historical_spike": False,
            "current_spike": False,
            "historical_max": 0,
            "current_max": 0,
        }

    # For 5-year weekly data (≈260 pts) use 8-week current window.
    # For shorter series (12-month monthly, ~12 pts) use 2-point window.
    n = len(timeline_data)
    current_window = 8 if n >= 30 else 2

    current_data    = timeline_data[-current_window:]
    historical_data = timeline_data[:-current_window]

    def get_val(item):
        if "values" in item and item["values"]:
            return int(item["values"][0].get("extracted_value", 0))
        return int(item.get("value", 0))

    current_vals    = [get_val(t) for t in current_data]
    historical_vals = [get_val(t) for t in historical_data]

    current_max    = max(current_vals)    if current_vals    else 0
    historical_max = max(historical_vals) if historical_vals else 0

    # Mean of non-zero historical values (avoid zero-inflation)
    nonzero_hist = [v for v in historical_vals if v > 0]
    hist_mean    = (sum(nonzero_hist) / len(nonzero_hist)) if nonzero_hist else 0
    curr_mean    = (sum(current_vals) / len(current_vals))  if current_vals  else 0

    # --- Spike thresholds ---
    # Absolute: any peak >= 20/100 is meaningful on a global 5-year scale
    SPIKE_THRESHOLD = 20

    historical_spike = historical_max >= SPIKE_THRESHOLD

    # Current spike: absolute OR relative surge (1.5× historical mean)
    current_spike = (
        current_max >= SPIKE_THRESHOLD
        or (hist_mean > 0 and curr_mean >= hist_mean * 1.5)
    )

    return {
        "historical_spike": historical_spike,
        "current_spike":    current_spike,
        "historical_max":   historical_max,
        "current_max":      current_max,
        "hist_mean":        round(hist_mean, 1),
        "curr_mean":        round(curr_mean, 1),
    }


# ------------------------------------------------------------------
# Scholar / academic source analysis
# ------------------------------------------------------------------

def analyze_scholar_sources(evidence_sources) -> dict:
    """
    Checks academic sources for age.  If the claim cites research but all
    papers found are more than 5 years old AND no recent paper exists,
    we flag it as potentially citing outdated science.
    """
    current_year = datetime.now().year
    academic = [
        s for s in evidence_sources
        if getattr(s, "source_type", None) == "academic"
    ]

    if not academic:
        return {"has_academic": False, "outdated": False, "oldest_year": None}

    years = []
    for s in academic:
        pub = getattr(s, "published_at", None)
        if pub and hasattr(pub, "year"):
            years.append(pub.year)

    if not years:
        return {"has_academic": True, "outdated": False, "oldest_year": None}

    most_recent = max(years)
    oldest = min(years)
    outdated = most_recent < (current_year - 5)

    return {
        "has_academic": True,
        "outdated": outdated,
        "most_recent_year": most_recent,
        "oldest_year": oldest,
    }


# ------------------------------------------------------------------
# Dynamic confidence scoring
# ------------------------------------------------------------------

def _compute_confidence(
    spike_analysis: dict,
    is_contested: bool,
    is_developing: bool,
    scholar: dict,
    num_events: int,
    num_sources: int,
) -> float:
    """
    Produces a 0.0–1.0 confidence score based on:
    - Strength of the historical / current spike
    - Number of corroborating evidence sources
    - Event consensus (contested lowers confidence)
    """
    score = 0.50  # neutral start

    # Trends signal quality
    h_max = spike_analysis.get("historical_max", 0)
    c_max = spike_analysis.get("current_max", 0)

    # Strong spikes → higher confidence in the verdict
    score += min(h_max / 200, 0.15)   # up to +0.15 for historical
    score += min(c_max / 200, 0.15)   # up to +0.15 for current

    # Evidence volume
    score += min(num_sources / 40, 0.10)  # up to +0.10 for evidence breadth

    # Contested narratives reduce confidence
    if is_contested:
        score -= 0.12
    if is_developing:
        score -= 0.05

    # Scholar corroboration
    if scholar.get("has_academic"):
        score += 0.05

    return round(min(max(score, 0.30), 0.97), 2)


# ------------------------------------------------------------------
# Main verdict generator
# ------------------------------------------------------------------

def generate_verdict(investigation, events, trends, evidence_sources) -> dict:
    timeline_data = []
    if trends and trends[0].timeline:
        try:
            timeline_data = json.loads(trends[0].timeline)
        except json.JSONDecodeError:
            pass

    spike_analysis = analyze_trends_spikes(timeline_data)
    scholar = analyze_scholar_sources(evidence_sources)

    reasons = []
    changes_detected = []

    # --- Detect if we have recent news (within ~7 days) ---
    now = datetime.utcnow()
    recent_sources = []
    for s in evidence_sources:
        pub = getattr(s, 'published_at', None)
        if pub:
            age_days = (now - pub).days
            if age_days <= 7:
                recent_sources.append(s)
    has_recent_news = len(recent_sources) >= 2
    has_any_trends_data = len(timeline_data) >= 4

    # 1. Cluster events to find the main narrative
    clusters = cluster_events(events)

    is_contested = False
    is_developing = False

    if clusters:
        primary_cluster = clusters[0]
        
        # Check for inherent conflict in the cluster's events
        for idx in primary_cluster.event_indices:
            if "conflict_signal" in getattr(events[idx], "event_markers", []):
                is_contested = True
                msg = "Reporting indicates disputes, denials, or conflicting accounts."
                if msg not in changes_detected:
                    changes_detected.append(msg)
                break

        # Compare earliest and latest events in the primary cluster
        if len(primary_cluster.event_indices) >= 2:
            earliest_idx = primary_cluster.event_indices[-1]
            latest_idx = primary_cluster.event_indices[0]

            changes = compare_event_details(
                events[earliest_idx],
                events[latest_idx],
                earliest_idx,
                latest_idx,
            )

            for change in changes:
                if change.description not in changes_detected:
                    changes_detected.append(change.description)
                if change.severity == "high":
                    is_contested = True
                else:
                    is_developing = True

    # 2. Determine Verdict
    historical = spike_analysis["historical_spike"]
    current = spike_analysis["current_spike"]

    if not has_any_trends_data:
        # Google Trends returned nothing — brand-new topic or very niche query
        if is_contested:
            verdict = "CONTESTED"
            reasons.append(
                "This appears to be an emerging topic with conflicting accounts "
                "and no established Google Trends footprint."
            )
        elif has_recent_news:
            # Recent news but zero Trends history = genuinely new / BREAKING
            verdict = "BREAKING"
            reasons.append(
                "This appears to be a new event: Google Trends has no historical "
                "record for this topic, and recent news coverage is actively emerging."
            )
        else:
            verdict = "NEEDS REVIEW"
            reasons.append(
                "There is no Google Trends data and insufficient news coverage "
                "to classify this claim automatically."
            )
    elif historical:
        if is_contested:
            verdict = "CONTESTED"
            reasons.append(
                "While this is an old topic, contradictory accounts "
                "appear in the recent reporting — the narrative has shifted."
            )
        elif is_developing:
            verdict = "OLD TOPIC + NEW EVENT"
            reasons.append(
                "Historical interest exists, but new details or developments "
                "have emerged that go beyond the original story."
            )
        elif current:
            verdict = "RECYCLED"
            reasons.append(
                "Google Trends shows significant past interest (historical spike: "
                f"{spike_analysis['historical_max']}/100). "
                "Current reports mirror old claims with no new triggering event."
            )
        else:
            # Old topic, no current spike — could be developing quietly
            if is_developing:
                verdict = "OLD TOPIC + NEW EVENT"
                reasons.append(
                    "This topic has historical search interest and new developments "
                    "are now being reported."
                )
            else:
                verdict = "NEEDS REVIEW"
                reasons.append(
                    "This topic was popular in the past but is not currently "
                    "driving meaningful new search interest."
                )
    else:
        # No historical spike
        if is_contested:
            verdict = "CONTESTED"
            reasons.append(
                "This is a new or emerging topic, but multiple sources have "
                "materially different accounts of what happened."
            )
        elif is_developing:
            verdict = "DEVELOPING"
            reasons.append(
                "This is a recent event that is actively developing — "
                "new details are still emerging."
            )
        elif current:
            verdict = "BREAKING"
            reasons.append(
                "This is a new, unprecedented spike in search interest "
                f"(current: {spike_analysis['current_max']}/100) "
                "with a broadly unified narrative."
            )
        elif has_recent_news:
            verdict = "BREAKING"
            reasons.append(
                "This is a new event with active current news coverage "
                "and no established historical footprint on Google Trends."
            )
        else:
            verdict = "NEEDS REVIEW"
            reasons.append(
                "There is low overall search interest and no strong event "
                "consensus. Verify the claim manually."
            )

    # 3. Scholar / academic layer
    if scholar.get("has_academic"):
        if scholar.get("outdated"):
            most_recent = scholar.get("most_recent_year", "unknown")
            reasons.append(
                f"⚠️  Academic sources found for this claim, but the most "
                f"recent paper is from {most_recent} — the research cited "
                f"may be outdated or superseded."
            )
        else:
            most_recent = scholar.get("most_recent_year", "unknown")
            reasons.append(
                f"Recent academic literature ({most_recent}) supports "
                "or covers this topic."
            )

    # 4. Re-shared signal from markers
    if any(
        "reshared_old" in getattr(e, "event_markers", [])
        for e in events
    ):
        reasons.append(
            "🔁 Headlines in the evidence explicitly reference old videos, "
            "photos, or articles being recirculated."
        )

    # 5. Confidence
    confidence = _compute_confidence(
        spike_analysis=spike_analysis,
        is_contested=is_contested,
        is_developing=is_developing,
        scholar=scholar,
        num_events=len(events),
        num_sources=len(evidence_sources),
    )

    return {
        "verdict": verdict,
        "confidence": confidence,
        "reasons": reasons,
        "historical_spike": historical,
        "current_spike": current,
        "historical_max": spike_analysis["historical_max"],
        "current_max": spike_analysis["current_max"],
        "trends_timeline": timeline_data,
        "narrative_changes": changes_detected,
        "academic_signal": scholar,
    }
