from dataclasses import dataclass
import re
from datetime import datetime


@dataclass
class ClaimAnalysis:
    original_claim: str
    normalized_claim: str
    claim_type: str
    entities: list[str]
    keywords: list[str]


@dataclass
class SearchQuery:
    query: str
    engine: str
    purpose: str


STOP_WORDS = {
    "a", "about", "actually", "after", "all", "also", "an", "and", "any", "are", 
    "as", "at", "be", "because", "been", "before", "being", "between", "both", "but", 
    "by", "came", "can", "come", "could", "did", "different", "do", "does", "doing", 
    "down", "each", "few", "for", "from", "further", "had", "happen", "happened", 
    "has", "have", "having", "he", "her", "here", "hers", "herself", "him", "himself", 
    "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just", "me", 
    "more", "most", "my", "myself", "new", "no", "nor", "not", "now", "of", "off", 
    "on", "once", "only", "or", "other", "our", "ours", "ourselves", "out", "over", 
    "own", "said", "same", "says", "she", "should", "so", "some", "such", "than", 
    "that", "the", "their", "theirs", "them", "themselves", "then", "there", "these", 
    "they", "this", "those", "through", "to", "too", "under", "until", "up", "very", 
    "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom", 
    "why", "will", "with", "you", "your", "yours", "yourself", "yourselves", "according"
}


def normalize_claim(claim: str) -> str:
    claim = claim.strip()
    claim = re.sub(r"\s+", " ", claim)
    return claim


def extract_keywords(claim: str) -> list[str]:
    words = re.findall(r"[A-Za-z0-9]+", claim.lower())

    keywords = []

    for word in words:
        if len(word) < 3:
            continue

        if word in STOP_WORDS:
            continue

        if word not in keywords:
            keywords.append(word)

    return keywords[:10]


def extract_entities(claim: str) -> list[str]:
    entities = []

    # Basic proper-name detection.
    # This is intentionally simple for version 1.
    matches = re.findall(
        r"\b[A-Z][a-zA-Z0-9]*(?:\s+[A-Z][a-zA-Z0-9]*){0,3}",
        claim,
    )

    for match in matches:
        cleaned = match.strip()

        if cleaned.lower() not in STOP_WORDS:
            if cleaned not in entities:
                entities.append(cleaned)

    return entities[:8]


def detect_claim_type(claim: str) -> str:
    text = claim.lower()

    research_words = [
        "study",
        "research",
        "researchers",
        "scientists",
        "scientist",
        "found",
        "suggests",
        "suggest",
        "linked",
        "associated",
        "health",
        "risk",
    ]

    event_words = [
        "discovers",
        "discovered",
        "discover",
        "launches",
        "launched",
        "announces",
        "announced",
        "opens",
        "opened",
        "arrested",
        "dies",
        "killed",
        "wins",
        "won",
        "earthquake",
        "crash",
    ]

    policy_words = [
        "government",
        "law",
        "policy",
        "bill",
        "regulation",
        "minister",
        "court",
        "ban",
        "banned",
        "election",
    ]

    if any(word in text for word in research_words):
        return "research"

    if any(word in text for word in policy_words):
        return "policy"

    if any(word in text for word in event_words):
        return "event"

    return "general"


def analyze_claim(claim: str) -> ClaimAnalysis:
    normalized = normalize_claim(claim)

    return ClaimAnalysis(
        original_claim=claim,
        normalized_claim=normalized,
        claim_type=detect_claim_type(normalized),
        entities=extract_entities(normalized),
        keywords=extract_keywords(normalized),
    )


def build_search_plan(claim: str) -> list[SearchQuery]:
    analysis = analyze_claim(claim)

    topic = " ".join(analysis.keywords[:6])

    plan = [
        SearchQuery(
            query=analysis.normalized_claim,
            engine="google_news",
            purpose="current_news",
        ),
        SearchQuery(
            query=f'"{analysis.normalized_claim[:60]}"',
            engine="google",
            purpose="exact_claim",
        ),
        SearchQuery(
            query=f"{topic} before:{datetime.now().year}-01-01",
            engine="google",
            purpose="historical_search",
        ),
        SearchQuery(
            query=f"{topic} {datetime.now().year - 1}",
            engine="google",
            purpose="historical_context",
        ),
        SearchQuery(
            query=f"{topic} new update",
            engine="google_news",
            purpose="new_event_check",
        ),
    ]

    if analysis.claim_type == "research":
        plan.append(
            SearchQuery(
                query=topic,
                engine="google_scholar",
                purpose="scholar_research",
            )
        )
        plan.append(
            SearchQuery(
                query=topic,
                engine="google_patents",
                purpose="patent_research",
            )
        )

    return plan

