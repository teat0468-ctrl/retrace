# 🕵️ RETRACE — Recycled News Detector

> **The mind-bender signal: using Google Trends history as a fact-checking weapon.**

RETRACE is an automated claim-investigation engine that detects fake, misleading, and recycled news by combining live search results with 5-year Google Trends history. The core insight: *fake stories are often not new — they are old stories re-shared as if they just happened.* By overlaying historical search-interest curves against current reporting, RETRACE can flag "recycled, not breaking" content that no traditional fact-checker would catch.

---

## 🧠 The Core Idea

```
A viral headline appears.
      │
      ▼
Is this actually new?
      │
      ├─ Pull Google News → What are people writing TODAY?
      │
      ├─ Pull Google Trends (5 years) → Did this topic spike BEFORE?
      │
      ├─ Pull Google Scholar + Patents → Is the "science" old or debunked?
      │
      └─ Compare narratives → Did the story CHANGE between then and now?
```

If the Trends data shows a massive spike 3 years ago, and today's articles use near-identical language without citing any new triggering event, RETRACE flags it as **RECYCLED**.

---

## 🎯 Verdict Types

RETRACE produces one of **6 possible verdicts**:

| Verdict | Meaning |
|---|---|
| 🔴 **BREAKING** | New event with no Trends history and active recent news coverage |
| 🔵 **DEVELOPING** | Recent event actively evolving — new entities and details still emerging |
| 🟣 **CONTESTED** | Multiple sources give materially different or conflicting accounts |
| 🟡 **OLD TOPIC + NEW EVENT** | Historical topic with a genuinely new development or actor |
| ♻️ **RECYCLED** | Old topic currently re-spiking — classic viral reshare with no new event |
| ⚪ **NEEDS REVIEW** | Low signal across all channels — requires manual verification |

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────┐
│                    Frontend (HTML)                   │
│   Single-page app · Dark UI · Chart.js Trends graph  │
└──────────────────────┬───────────────────────────────┘
                       │  HTTP
┌──────────────────────▼───────────────────────────────┐
│               FastAPI Backend (Python)               │
│                                                      │
│  POST /investigations          ← Create new claim    │
│  POST /investigations/{id}/collect   ← Gather data   │
│  POST /investigations/{id}/extract-events            │
│  POST /investigations/{id}/trends    ← 5-yr Trends   │
│  GET  /investigations/{id}/verdict   ← Final result  │
└───────────┬──────────────────────────────────────────┘
            │
   ┌────────┴────────────────────────────────────┐
   │              Services Layer                 │
   │                                             │
   │  investigation.py  →  Claim parsing &       │
   │                        dual-topic builder   │
   │                                             │
   │  evidence.py       →  Evidence collection   │
   │                        (multi-engine) +     │
   │                        domain blocklist     │
   │                                             │
   │  events.py         →  Event & entity        │
   │                        extraction           │
   │                                             │
   │  trends.py         →  5-year Trends fetch   │
   │                                             │
   │  what_changed.py   →  Narrative drift &     │
   │                        entity drift detect  │
   │                                             │
   │  verdict.py        →  Spike analysis +      │
   │                        recency check +      │
   │                        final verdict logic  │
   │                                             │
   │  search.py         →  SerpAPI wrapper       │
   │                        (with retry logic)   │
   │                                             │
   │  cache.py          →  Disk-based API cache  │
   └────────┬────────────────────────────────────┘
            │
   ┌────────▼────────────────────────────────────┐
   │         External APIs (via SerpAPI)         │
   │                                             │
   │  • Google News          (current coverage)  │
   │  • Google Search        (historical search) │
   │  • Google Scholar       (academic papers)   │
   │  • Google Patents       (patent filings)    │
   │  • Google Trends        (5-year interest)   │
   └─────────────────────────────────────────────┘
            │
   ┌────────▼────────────────────────────────────┐
   │           SQLite Database (retrace.db)      │
   │                                             │
   │  Investigation · Source · Event · TrendSignal│
   └─────────────────────────────────────────────┘
