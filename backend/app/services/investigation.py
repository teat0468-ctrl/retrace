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
    news_topic: str
    trends_topic: str


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


def extract_trends_topic(entities: list[str], keywords: list[str]) -> str:
    """
    Broad topic for Google Trends — uses the core NOUN content of the claim.
    Strips action verbs ('announced', 'replace', 'approved') since they produce
    zero Trends data. Domain nouns come FIRST so the historical topic
    anchors the search rather than a new specific actor.
    """
    VERB_NOISE = {
        'announced', 'announce', 'replaced', 'replace', 'approved', 'approve',
        'introduced', 'introduce', 'launched', 'launch', 'dismissed', 'dismiss',
        'escalating', 'escalate', 'appointed', 'appoint', 'dispute', 'disputing',
        'clashing', 'clash', 'newly', 'officially', 'groundbreaking', 'massive',
        'just', 'will', 'start', 'getting', 'really', 'claim', 'claims',
        'new', 'actually', 'officially', 'increasing', 'starting', 'also',
        'governor', 'minister', 'president', 'chairman', 'secretary',
        # Generic nouns that pollute Trends searches
        'product', 'products', 'service', 'services', 'issue', 'issues',
        'leadership', 'governance', 'management', 'company', 'companies',
        'sector', 'banks', 'notes', 'teams', 'members', 'board', 'legal',
        'simultaneously', 'launching', 'duo', 'trio', 'decision',
    }

    # Entity words to deduplicate
    entity_words = set()
    for e in entities:
        for w in e.lower().split():
            entity_words.add(w)

    # Domain nouns: keywords NOT in entity words and NOT verbs
    # These are the most searchable content words (e.g. "currency", "merger", "polymer")
    noun_kws = [
        kw for kw in keywords
        if kw not in VERB_NOISE and kw not in entity_words and len(kw) > 3
    ]

    # Entity brand/org tokens as supplementary (e.g. "Apple", "Tata", "RBI")
    org_tokens = []
    for e in entities[:2]:
        e_clean = re.sub(r'^(The|A|An)\s+', '', e, flags=re.IGNORECASE)
        count = 0
        for word in e_clean.split():
            if word.lower() not in VERB_NOISE and len(word) >= 3:
                org_tokens.append(word)
                count += 1
                if count >= 2:  # Take up to 2 words per entity (e.g. "Tata Trusts", "Apple Vision")
                    break

    # Domain nouns first, then org tokens
    combined = []
    seen = set()
    for tok in noun_kws[:3] + org_tokens:
        if tok.lower() not in seen:
            seen.add(tok.lower())
            combined.append(tok)

    return ' '.join(combined[:5])[:80]



def extract_news_topic(entities: list[str], keywords: list[str]) -> str:
    """
    Specific topic for Google News — entities + domain nouns.
    Includes WHO (entity names) so News finds this exact event.
    """
    VERB_NOISE = {
        'announced', 'announce', 'replaced', 'replace', 'approved', 'approve',
        'introduced', 'introduce', 'launched', 'launch', 'dismissed', 'dismiss',
        'escalating', 'escalate', 'appointed', 'appoint', 'dispute', 'disputing',
        'just', 'will', 'start', 'getting', 'really', 'claim', 'claims', 'new',
        'actually', 'officially', 'massive', 'groundbreaking', 'huge'
    }
    entity_words = set()
    for e in entities:
        for w in e.lower().split():
            entity_words.add(w)

    filtered_kws = [kw for kw in keywords if kw not in entity_words and kw not in VERB_NOISE]

    core_parts = []
    for e in entities[:2]:
        e_clean = re.sub(r'^(The|A|An)\s+', '', e, flags=re.IGNORECASE)
        core_parts.append(e_clean)

    core_parts.extend(filtered_kws[:3])
    return ' '.join(core_parts)[:100]


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
    entities = extract_entities(normalized)
    keywords = extract_keywords(normalized)

    return ClaimAnalysis(
        original_claim=claim,
        normalized_claim=normalized,
        claim_type=detect_claim_type(normalized),
        entities=entities,
        keywords=keywords,
        news_topic=extract_news_topic(entities, keywords),
        trends_topic=extract_trends_topic(entities, keywords)
    )


def build_search_plan(claim: str) -> list[SearchQuery]:
    analysis = analyze_claim(claim)

    plan = [
        SearchQuery(
            query=analysis.news_topic,
            engine="google_news",
            purpose="current_news",
        ),
        SearchQuery(
            query=f'"{analysis.normalized_claim[:60]}"',
            engine="google",
            purpose="exact_claim",
        ),
        SearchQuery(
            query=f"{analysis.trends_topic} before:{datetime.now().year}-01-01",
            engine="google",
            purpose="historical_search",
        ),
        SearchQuery(
            query=f"{analysis.trends_topic} {datetime.now().year - 1}",
            engine="google",
            purpose="historical_context",
        ),
        SearchQuery(
            query=f"{analysis.news_topic} new update",
            engine="google_news",
            purpose="new_event_check",
        ),
    ]

    if analysis.claim_type == "research":
        plan.append(
            SearchQuery(
                query=analysis.trends_topic,
                engine="google_scholar",
                purpose="scholar_research",
            )
        )
        plan.append(
            SearchQuery(
                query=analysis.trends_topic,
                engine="google_patents",
                purpose="patent_research",
            )
        )

    return plan

