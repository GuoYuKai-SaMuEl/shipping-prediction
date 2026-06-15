"""
AI Market Brief Generator — Google Gemini via REST API (no extra packages)
Queries InfluxDB + ES directly, calls Gemini, saves to data/ai_insights.json

Run once:        python -m src.processing.ai_summarizer --once
Run periodically: python -m src.processing.ai_summarizer --interval 14400
"""
import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

from influxdb_client import InfluxDBClient

BASE_DIR      = Path(__file__).resolve().parents[2]
INSIGHTS_PATH = BASE_DIR / "data" / "ai_insights.json"

INFLUX_URL    = "http://localhost:8086"
INFLUX_TOKEN  = "shipping-super-secret-token"
INFLUX_ORG    = "shipping-org"
INFLUX_BUCKET = "shipping-metrics"
ES_HOST       = "http://localhost:9200"
GEMINI_MODEL  = "gemini-3.1-flash-lite"


# ── Data collection ───────────────────────────────────────────

def influx_last(measurement: str, field: str, source_tag: str = "") -> float | None:
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    tag = f'|> filter(fn:(r) => r["source"] == "{source_tag}")' if source_tag else ""
    flux = f'''
    from(bucket:"{INFLUX_BUCKET}")
      |> range(start: -7d)
      |> filter(fn:(r) => r._measurement == "{measurement}" and r._field == "{field}")
      {tag}
      |> last()
    '''
    try:
        for t in client.query_api().query(flux):
            for r in t.records:
                return r.get_value()
    finally:
        client.close()
    return None


def es_search(path: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req  = urllib.request.Request(
        f"{ES_HOST}{path}", data=data,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    return json.loads(urllib.request.urlopen(req, timeout=10).read())


def collect_data() -> dict:
    # Market metrics from InfluxDB
    metrics = {}
    try:
        oil  = influx_last("oil_price",       "value")
        bdry = influx_last("bdi_proxy_etf",   "close", "bdry")
        zim  = influx_last("container_stock", "close", "zim")
        sblk = influx_last("shipping_stock",  "close", "star_bulk")
        egle = influx_last("shipping_stock",  "close", "eagle_bulk")
        metrics = {
            "oil_price_usd":      round(oil,  2) if oil  else None,
            "bdry_etf":           round(bdry, 3) if bdry else None,
            "zim_stock":          round(zim,  2) if zim  else None,
            "sblk":               round(sblk, 2) if sblk else None,
            "egle":               round(egle, 2) if egle else None,
            "dry_bulk_composite": round((sblk + egle) / 2, 2) if sblk and egle else None,
        }
    except Exception as e:
        print(f"  [warn] InfluxDB: {e}")

    # News from ES
    news = []
    try:
        resp = es_search("/shipping-news-index/_search", {
            "query": {"match_all": {}},
            "sort":  [{"indexed_at": {"order": "desc"}}],
            "size":  20,
        })
        news = [h["_source"] for h in resp["hits"]["hits"]]
    except Exception as e:
        print(f"  [warn] ES news: {e}")

    # News sentiment aggregation
    sentiment = {}
    try:
        resp = es_search("/shipping-news-index/_search", {
            "size": 0,
            "aggs": {
                "overall": {"terms": {"field": "sentiment"}},
                "avg":     {"avg":   {"field": "score"}},
                "by_source": {
                    "terms": {"field": "source", "size": 10},
                    "aggs": {"avg_score": {"avg": {"field": "score"}}},
                },
            },
        })
        aggs = resp["aggregations"]
        sentiment = {
            "avg_score": round(aggs["avg"]["value"] or 0, 3),
            "overall":   {b["key"]: b["doc_count"] for b in aggs["overall"]["buckets"]},
            "by_source": [
                {"source": b["key"], "count": b["doc_count"],
                 "avg_score": round(b["avg_score"]["value"] or 0, 3)}
                for b in aggs["by_source"]["buckets"]
            ],
        }
    except Exception as e:
        print(f"  [warn] ES sentiment: {e}")

    # Community sentiment from ES
    community = {}
    try:
        for ticker in ["ZIM", "SBLK", "EGLE", "BDRY"]:
            resp = es_search("/shipping-community-sentiment/_search", {
                "size": 0,
                "query": {"bool": {"must": [
                    {"term": {"ticker": ticker}},
                    {"range": {"indexed_at": {"gte": "now-48h"}}},
                ]}},
                "aggs": {
                    "by_sentiment": {"terms": {"field": "sentiment"}},
                    "avg_score":    {"avg":   {"field": "score"}},
                },
            })
            buckets = resp["aggregations"]["by_sentiment"]["buckets"]
            avg     = resp["aggregations"]["avg_score"]["value"] or 0
            dist    = {b["key"]: b["doc_count"] for b in buckets}
            total   = sum(dist.values())
            community[ticker] = {
                "total": total, "avg_score": round(avg, 3),
                "positive": dist.get("positive", 0),
                "negative": dist.get("negative", 0),
                "neutral":  dist.get("neutral", 0),
            }
    except Exception as e:
        print(f"  [warn] ES community: {e}")

    return {"metrics": metrics, "news": news, "sentiment": sentiment, "community": community}


# ── Prompt builder ────────────────────────────────────────────

def build_prompt(data: dict) -> str:
    m   = data["metrics"]
    s   = data["sentiment"]
    com = data["community"]

    headlines = "\n".join(
        f"  [{a.get('score', 0):+.2f}] {a.get('title', 'N/A')} ({a.get('source', '')})"
        for a in data["news"][:15]
    ) or "  No recent news available."

    comm_lines = "\n".join(
        f"  ${t}: score={info.get('avg_score', 0):+.3f}  "
        f"bull={info.get('positive', 0)}  bear={info.get('negative', 0)}  "
        f"total={info.get('total', 0)}"
        for t, info in com.items()
    ) or "  No community data."

    overall = s.get("overall", {})
    avg_sc  = s.get("avg_score", 0)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return f"""You are a senior maritime shipping market analyst producing a professional intelligence brief. Data collected at {now_str}.

MARKET PRICES (live)
  WTI Crude Oil:        ${m.get('oil_price_usd', 'N/A')}/bbl
  BDRY Dry Bulk ETF:    ${m.get('bdry_etf', 'N/A')}
  ZIM Container Shares: ${m.get('zim_stock', 'N/A')}
  Star Bulk (SBLK):     ${m.get('sblk', 'N/A')}
  Eagle Bulk (EGLE):    ${m.get('egle', 'N/A')}
  Dry Bulk Composite:   ${m.get('dry_bulk_composite', 'N/A')}

NEWS SENTIMENT (last 24h)
  Aggregate score: {avg_sc:+.3f}  |  Positive: {overall.get('positive', 0)}  Negative: {overall.get('negative', 0)}  Neutral: {overall.get('neutral', 0)}
  Recent headlines (sentiment score, title, source):
{headlines}

COMMUNITY SENTIMENT — StockTwits (last 48h)
{comm_lines}

---

Write a professional maritime market intelligence brief with exactly these five labeled sections. Plain text only, no markdown symbols, no asterisks, no bullet dashes:

EXECUTIVE SUMMARY
Two to three sentences. State the overall market direction and the single most important driver.

KEY MARKET DRIVERS
List three to five numbered factors shaping freight rates right now. Be specific: cite price levels, percentage moves, or named routes where relevant.

RISK FACTORS
List two to three numbered downside risks. Reference supply chain disruptions, geopolitical factors, or commodity price volatility as appropriate.

OPPORTUNITIES
List two to three numbered upside catalysts. Focus on routes, commodities, or market segments with favorable dynamics.

ROUTE OUTLOOK
One paragraph. Compare container shipping (Asia-Europe, Trans-Pacific) vs dry bulk (Capesize, Supramax) outlook for the coming week. Mention concrete routes or trade lanes.

ANALYST NOTE
One sentence on data confidence or any caveats about the indicators used.

Keep total response under 550 words. Use professional shipping industry terminology (TEU, BDI, Capesize, Supramax, SCFI, etc.) where appropriate."""


# ── Gemini API call ───────────────────────────────────────────

def call_gemini(prompt: str, api_key: str) -> str:
    url  = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={api_key}"
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.25, "maxOutputTokens": 1024},
    }).encode()
    req  = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    resp = json.loads(urllib.request.urlopen(req, timeout=90).read())
    return resp["candidates"][0]["content"]["parts"][0]["text"].strip()