```

---

## 🔍 How the Pipeline Works

### Step 1 — Claim Analysis & Dual-Topic Extraction

The claim is parsed by `investigation.py` to extract:
- **Claim type** (`research`, `policy`, `event`, `general`)
- **Named entities** (people, organisations, places) via proper-noun regex
- **Keywords** (stopword-filtered)

Two optimised search topics are then derived:

| Topic | Purpose | Strategy |
|---|---|---|
| `news_topic` | Google News searches | Entity names + domain nouns — finds the *specific current event* |
| `trends_topic` | Google Trends + historical searches | Domain nouns first, org/brand names second — anchors on the *underlying topic*, not the current actor |

**Why two topics?** If you search Google Trends for `"RBI Governor Sanjay Malhotra"`, you get zero history because he is a new figure. But if you search for `"paper currency India"`, you see the correct 5-year footprint of the underlying topic. The separation prevents new actors from masking the historical signal.

Action verbs (`"announced"`, `"launched"`, `"approved"`) and generic nouns (`"product"`, `"notes"`, `"banks"`) are stripped from `trends_topic` because they return no useful Trends data.

### Step 2 — Search Plan

A multi-engine search plan is built from the two topics:

```
google_news    → current_news        (news_topic)
google         → exact_claim         (first 60 chars of raw claim)
google         → historical_search   (trends_topic + before:YEAR-01-01)
google         → historical_context  (trends_topic + previous year)
google_news    → new_event_check     (news_topic + "new update")
google_scholar → scholar_research    (trends_topic, research claims only)
google         → patent_research     (trends_topic + tbm=pts, research only)
```

### Step 3 — Evidence Collection

`evidence.py` executes every search via the SerpAPI wrapper:
- Results are parsed into a unified schema (title, URL, publisher, published_at, source_type)
- A **domain blocklist** discards junk results: YouTube, TikTok, Pinterest, Amazon, Flipkart, Spotify, and app stores
- All results are deduplicated by URL
- Up to 65+ sources are stored in the SQLite database per investigation

**Retry logic:** If SerpAPI times out or returns a network error, `search.py` automatically retries up to **3 times** with a 1-second delay between attempts. If all attempts fail, the search is skipped gracefully rather than crashing the investigation.

### Step 4 — Event Extraction

`events.py` scans every stored source title and accepts any headline with **3 or more meaningful words**. This ensures passive-voice and noun-heavy headlines are included for entity comparison.

Each accepted headline is parsed for:
- **Named entities** — proper noun sequences (up to 4-word multi-token names)
- **Event markers** — 14 domain-agnostic pattern groups:

| Marker | Triggers on |
|---|---|
| `conflict_signal` | "denies", "blames", "rejects", "disputes", "contradicts", "different accounts" |
| `reshared_old` | "old video", "from 2021", "originally", "going viral again" |
| `debunked` | "fact-checked", "misleading", "disproved", "refuted" |
| `policy_change` | "banned", "approved", "law", "regulation", "mandate" |
| `health_alert` | "cancer", "pandemic", "outbreak", "vaccine", "warning" |
| `economic_signal` | "recession", "inflation", "stock market crash", "bankruptcy" |
| `study_claim` | "study", "researchers", "scientists", "suggests", "linked to" |
| `newly_discovered` | "newly discovered", "first ever", "unprecedented" |
| `impact_event` | "impact", "slammed", "exploded", "blasted" |
| `once_in_a_century` | "once in a century", "once in a lifetime" |
| `detection_delay` | "undetected", "hidden", "years later", "overlooked" |
| `outdated_research` | "old study", "outdated", "overturned" |
| `newly_formed` | "newly formed", "recently formed" |

### Step 5 — Trends Analysis *(the secret weapon)*

`trends.py` fetches a **5-year weekly** Trends timeline (~262 data points) using the `trends_topic` query globally.

`verdict.py` then splits this into two windows:
- **Historical window** — everything before the last 8 weeks
- **Current window** — the last 8 weeks (~2 months)

A spike is triggered when:
- `max_value >= 20` (out of 100) in that window, **OR**
- Current mean >= 1.5× the historical mean (relative surge detection)

### Step 6 — Narrative Drift Detection

`what_changed.py` compares the earliest and latest events in the primary cluster across 6 dimensions:

| Signal | Description | Severity |
|---|---|---|
| New entity introduced | Later articles mention new people or organisations | medium → DEVELOPING |
| Entity dropped | Earlier articles mentioned an entity that later vanishes | low |
| New event marker | A new category label appears in later headlines | medium |
| Marker removed | A category label disappears in later headlines | low |
| Measurement changed | Reported figures differ between oldest and newest articles | medium |
| Claim flip pair | A story shifts from `study_claim` → `debunked` or similar | high → CONTESTED |

### Step 7 — Conflict Signal Detection

If any event in the primary cluster carries the `conflict_signal` marker (words like "denies", "blames", "rejects", "disputes"), the verdict is immediately promoted to **CONTESTED**, regardless of the Trends data. This catches disputes and denials in both new and historical topics.

### Step 8 — Academic / Patent Layer

For research-type claims, `verdict.py` inspects the publication dates of all academic sources. If the most recent paper found is **older than 5 years**, an Outdated Research warning is added to the reasons regardless of the Trends signal.

### Step 9 — Verdict + Confidence

The final verdict is chosen by this decision tree:

```
                     Has any Trends data?
                    /                    \
                  NO                     YES
                   │                       │
          Has recent news?          Historical spike?
         (≥2 sources ≤7d)          /               \
          /           \          YES                NO
        YES            NO         │                  │
         │              │    Conflict?           Conflict?
      BREAKING      NEEDS    /       \           /       \
                    REVIEW YES       NO        YES        NO
                            │         │         │          │
                        CONTESTED  Developing? CONTESTED  Developing?
                                   /       \             /       \
                                 YES        NO         YES        NO
                                  │          │          │          │
                           OLD TOPIC +   Current?   DEVELOPING  Current?
                           NEW EVENT    /       \              /       \
                                       YES       NO           YES       NO
                                        │         │            │         │
                                     RECYCLED  NEEDS       BREAKING    NEEDS
                                              REVIEW                   REVIEW
