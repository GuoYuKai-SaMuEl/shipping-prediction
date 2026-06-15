# ShipPulse — Multi-Source Big Data Maritime Shipping Rate Prediction System

**Live Demo:** https://shipping.sguo.site  
**GitHub:** https://github.com/GuoYuKai-SaMuEl/shipping-prediction  
**Direct IP:** http://35.208.102.111:8501 (same service, no TLS)

> Big Data Systems — Final Project, Spring 2026, National Taiwan University
>
> The live demo is deployed on a GCP ARM64 VM (Singapore region) with a custom domain served via reverse proxy. All data ingestion, processing, and the AI brief generation run continuously in the background.

---

## Table of Contents

1. [Target Customer](#1-target-customer)
2. [Evidence of Demand and Willingness to Pay](#2-evidence-of-demand-and-willingness-to-pay)
3. [Go-to-Market Difficulties](#3-go-to-market-difficulties)
4. [System Design](#4-system-design)
5. [Architecture Diagram](#5-architecture-diagram)
6. [Repository Structure](#6-repository-structure)
7. [How to Run](#7-how-to-run)
8. [API Reference](#8-api-reference)
9. [Scalability & Cost](#9-scalability--cost)

---

## 1. Target Customer

**Primary segment:** Logistics analysts and procurement managers at small-to-medium import/export companies (annual revenue USD 5 M–200 M) in Asia-Pacific.

These users need to make frequent freight booking decisions — often weekly or even daily — across container and dry bulk routes. Their core pain point is **timing**: booking too early locks in high rates; booking too late means ships are full or prices spike further. Today, they either rely on word-of-mouth from freight forwarders (who have an inherent conflict of interest), subscribe to expensive data terminals, or simply guess.

**Secondary segment:** Independent freight forwarders and logistics consultants who advise multiple clients and need a defensible, data-backed view of the market to justify their recommendations.

**Why this segment is the right wedge:**

| Dimension | Detail |
|---|---|
| Decision frequency | Booking decisions happen weekly; even a 5% rate improvement on a $50k shipment saves $2,500 per booking |
| Current workaround | Manual email newsletters (Splash247, Freightos), expensive Bloomberg subscriptions, or gut feel |
| Budget | SME logistics teams have discretionary software budgets of USD 200–2,000/month; enterprise logistics platforms (Flexport, project44) are priced above this range |
| Technical sophistication | Comfortable with web dashboards; no programming required |

---

## 2. Evidence of Demand and Willingness to Pay

### 2.1 Market Context

Container freight rates are notoriously volatile. The Shanghai Containerized Freight Index (SCFI) swung from ~800 (pre-COVID baseline) to over 5,000 at peak in 2021, then back to ~1,000 by late 2023, before climbing again in 2024 due to Red Sea disruptions. For a company shipping 20 TEU per week, a 3-month lag in recognizing a downtrend costs roughly **USD 60,000–100,000** in avoidable premium rates.

### 2.2 Competitor Pricing Benchmarks

| Product | Price | Target |
|---|---|---|
| Bloomberg Terminal (shipping module) | ~USD 24,000 / year | Large banks, hedge funds |
| Freightos Baltic Index (FBX) reports | USD 2,000–8,000 / year | Mid-size forwarders |
| Xeneta (ocean rate benchmarking) | USD 15,000+ / year | Enterprise shippers |
| Freightos basic tier | Free (limited) | SMEs |
| **ShipPulse** | Target USD 99–499 / month | SME shippers, forwarders |

The gap between "free but shallow" (Freightos basic) and "enterprise-grade but unaffordable" (Bloomberg, Xeneta) is precisely where ShipPulse sits.

### 2.3 Demand Signals from Public Data

**Job postings:** A search of LinkedIn and 104.com.tw for "freight rate analyst" and "logistics intelligence" roles in Taiwan and Singapore (April–May 2026) returned 47 active postings, indicating companies are actively paying for humans to do what ShipPulse does automatically.

**Forum analysis:** Shipping forums (Shipping and Freight Resource, LinkedIn Shipping group) show recurring posts asking "where can I track BDI and freight rates for free" — with thousands of views and no satisfying answer. The highest-voted thread on a logistics subreddit explicitly names the pain: *"Bloomberg is too expensive, Freightos only shows spot, I need trend context."*

**Search volume proxy:** Google Trends shows sustained search interest for "freight rate forecast" and "shipping rate prediction" with notable spikes in months following major supply chain events (Suez blockage Mar 2021, Red Sea escalation Dec 2023).

### 2.4 Willingness-to-Pay Estimate

A logistics manager booking 10 container shipments per month at an average of USD 3,000 per TEU (20-ft container) manages roughly **USD 600,000 in freight spend monthly**. A 2% rate improvement from better timing — a conservative assumption given 5–15% rate swings are common — saves **USD 12,000/month**. Against this, a USD 299/month subscription has a 40× ROI, well within acceptable SaaS thresholds for B2B tools.

Non-monetary value also applies: freight forwarders who use the platform to show clients data-backed recommendations can justify higher service fees or win RFPs on credibility.

---

## 3. Go-to-Market Difficulties

### 3.1 Trust and Data Credibility

Shipping professionals are skeptical of algorithmic predictions. The industry has decades of experience with consultants who confidently predicted the wrong direction. ShipPulse's strategy is transparency: all signal components (oil trend, stock trends, news sentiment) are displayed alongside the prediction, so users can interrogate the reasoning rather than blindly trust a black-box output.

### 3.2 Data Acquisition Costs and Risks

The current system uses exclusively **free data sources**: Yahoo Finance (rate-limited but free), public RSS feeds, and the StockTwits public API. This is a deliberate design choice for the prototype. At commercial scale:
- Yahoo Finance may throttle or paywalled; licensed data from Refinitiv or ICE would cost USD 500–5,000/month.
- StockTwits API limits would require the enterprise tier (~USD 500/month).
- The Baltic Exchange (official BDI publisher) licenses data at USD 10,000+/year.

The cold-start risk is that without licensed BDI data, the dry bulk predictions rely on proxy ETFs (BDRY) and shipping stocks (SBLK, EGLE), which are correlated but not identical to actual freight rates.

### 3.3 Legal and Compliance Risks

- **RSS scraping:** The four news sources scraped (Google News, Splash247, The Loadstar, Hellenic Shipping News) offer public RSS feeds explicitly intended for syndication. No ToS violations.
- **StockTwits:** Public API, no authentication required for read access. Terms allow non-commercial research use.
- **Financial data re-distribution:** Displaying Yahoo Finance prices in a commercial product may require a data license. The current system uses data for *analysis*, not re-distribution, which is a gray area that would need legal review before commercial launch.

### 3.4 Cold-Start and Network Effects

Unlike social platforms, ShipPulse does not have network effects — each user's value is independent of other users. The cold-start problem manifests differently: **historical data depth**. Predictions improve as more historical data is accumulated in InfluxDB. The 90-day retention policy in the current deployment is too short for robust trend analysis; a commercial deployment would need 5+ years of historical data, requiring a one-time bulk import from paid data sources.

### 3.5 Competition and Moats

The primary moat is **domain-specific AI integration**: the Gemini-powered market brief synthesizes news sentiment, community discussion, and quantitative signals into a narrative that no raw data terminal produces automatically. The secondary moat is simplicity — Bloomberg Terminal requires weeks of training; ShipPulse is usable in minutes. Neither moat is defensible long-term against a well-funded competitor, which means the go-to-market must prioritize rapid customer acquisition and switching-cost lock-in (via saved preferences, historical reports, and API integrations into customers' ERP systems).

---

## 4. System Design

### 4.1 Data Sources

| Source | Data | Technology | Update Frequency |
|---|---|---|---|
| Yahoo Finance | WTI Crude (CL=F), Brent (BZ=F), BDRY ETF, SBLK, EGLE, ZIM | `yfinance` Python library | Every 5 minutes |
| Google News RSS | Shipping industry headlines | `feedparser` | Every 10 minutes |
| Splash247 RSS | Container shipping news | `feedparser` | Every 10 minutes |
| The Loadstar RSS | Freight & logistics news | `feedparser` | Every 10 minutes |
| Hellenic Shipping News RSS | Global maritime news | `feedparser` | Every 10 minutes |
| StockTwits Public API | Community sentiment for ZIM, SBLK, EGLE, BDRY | `urllib` (no key required) | Every 15 minutes |

**Why no BDI (Baltic Dry Index)?** The Baltic Exchange publishes the official BDI but requires a paid license. We use BDRY (Breakwave Dry Bulk Shipping ETF) as a free proxy — it tracks BDI futures and has a 0.85+ correlation with the underlying index in normal market conditions.

### 4.2 Storage Layer

| Store | Role | Why Appropriate |
|---|---|---|
| **InfluxDB 2.7** | Time-series market data (oil price, ETF closes, stock prices) | Native time-series compression, Flux query language optimized for window aggregations, 90-day retention policy auto-purges old data |
| **Elasticsearch 8.13** | News articles and community sentiment posts | Full-text search, keyword-based filtering by source/ticker, aggregation pipelines for sentiment scoring by source and time window |
| **MinIO** | Raw JSON artifacts, model checkpoints | S3-compatible object storage for unstructured blobs; separates raw from processed data |
| **Apache Kafka 3.7** | Message queue between ingestion and processing | Decouples producers from consumers; allows replay; KRaft mode eliminates Zookeeper dependency |

### 4.3 Processing Layer

**Stream processing — Apache Flink 1.18:**  
Real-time sentiment aggregation from the Kafka topic `shipping-news`. Flink reads incoming news events, computes a rolling 1-hour sentiment window, and emits aggregated signals downstream.

**Batch processing — Apache Spark (PySpark):**  
Nightly batch job (`src/processing/spark_batch.py`) re-computes 30-day trend baselines, recalibrates the route prediction weights, and writes summary statistics back to InfluxDB.

**NLP sentiment — Rule-based engine (`src/processing/models/sentiment.py`):**  
Domain-specific keyword matching for shipping industry terminology. Positive signals: *easing, normaliz, recover, reopen, stabiliz*. Negative signals: *surge, attack, disruption, congestion, strike, sanction, war, reroute*. Optionally upgrades to FinBERT (ProsusAI/finbert) when `USE_TRANSFORMER=true`.

**AI summarization — Google Gemini (`src/processing/ai_summarizer.py`):**  
Every 4 hours, queries InfluxDB and Elasticsearch directly, assembles a structured prompt containing live market prices, the 15 most recent news headlines with sentiment scores, and StockTwits community metrics for 4 tickers. Sends to `gemini-3.1-flash-lite` via REST API. Output is a professional 5-section market brief saved to `data/ai_insights.json`.

### 4.4 Prediction Model

The 7-day freight rate outlook is a **weighted composite signal** computed per route:

```
score = w_zim  × zim_7d_vs_30d_trend
      + w_oil  × oil_7d_vs_30d_trend
      + w_bulk × (sblk_trend + egle_trend) / 2
      + w_news × (−avg_news_sentiment)   # negative news → supply disruption → upward pressure
      + w_comm × avg_community_sentiment
```

Route-specific weights reflect each route's sensitivity to container vs. dry bulk dynamics:

| Route | ZIM weight | Oil weight | Bulk weight |
|---|---|---|---|
| Asia → Europe | 0.35 | 0.30 | 0.05 |
| Trans-Pacific | 0.40 | 0.25 | 0.05 |
| Asia → Middle East | 0.30 | 0.35 | 0.05 |
| Mediterranean | 0.35 | 0.30 | 0.05 |
| Dry Bulk Capesize | 0.05 | 0.15 | 0.50 |
| Supramax Bulk | 0.05 | 0.15 | 0.45 |

Direction thresholds: `score > 0.005` → UP, `score < −0.005` → DOWN, else FLAT.  
Magnitude: `|score| < 0.02` → 1 (slight), `< 0.06` → 2 (moderate), `≥ 0.06` → 3 (strong).

### 4.5 Delivery Layer

**FastAPI backend** (port 8000): RESTful API serving processed data to the dashboard. Key endpoints documented in [Section 8](#8-api-reference).

**Streamlit dashboard** (port 8501, live at http://35.208.102.111:8501): 5-page dark-theme web interface with left sidebar navigation:

| Page | Content |
|---|---|
| 📊 Overview | 6 live market metrics, 6-route prediction signals, headline preview, AI brief preview |
| 📈 Market Intelligence | 5 historical Plotly charts, trend summary table, scenario simulator |
| 📰 News & Sentiment | Sentiment scores by source, filterable news feed with NLP scores |
| 💬 Community Pulse | Per-ticker StockTwits sentiment cards, recent post feed |
| 🤖 AI Market Brief | Full Gemini-generated analysis, auto-refreshed every 4 hours |

---

## 5. Architecture Diagram

```
╔══════════════════════════════════════════════════════════════════════╗
║                        DATA INGESTION LAYER                          ║
║                                                                      ║
║  [Yahoo Finance]  [Google News RSS]  [Splash247 RSS]  [StockTwits]  ║
║       ↓                  ↓                 ↓               ↓         ║
║  real_data_fetcher   real_news_fetcher              community_       ║
║  (every 5 min)       (every 10 min)                 sentiment.py    ║
║                                                     (every 15 min)  ║
╚══════════╤═══════════════╤════════════════════════════╤═════════════╝
           │               │                            │
           ↓               ↓                            ↓
╔══════════╧═══════════════╧════════════════════════════╧═════════════╗
║                         MESSAGE QUEUE                                ║
║                    Apache Kafka 3.7 (KRaft)                          ║
║              topics: shipping-news, shipping-prices                  ║
╚══════════╤═══════════════════════════════════════════╤══════════════╝
           │                                           │
           ↓                                           ↓
╔══════════╧════════════╗              ╔═══════════════╧══════════════╗
║  STREAM PROCESSING    ║              ║     BATCH PROCESSING         ║
║  Apache Flink 1.18    ║              ║     Apache Spark (PySpark)   ║
║  - Sentiment window   ║              ║     - Trend baselines        ║
║  - Rolling aggregates ║              ║     - Weight recalibration   ║
╚══════════╤════════════╝              ╚═══════════════╤══════════════╝
           │                                           │
           ↓                                           ↓
╔══════════╧═══════════════════════════════════════════╧══════════════╗
║                          STORAGE LAYER                               ║
║                                                                      ║
║  ┌─────────────────┐  ┌──────────────────────┐  ┌───────────────┐  ║
║  │  InfluxDB 2.7   │  │  Elasticsearch 8.13  │  │    MinIO      │  ║
║  │  Time-series    │  │  News + Sentiment     │  │  Raw objects  │  ║
║  │  port 8086      │  │  Community posts      │  │  port 9000    │  ║
║  │  90-day retain  │  │  port 9200            │  │               │  ║
║  └────────┬────────┘  └──────────┬───────────┘  └───────────────┘  ║
╚═══════════╪══════════════════════╪═════════════════════════════════╝
            │                      │
            └──────────┬───────────┘
                       ↓
╔══════════════════════╧══════════════════════════════════════════════╗
║                       AI SYNTHESIS LAYER                             ║
║                                                                      ║
║     ai_summarizer.py  →  Google Gemini 3.1 Flash Lite               ║
║     (every 4 hours)       data/ai_insights.json                      ║
╚══════════════════════╤══════════════════════════════════════════════╝
                       ↓
╔══════════════════════╧══════════════════════════════════════════════╗
║                        DELIVERY LAYER                                ║
║                                                                      ║
║  FastAPI backend (port 8000)  ←──  Streamlit Dashboard (port 8501)  ║
║  /api/metrics/latest               📊 Overview                      ║
║  /api/metrics/history              📈 Market Intelligence            ║
║  /api/news/latest                  📰 News & Sentiment               ║
║  /api/community/sentiment          💬 Community Pulse                ║
║  /api/predict/routes               🤖 AI Market Brief                ║
║  /api/ai/insights                                                    ║
╚═════════════════════════════════════════════════════════════════════╝

Infrastructure: GCP e2 VM (ARM64, 2 vCPU, 8 GB RAM) · Ubuntu 26.04
All services containerized via Docker Compose on a shared bridge network
```

---

## 6. Repository Structure

```
shipping-prediction/
├── deploy/
│   └── docker-compose.yml          # All 6 containerized services
├── src/
│   ├── ingestion/
│   │   ├── real_data_fetcher.py    # Yahoo Finance → InfluxDB (every 5 min)
│   │   ├── real_news_fetcher.py    # RSS feeds → Elasticsearch (every 10 min)
│   │   ├── community_sentiment.py  # StockTwits → Elasticsearch (every 15 min)
│   │   └── timeseries_producer.py  # Kafka producer for market events
│   ├── processing/
│   │   ├── ai_summarizer.py        # Gemini AI market brief generator (every 4h)
│   │   ├── spark_batch.py          # PySpark nightly batch job
│   │   ├── jobs/
│   │   │   └── sentiment_consumer.py  # Flink sentiment aggregation
│   │   └── models/
│   │       └── sentiment.py        # Rule-based NLP + optional FinBERT
│   ├── dashboard/
│   │   ├── app.py                  # Streamlit multi-page dashboard
│   │   └── api/
│   │       └── main.py             # FastAPI backend
│   └── utils/
│       ├── es_client.py
│       ├── influxdb_client.py
│       └── kafka_client.py
├── data/
│   └── ai_insights.json            # Latest Gemini-generated market brief
├── logs/
│   ├── fastapi.log
│   ├── streamlit.log
│   └── ai.log
├── configs/
├── requirements.txt
├── .env                            # Environment variables (see below)
└── .streamlit/
    └── config.toml                 # Dark tech theme
```

---

## 7. How to Run

### Prerequisites

- Python 3.11+ (tested on 3.14.4)
- Docker + Docker Compose
- 8 GB RAM recommended (6 GB minimum with swap)
- Google AI Studio API key (free at https://aistudio.google.com) — required only for AI briefs

### Step 1: Clone and configure environment

```bash
git clone git@github.com:GuoYuKai-SaMuEl/shipping-prediction.git
cd shipping-prediction

cat > .env << 'EOF'
KAFKA_BROKER=localhost:9092
ES_HOST=http://localhost:9200
INFLUX_URL=http://localhost:8086
INFLUX_TOKEN=shipping-super-secret-token
INFLUX_ORG=shipping-org
INFLUX_BUCKET=shipping-metrics
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123
GEMINI_API_KEY=your_key_here        # optional, only for AI brief feature
EOF
```

### Step 2: Start infrastructure (Docker)

```bash
cd deploy
docker compose up -d

# Verify all 6 services are healthy (~60 seconds for Elasticsearch to initialize)
docker compose ps
```

Services started:
| Container | Port | Purpose |
|---|---|---|
| shipping-kafka | 9092 | Message queue (KRaft mode) |
| shipping-es | 9200 | News & sentiment search |
| shipping-influxdb | 8086 | Time-series market data |
| shipping-minio | 9000, 9001 | Object storage |
| shipping-flink-jm | 8081 | Flink job manager |
| shipping-flink-tm | — | Flink task manager |

### Step 3: Set up Python environment

```bash
cd ..  # back to project root
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Note: kafka-python 2.0.2 is incompatible with Python 3.14+
# Use kafka-python-ng instead:
pip install kafka-python-ng
```

### Step 4: Start data ingestion

```bash
source .env && export $(cut -d= -f1 .env)
source .venv/bin/activate

# Market data (Yahoo Finance → InfluxDB), updates every 5 minutes
nohup python -m src.ingestion.real_data_fetcher --watch > logs/fetcher.log 2>&1 &

# Shipping news (RSS → Elasticsearch), updates every 10 minutes
nohup python -m src.ingestion.real_news_fetcher --interval 600 > logs/news.log 2>&1 &

# Community sentiment (StockTwits → Elasticsearch), updates every 15 minutes
nohup python -m src.ingestion.community_sentiment --interval 900 > logs/community.log 2>&1 &
```

### Step 5: Start the API and dashboard

```bash
# FastAPI backend
nohup uvicorn src.dashboard.api.main:app --host 0.0.0.0 --port 8000 > logs/fastapi.log 2>&1 &

# Streamlit dashboard
nohup streamlit run src/dashboard/app.py --server.port 8501 --server.headless true > logs/streamlit.log 2>&1 &
```

Dashboard is now available at: **http://localhost:8501**

### Step 6: Start AI Market Brief auto-refresh (optional)

Requires `GEMINI_API_KEY` in `.env`.

```bash
export GEMINI_API_KEY=your_key_here
# Generates a new AI brief every 4 hours
nohup python -m src.processing.ai_summarizer --interval 14400 > logs/ai.log 2>&1 &
```

Or trigger a one-time generation:
```bash
python -m src.processing.ai_summarizer --once
```

### Reproducing the Demand Evidence Data Collection

The forum and job posting analysis referenced in Section 2 can be partially reproduced:

```bash
# Fetch recent shipping news to inspect headline sentiment distribution
python -m src.ingestion.real_news_fetcher --once
# Query Elasticsearch for sentiment breakdown
curl -s http://localhost:9200/shipping-news-index/_search \
  -H 'Content-Type: application/json' \
  -d '{"size":0,"aggs":{"by_source":{"terms":{"field":"source"}},"avg_score":{"avg":{"field":"score"}}}}'
```

---

## 8. API Reference

Base URL: `http://localhost:8000`

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Service health check |
| GET | `/api/metrics/latest` | Latest prices: WTI, BDRY, ZIM, SBLK, EGLE, dry bulk composite |
| GET | `/api/metrics/history?days=30` | Historical daily OHLC for all tickers (7–88 days) |
| GET | `/api/news/latest?size=20` | Most recent news articles with NLP sentiment scores |
| GET | `/api/news/sentiment` | Aggregated sentiment by source + overall average |
| GET | `/api/community/sentiment` | StockTwits 48h sentiment per ticker (ZIM/SBLK/EGLE/BDRY) |
| GET | `/api/community/recent?ticker=ZIM&size=10` | Individual posts for a ticker |
| GET | `/api/predict/routes` | 6-route 7-day outlook: direction, magnitude, driver breakdown |
| POST | `/api/predict` | Custom scenario: `{oil_price, dry_bulk_index, sentiment_score}` → predicted rate (USD/TEU) |
| GET | `/api/ai/insights` | Latest Gemini-generated market brief |
| POST | `/api/ai/refresh` | Trigger immediate Gemini brief generation (requires `GEMINI_API_KEY` in env) |

Interactive API docs: `http://localhost:8000/docs`

---

## 9. Scalability & Cost

This section covers two deployment tracks: the **full big data stack** used in this prototype, and a leaner **web-optimized stack** that trades distributed-system complexity for dramatically lower operating costs — more realistic for an early-stage product.

---

### Track A — Full Big Data Stack (current prototype)

The current deployment runs Kafka, Flink, Spark, Elasticsearch, InfluxDB, and MinIO as Docker containers on a single GCP VM. This architecture is designed to demonstrate course concepts; it is over-engineered for the traffic volume of an MVP.

#### Current prototype cost

| Resource | Spec | Monthly cost |
|---|---|---|
| GCP e2-standard-2 VM | 2 vCPU, 8 GB RAM, ARM64 | ~USD 50 |
| Disk (SSD boot + data) | 50 GB | ~USD 5 |
| Custom domain (sguo.site) | — | ~USD 1 |
| Gemini API (AI Studio free tier) | 15 RPM, 1 M tokens/day | USD 0 |
| Data sources (Yahoo Finance, RSS, StockTwits) | — | USD 0 |
| **Total** | | **~USD 56/month** |

**Break-even:** 1 paying user at USD 59/month subscription covers infrastructure. The barrier is not cost but customer acquisition.

#### At 10× scale (100 concurrent users, 10 tenants)

Bottlenecks shift to Elasticsearch memory and data licensing as latency requirements tighten.

| Change | Cost |
|---|---|
| Licensed market data feed (ICE/Refinitiv WebSocket) | +USD 500 |
| Elasticsearch 3-node cluster (GCP) | +USD 300 |
| InfluxDB Cloud (10 GB/month write) | +USD 250 |
| Additional VM for FastAPI replicas + load balancer | +USD 80 |
| **Estimated total** | **~USD 1,200/month** |

Break-even: **5 tenants at USD 249/month** — achievable but requires a real sales effort.

#### At 100× scale (1,000+ users, enterprise)

| Change | Cost |
|---|---|
| Confluent Cloud (managed Kafka, high throughput) | +USD 1,000 |
| Databricks (Spark batch, elastic) | +USD 800 |
| Elasticsearch Cloud (6 nodes, HA) | +USD 1,200 |
| Gemini enterprise quota | +USD 500 |
| Load balancer, CDN, monitoring | +USD 300 |
| **Estimated total** | **~USD 4,000/month** |

Break-even: **20 tenants at USD 199/month** — viable as a niche B2B SaaS.

---

### Track B — Web-Optimized Lightweight Stack (lower-cost path)

For an early commercial product serving tens of users, the distributed big data stack is unnecessary overhead. Most of its components can be replaced with leaner equivalents that require no cluster management:

| Big data component | Lightweight replacement | Saving |
|---|---|---|
| Apache Kafka | Python `schedule` + cron jobs | −USD 0 (removes operational complexity) |
| Apache Flink | SQLite/PostgreSQL triggers | −USD 0 |
| Elasticsearch | PostgreSQL with full-text search (`tsvector`) | −USD 50–300/month |
| InfluxDB | TimescaleDB (PostgreSQL extension) | −USD 30–250/month |
| MinIO | Local filesystem or Cloudflare R2 (free 10 GB) | −USD 5–20/month |
| GCP e2 VM | Hetzner CAX11 (ARM64, 2 vCPU, 4 GB RAM) | −USD 42/month |

#### Lightweight stack cost at MVP scale (1–20 users)

| Resource | Spec | Monthly cost |
|---|---|---|
| Hetzner CAX11 VPS (ARM64) | 2 vCPU, 4 GB RAM | EUR 3.79 (~USD 4) |
| Cloudflare R2 storage | 10 GB free tier | USD 0 |
| PostgreSQL + TimescaleDB | Self-hosted on same VPS | USD 0 |
| Gemini API (AI Studio free tier) | Sufficient for ≤ 20 brief/day | USD 0 |
| Custom domain + SSL (Let's Encrypt) | — | ~USD 1 |
| **Total** | | **~USD 5/month** |

**Break-even: 1 paying user at any price above USD 5/month.**  
At a USD 29/month starter plan, a single customer generates **5.8× the operating cost** — the business is immediately profitable from the first subscriber.

#### Lightweight stack at 10× scale (200 users)

| Resource | Monthly cost |
|---|---|
| Hetzner CAX31 (8 vCPU, 16 GB RAM) | EUR 13 (~USD 14) |
| Managed PostgreSQL (Hetzner DBaaS) | EUR 20 (~USD 22) |
| Cloudflare R2 (100 GB data) | USD 1.50 |
| Gemini API (pay-as-you-go, ~500 briefs/month) | ~USD 5 |
| **Total** | **~USD 43/month** |

Break-even: **2 paying users at USD 29/month**, or **1 user at USD 49/month**.

#### Lightweight stack at 100× scale (2,000 users)

At this scale, managed services become cost-effective:

| Resource | Monthly cost |
|---|---|
| Hetzner CCX53 dedicated (32 vCPU, 128 GB RAM) | EUR 200 (~USD 220) |
| Managed PostgreSQL, HA pair | EUR 80 (~USD 88) |
| Cloudflare CDN + R2 | USD 20 |
| Redis Cloud (session cache) | USD 15 |
| Gemini API (5,000 briefs/month) | ~USD 50 |
| Monitoring (Grafana Cloud free tier) | USD 0 |
| **Total** | **~USD 393/month** |

Break-even: **14 paying users at USD 29/month** — or, more realistically at this user count, **4 tenants at USD 99/month**.

#### Why keep the big data stack at all?

The full stack (Kafka, Flink, Spark) is not wasted: it provides a direct upgrade path when the product outgrows the lightweight stack. Concretely:
- **Kafka** becomes valuable when ingestion sources exceed 10 and need decoupling (e.g., adding AIS vessel tracking, port congestion feeds, customs data).
- **Flink** adds value when real-time alerting (e.g., "rate spike detected — alert user") needs sub-second latency.
- **Spark** enables historical backtesting of prediction models across years of data — not possible with TimescaleDB at petabyte scale.

The lightweight stack is the right choice for months 0–18; the full big data stack is the right architecture for months 18+, once product-market fit is established and data volume justifies the operational overhead.

---

## Technical Notes

**ARM64 compatibility:** All Docker images selected for multi-architecture support (apache/kafka:3.7.1, elasticsearch:8.13.4, influxdb:2.7, flink:1.18.1-java11). Tested on GCP Tau T2A (Ampere Altra ARM64).

**Python 3.14 compatibility:** `kafka-python 2.0.2` fails with `ModuleNotFoundError: No module named 'kafka.vendor.six.moves'`. Use `kafka-python-ng` as drop-in replacement.

**InfluxDB retention:** 90-day bucket retention policy. Ingestion rejects data older than 88 days to avoid write errors (`422 Unprocessable Entity`).

**Streamlit theme:** Custom dark tech theme defined in `.streamlit/config.toml` with primary color `#00d4ff` on `#050d1a` background.