# ── Main entry ────────────────────────────────────────────────

def generate_and_save(api_key: str) -> dict:
    """Collect data, call Gemini, persist to disk, return result dict."""
    print(f"[AI] Collecting data...")
    data = collect_data()
    news_count = len(data["news"])
    comm_total = sum(v.get("total", 0) for v in data["community"].values())
    indicators = len([v for v in data["metrics"].values() if v is not None])
    print(f"  News: {news_count} articles  Community: {comm_total} msgs  Indicators: {indicators}")

    print("[AI] Calling Gemini...")
    prompt  = build_prompt(data)
    summary = call_gemini(prompt, api_key)
    print(f"  Response: {len(summary)} chars")

    result = {
        "summary":      summary,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "meta": {
            "news_count":     news_count,
            "community_msgs": comm_total,
            "indicators":     indicators,
            "model":          GEMINI_MODEL,
        },
    }
    INSIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    INSIGHTS_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"[AI] Saved → {INSIGHTS_PATH}")
    return result


def run_loop(interval: int):
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        print("ERROR: GEMINI_API_KEY environment variable not set.")
        sys.exit(1)
    print(f"[AI Summarizer] interval={interval}s ({interval / 3600:.1f}h)")
    while True:
        try:
            generate_and_save(api_key)
        except Exception as e:
            print(f"[AI] ERROR: {e}")
        print(f"[AI] Next run in {interval}s...")
        time.sleep(interval)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--once",     action="store_true", help="Run once and exit")
    p.add_argument("--interval", type=int, default=14400, help="Interval in seconds (default 4h)")
    args = p.parse_args()

    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        print("ERROR: Set GEMINI_API_KEY before running.")
        sys.exit(1)

    if args.once:
        generate_and_save(key)
    else:
        run_loop(args.interval)