```

**Key insight:** If Google Trends returns **no data at all** (brand-new topic like a just-launched product), and there are ≥2 recent news sources published within the last 7 days, the claim is classified as **BREAKING** — because zero history + active current coverage is the hallmark of a genuinely new event.

Confidence is dynamically calculated (0.30–0.97) from:
- Spike magnitude (historical + current max out of 100)
- Evidence volume (number of sources collected, up to +0.10)
- Whether the narrative is contested (−0.12)
- Whether the story is developing (−0.05)
- Presence of recent academic corroboration (+0.05)

---

## 📁 Project Structure

```
retrace/
├── backend/
│   ├── app/
│   │   ├── api/routes/investigations.py   # All API endpoints
│   │   ├── core/config.py                 # SERPAPI_KEY, settings
│   │   ├── db/
│   │   │   ├── database.py                # SQLAlchemy session
│   │   │   └── tables.py                  # DB table models
│   │   ├── services/
│   │   │   ├── investigation.py           # Claim parsing, dual-topic extraction, search plan
│   │   │   ├── evidence.py                # Multi-engine evidence collector + domain blocklist
│   │   │   ├── events.py                  # Entity & event marker extraction
│   │   │   ├── trends.py                  # Google Trends (5-year) fetcher
│   │   │   ├── what_changed.py            # Narrative drift & entity drift detection
│   │   │   ├── verdict.py                 # Spike analysis, recency check & verdict logic
│   │   │   ├── search.py                  # SerpAPI wrapper with retry logic (3 attempts)
│   │   │   ├── cache.py                   # Disk-based API response cache
│   │   │   ├── event_clustering.py        # Groups similar events into clusters
│   │   │   ├── event_comparison.py        # Compares two events structurally
│   │   │   ├── event_matcher.py           # Classifies event relationships (SAME/VARIANT/DIFFERENT)
│   │   │   ├── event_relationships.py     # Builds the full event relationship graph
│   │   │   ├── anchor_frequency.py        # TF-IDF-style anchor scoring for entity matching
│   │   │   └── event_identity.py          # Event deduplication logic
│   │   └── main.py                        # FastAPI app entry point
│   ├── .env                               # SERPAPI_KEY (not committed)
│   ├── requirements.txt
│   └── retrace.db                         # SQLite database (not committed)
├── data/
│   ├── cache/                             # Cached SerpAPI responses (JSON)
│   └── fixtures/                          # Test fixtures
├── frontend/
│   └── index.html                         # Single-file frontend (no build step)
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- A [SerpAPI](https://serpapi.com) API key (free tier works)

### 1. Clone the repo
```bash
git clone https://github.com/your-username/retrace.git
cd retrace
```

### 2. Set up the backend
```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# or: source venv/bin/activate  (macOS/Linux)
pip install -r requirements.txt
```

### 3. Configure your API key
Create a `.env` file inside the `backend/` folder:
```
SERPAPI_KEY=your_serpapi_key_here
```

### 4. Start the server
```bash
uvicorn app.main:app --reload
```

### 5. Open the frontend
Open `frontend/index.html` in your browser directly — no build step needed.
The UI talks to `http://localhost:8000` automatically.



## 🔑 Environment Variables

| Variable | Description |
|---|---|
| `SERPAPI_KEY` | Your SerpAPI key (required) |

---

## 🛡️ API Reference

All endpoints are under `/investigations`.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/investigations` | Create a new investigation from a claim |
| `GET` | `/investigations/{id}` | Get investigation status |
| `POST` | `/investigations/{id}/collect` | Collect and store evidence from SerpAPI |
| `POST` | `/investigations/{id}/extract-events` | Extract events and markers from stored sources |
| `POST` | `/investigations/{id}/trends` | Fetch 5-year Google Trends data |
| `GET` | `/investigations/{id}/verdict` | Generate the final verdict |

Full interactive docs are available at `http://localhost:8000/docs` (Swagger UI).

---

## 💡 What Makes This Different

Most fact-checkers search for **existing debunks**. RETRACE finds misinformation that has not been debunked yet by looking at **structural patterns**:

1. **Dual-Topic Search Strategy** — One optimised query finds the *current specific event* (news_topic, entity-heavy), while a separate query finds the *historical topic footprint* (trends_topic, noun-heavy, actor-agnostic). This prevents a new actor (e.g. a newly appointed governor) from masking the historical search interest of the underlying topic.

2. **The Trend History Signal** — A story that spiked massively in 2019 and is now going viral again with the same language is almost certainly recycled. Nobody expects search history to be used for fact-checking.

3. **Recency-Based BREAKING Detection** — If Google Trends has *no data at all* for a topic, but ≥2 news sources were published in the last 7 days, RETRACE correctly classifies it as BREAKING. Zero history + active news = genuinely new event.

4. **Conflict Signal Detection** — Words like "denies", "blames", "rejects", "disputes" in any collected headline immediately force a CONTESTED verdict. This catches inter-party disputes and claim denials that no simple keyword search would surface.

5. **Entity Drift Detection** — RETRACE compares the named entities in the oldest vs. newest articles on the same cluster. New people, organisations, or countries appearing in the latest reporting are a strong signal that a story is DEVELOPING.

6. **Academic Freshness Check** — If a "study" claim cites research that is over 5 years old, it gets flagged regardless of whether the topic is trending.

7. **No LLMs required** — The entire pipeline runs on regex, search APIs, and statistical analysis. Fast, cheap, and fully explainable.

---

## 📄 License

MIT — see [LICENSE](LICENSE) for details.

