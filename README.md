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

If the Trends data shows a massive spike 3 years ago, and today'`s articles use near-identical language without citing any new triggering event, RETRACE flags it as **RECYCLED**.

---

## 🎯 Verdict Types

RETRACE produces one of **6 possible verdicts**:

| Verdict | Meaning |
|---|---|
| 🔴 **RECYCLED** | Old topic currently re-spiking — classic viral reshare |
| 🟠 **CONTESTED** | Multiple sources tell materially different stories |
| 🟡 **OLD TOPIC + NEW EVENT** | Historical topic with a genuinely new development |
| 🟢 **BREAKING** | New, unprecedented spike — likely a real, fresh event |
| 🔵 **DEVELOPING** | Recent event actively evolving — details still emerging |
| ⚪ **NEEDS REVIEW** | Low signal across all channels — requires manual check |

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
│  GET  /investigations/{id}/trends    ← 5-yr Trends   │
│  GET  /investigations/{id}/verdict   ← Final result  │
└───────────┬──────────────────────────────────────────┘
            │
   ┌────────┴────────────────────────────────────┐
   │              Services Layer                 │
   │                                             │
   │  investigation.py  →  Claim parsing &       │
   │                        search plan builder  │
   │                                             │
   │  evidence.py       →  Evidence collection   │
   │                        (multi-engine)       │
   │                                             │
   │  events.py         →  Event & entity        │
   │                        extraction           │
   │                                             │
   │  trends.py         →  5-year Trends fetch   │
   │                                             │
   │  what_changed.py   →  Narrative drift       │
   │                        detection            │
   │                                             │
   │  verdict.py        →  Spike analysis +      │
   │                        final verdict logic  │
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

### Step 1 — Claim Analysis
The claim is parsed by `investigation.py` to extract:
- **Claim type** (`research`, `policy`, `event`, `general`)
- **Named entities** (people, organisations, places)
- **Keywords** (stopword-filtered)

### Step 2 — Search Plan
A multi-engine search plan is built. For a `research`-type claim this includes:

```
google_news    → current_news
google         → exact_claim
google         → historical_search   (before:YEAR-01-01)
google         → historical_context  (topic + previous year)
google_news    → new_event_check
google_scholar → scholar_research
google         → patent_research     (tbm=pts)
```

### Step 3 — Evidence Collection
`evidence.py` executes every search, parses the results into a unified schema, deduplicates by URL, and stores up to 65+ sources in the database.

### Step 4 — Event Extraction
`events.py` scans every source title for:
- **Named entities** — proper noun sequences
- **Event markers** — 15 domain-agnostic pattern groups:
  - `study_claim`, `health_alert`, `policy_change`, `economic_signal`
  - `reshared_old`, `debunked`, `once_in_a_century`, `disaster`, etc.

### Step 5 — Trends Analysis *(the secret weapon)*
`trends.py` fetches a **5-year weekly** Trends timeline (~262 data points) for the claim'`s keywords globally.

`verdict.py` then splits this into two windows:
- **Historical window** — everything before the last 8 weeks
- **Current window** — the last 8 weeks (~2 months)

A spike is triggered when:
- `max_value >= 20` (out of 100) in that window, **OR**
- Current mean >= 1.5x the historical mean (relative surge detection)

### Step 6 — Narrative Drift (Contested Detection)
`what_changed.py` compares the earliest and latest events in the primary cluster. If marker categories shift (e.g. a `study_claim` becomes a `debunked` across sources), it is flagged as a contested narrative.

### Step 7 — Academic / Patent Layer
For research-type claims, `verdict.py` inspects the publication dates of all academic sources. If the most recent paper found is **older than 5 years**, an Outdated Research warning is added regardless of the Trends signal.

### Step 8 — Verdict + Confidence
The final verdict is chosen by a decision tree:

```
                        Historical spike?
                       /                \
                     YES                NO
                      │                  │
              Contested?           Contested?
             /          \         /          \
           YES           NO     YES           NO
            │             │      │             │
        CONTESTED    Developing? CONTESTED  Developing?
                     /       \              /       \
                   YES        NO          YES        NO
                    │          │           │          │
             OLD TOPIC +  Current?     DEVELOPING  Current?
             NEW EVENT   /       \               /       \
                        YES       NO           YES        NO
                         │         │            │          │
                      RECYCLED  NEEDS        BREAKING   NEEDS
                                REVIEW                  REVIEW
```

Confidence is dynamically calculated from:
- Spike magnitude (historical + current max)
- Evidence volume (number of sources)
- Whether the narrative is contested (lowers confidence)
- Presence of recent academic corroboration

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
│   │   │   ├── investigation.py           # Claim parsing & search plan
│   │   │   ├── evidence.py                # Multi-engine evidence collector
│   │   │   ├── events.py                  # Entity & event marker extraction
│   │   │   ├── trends.py                  # Google Trends (5-year) fetcher
│   │   │   ├── what_changed.py            # Narrative drift detection
│   │   │   ├── verdict.py                 # Spike analysis & verdict logic
│   │   │   ├── search.py                  # SerpAPI wrapper
│   │   │   ├── cache.py                   # Disk-based API response cache
│   │   │   ├── event_clustering.py        # Groups similar events
│   │   │   ├── event_comparison.py        # Compares two events
│   │   │   ├── event_matcher.py           # Classifies event relationships
│   │   │   ├── event_relationships.py     # Builds event relationship graph
│   │   │   ├── anchor_frequency.py        # TF-IDF-style anchor scoring
│   │   │   └── event_identity.py          # Event deduplication logic
│   │   └── main.py                        # FastAPI app entry point
│   ├── .env                               # SERPAPI_KEY (not committed)
│   ├── requirements.txt
│   └── retrace.db                         # SQLite database (not committed)
├── data/
│   ├── cache/                             # Cached SerpAPI responses (JSON)
│   └── fixtures/                          # Test fixtures
├── frontend/
│   └── index.html                         # Single-file frontend
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

---

## 🧪 Example Claims to Test

| Claim | Expected Verdict |
|---|---|
| `Dolphins return to Venice canals` | **RECYCLED** (2020 viral hoax) |
| `New study reveals COVID vaccines cause heart attacks` | **CONTESTED** |
| `TikTok ban officially passed by Congress` | **RECYCLED** (recurring topic) |
| `Newly formed asteroid crater found in Greenland` | **NEEDS REVIEW** + Outdated Research |
| `Federal Reserve announces emergency rate cut` | **RECYCLED** or **BREAKING** |

---

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
| `POST` | `/investigations/{id}/collect` | Collect and store evidence |
| `POST` | `/investigations/{id}/extract-events` | Extract events from sources |
| `GET` | `/investigations/{id}/trends` | Fetch 5-year Trends data |
| `GET` | `/investigations/{id}/verdict` | Generate the final verdict |

Full interactive docs are available at `http://localhost:8000/docs` (Swagger UI).

---

## 💡 What Makes This Different

Most fact-checkers search for **existing debunks**. RETRACE finds misinformation that has not been debunked yet by looking at **patterns**:

1. **The Trend History Signal** — Nobody expects search history data to be used for fact-checking. A story that spiked massively in 2020 and is now going viral again with the same language is almost certainly recycled.

2. **Narrative Drift Detection** — Even if a topic is genuinely old, the *way* it is being framed may have changed. RETRACE compares event markers across the oldest and newest articles to catch this.

3. **Academic Freshness Check** — If a "study" claim cites research that is over 5 years old, it gets flagged regardless of whether the topic is trending.

4. **No LLMs required** — The entire pipeline runs on regex, search APIs, and statistical analysis. Fast, cheap, and explainable.

---

## 📄 License

MIT — see [LICENSE](LICENSE) for details.
