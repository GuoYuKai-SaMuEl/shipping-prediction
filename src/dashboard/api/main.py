"""
FastAPI backend: Shipping Rate Prediction API
Data sources: InfluxDB (market time-series) + Elasticsearch (news & community sentiment)
"""
import json
import os
import urllib.request
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from influxdb_client import InfluxDBClient
from pydantic import BaseModel

BASE_DIR      = Path(__file__).resolve().parents[3]
INSIGHTS_PATH = BASE_DIR / "data" / "ai_insights.json"

INFLUX_URL    = "http://localhost:8086"
INFLUX_TOKEN  = "shipping-super-secret-token"
INFLUX_ORG    = "shipping-org"
INFLUX_BUCKET = "shipping-metrics"
ES_HOST       = "http://localhost:9200"

app = FastAPI(title="ShipPulse Maritime Intelligence API", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ── 工具函式 ──────────────────────────────────────────────────

def influx_query(flux: str):
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    tables = client.query_api().query(flux)
    client.close()
    return tables


def es_post(path: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req  = urllib.request.Request(
        f"{ES_HOST}{path}", data=data,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    return json.loads(urllib.request.urlopen(req, timeout=10).read())


def last_influx(measurement: str, field: str, tag_filter: str = "") -> float | None:
    tag_clause = f'|> filter(fn:(r) => r["source"] == "{tag_filter}")' if tag_filter else ""
    flux = f'''
    from(bucket:"{INFLUX_BUCKET}")
      |> range(start: -7d)
      |> filter(fn:(r) => r._measurement == "{measurement}" and r._field == "{field}")
      {tag_clause}
      |> last()
    '''
    for t in influx_query(flux):
        for r in t.records:
            return r.get_value()
    return None


# ── Endpoints ─────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/metrics/latest")
def get_latest_metrics():
    try:
        oil  = last_influx("oil_price",  "value")
        bdry = last_influx("bdi_proxy_etf", "close", "bdry")
        zim  = last_influx("container_stock", "close", "zim")
        sblk = last_influx("shipping_stock",  "close", "star_bulk")
        egle = last_influx("shipping_stock",  "close", "eagle_bulk")

        dry_bulk_composite = None
        if sblk and egle:
            dry_bulk_composite = round((sblk + egle) / 2, 2)

        return {
            "oil_price_usd":        round(oil,  2) if oil  else None,
            "bdry_etf":             round(bdry, 3) if bdry else None,
            "zim_stock":            round(zim,  2) if zim  else None,
            "dry_bulk_composite":   dry_bulk_composite,
            "sblk":                 round(sblk, 2) if sblk else None,
            "egle":                 round(egle, 2) if egle else None,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/metrics/history")
def get_history(days: int = 30):
    def query_series(measurement, field, source_tag=None):
        tag = f'|> filter(fn:(r) => r["source"] == "{source_tag}")' if source_tag else ""
        flux = f'''
        from(bucket:"{INFLUX_BUCKET}")
          |> range(start: -{days}d)
          |> filter(fn:(r) => r._measurement == "{measurement}" and r._field == "{field}")
          {tag}
          |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)
        '''
        rows = []
        for t in influx_query(flux):
            for r in t.records:
                v = r.get_value()
                if v is not None:
                    rows.append({
                        "time":  r.get_time().strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "value": round(v, 2),
                    })
        return rows

    try:
        return {
            "oil":     query_series("oil_price",       "value"),
            "bdry":    query_series("bdi_proxy_etf",   "close",  "bdry"),
            "zim":     query_series("container_stock", "close",  "zim"),
            "sblk":    query_series("shipping_stock",  "close",  "star_bulk"),
            "egle":    query_series("shipping_stock",  "close",  "eagle_bulk"),
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/news/latest")
def get_latest_news(size: int = 15):
    try:
        resp = es_post("/shipping-news-index/_search", {
            "query": {"match_all": {}},
            "sort":  [{"indexed_at": {"order": "desc"}}],
            "size":  size,
        })
        return [h["_source"] for h in resp["hits"]["hits"]]
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/news/sentiment")
def get_news_sentiment():
    try:
        resp = es_post("/shipping-news-index/_search", {
            "size": 0,
            "aggs": {
                "by_source": {
                    "terms": {"field": "source", "size": 10},
                    "aggs": {
                        "by_sentiment": {"terms": {"field": "sentiment"}},
                        "avg_score":    {"avg":   {"field": "score"}},
                    },
                },
                "overall_sentiment": {"terms": {"field": "sentiment"}},
                "overall_avg":       {"avg":   {"field": "score"}},
            },
        })
        aggs    = resp["aggregations"]
        overall = {b["key"]: b["doc_count"] for b in aggs["overall_sentiment"]["buckets"]}
        sources = []
        for b in aggs["by_source"]["buckets"]:
            dist = {s["key"]: s["doc_count"] for s in b["aggs"]["by_sentiment"]["buckets"]} if "aggs" in b else \
                   {s["key"]: s["doc_count"] for s in b.get("by_sentiment", {}).get("buckets", [])}
            sources.append({
                "source":    b["key"],
                "count":     b["doc_count"],
                "avg_score": round(b["avg_score"]["value"] or 0, 3),
            })
        return {
            "overall":    overall,
            "avg_score":  round(aggs["overall_avg"]["value"] or 0, 3),
            "by_source":  sources,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/community/sentiment")
def get_community_sentiment():
    try:
        tickers = ["ZIM", "SBLK", "EGLE", "BDRY"]
        result  = {}
        for ticker in tickers:
            resp = es_post("/shipping-community-sentiment/_search", {
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
            result[ticker] = {
                "total":    total,
                "avg_score": round(avg, 3),
                "positive": dist.get("positive", 0),
                "negative": dist.get("negative", 0),
                "neutral":  dist.get("neutral",  0),
            }
        return result
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/predict/routes")
def predict_routes():
    """
    根據目前市場指標，預測六大主要航線運費的漲跌方向與幅度等級。
    幅度等級：1=輕微(<3%)  2=中等(3-8%)  3=顯著(>8%)
    """
    try:
        # ── 取得各指標近 7 天與近 30 天均值，計算趨勢 ──────────
        def trend(measurement, field, source_tag=None):
            tag = f'|> filter(fn:(r) => r["source"] == "{source_tag}")' if source_tag else ""
            def avg(window):
                flux = f'''
                from(bucket:"{INFLUX_BUCKET}")
                  |> range(start: -{window}d)
                  |> filter(fn:(r) => r._measurement == "{measurement}" and r._field == "{field}")
                  {tag}
                  |> mean()
                '''
                for t in influx_query(flux):
                    for r in t.records:
                        return r.get_value() or 0
                return 0
            a7, a30 = avg(7), avg(30)
            return (a7 - a30) / a30 if a30 else 0   # 正 = 近期偏高，運費傾向上漲

        oil_trend   = trend("oil_price",       "value")
        bdry_trend  = trend("bdi_proxy_etf",   "close", "bdry")
        zim_trend   = trend("container_stock", "close", "zim")
        sblk_trend  = trend("shipping_stock",  "close", "star_bulk")
        egle_trend  = trend("shipping_stock",  "close", "eagle_bulk")
        bulk_trend  = (sblk_trend + egle_trend) / 2

        # ── 新聞與社群情緒（負面 = 供應中斷 = 運費上漲壓力） ───
        try:
            ns_resp    = es_post("/shipping-news-index/_search",
                                 {"size":0,"aggs":{"avg":{"avg":{"field":"score"}}}})
            news_sent  = ns_resp["aggregations"]["avg"]["value"] or 0
        except Exception:
            news_sent = 0

        try:
            cs_resp   = es_post("/shipping-community-sentiment/_search",
                                {"size":0,"aggs":{"avg":{"avg":{"field":"score"}}}})
            comm_sent = cs_resp["aggregations"]["avg"]["value"] or 0
        except Exception:
            comm_sent = 0

        disruption = -news_sent   # 負面新聞 → 供應中斷 → 運費上漲

        # ── 各航線評分模型（加權合成） ─────────────────────────
        routes = {
            "asia_europe": {
                "name":  "亞歐航線",
                "name_en": "Asia → Europe",
                "desc":  "Shanghai → Rotterdam",
                "score": zim_trend*0.35 + oil_trend*0.30 + disruption*0.25 + comm_sent*0.10,
                "type":  "container",
            },
            "trans_pacific": {
                "name":  "跨太平洋",
                "name_en": "Trans-Pacific",
                "desc":  "Shanghai → Los Angeles",
                "score": zim_trend*0.40 + oil_trend*0.25 + disruption*0.25 + comm_sent*0.10,
                "type":  "container",
            },
            "asia_mideast": {
                "name":  "亞洲↔中東",
                "name_en": "Asia → Middle East",
                "desc":  "Shanghai → Jeddah / Dubai",
                "score": zim_trend*0.30 + oil_trend*0.35 + disruption*0.25 + comm_sent*0.10,
                "type":  "container",
            },
            "mediterranean": {
                "name":  "地中海航線",
                "name_en": "Mediterranean",
                "desc":  "Shanghai → Genoa / Barcelona",
                "score": zim_trend*0.35 + oil_trend*0.30 + disruption*0.25 + comm_sent*0.10,
                "type":  "container",
            },
            "dry_bulk_cape": {
                "name":  "乾散貨（好望角）",
                "name_en": "Dry Bulk Capesize",
                "desc":  "Brazil / Australia → China",
                "score": bulk_trend*0.50 + bdry_trend*0.30 + oil_trend*0.15 + disruption*0.05,
                "type":  "dry_bulk",
            },
            "dry_bulk_supra": {
                "name":  "乾散貨（靈便型）",
                "name_en": "Supramax Bulk",
                "desc":  "Global grain / coal routes",
                "score": bulk_trend*0.45 + bdry_trend*0.35 + oil_trend*0.15 + disruption*0.05,
                "type":  "dry_bulk",
            },
        }

        result = {}
        for key, r in routes.items():
            s   = r["score"]
            mag = 1 if abs(s) < 0.02 else 2 if abs(s) < 0.06 else 3
            result[key] = {
                "name":     r["name"],
                "name_en":  r["name_en"],
                "desc":     r["desc"],
                "type":     r["type"],
                "direction": "up"   if s > 0.005 else "down" if s < -0.005 else "flat",
                "magnitude": mag,
                "score":    round(s, 4),
                "drivers": {
                    "oil_trend":   round(oil_trend,  4),
                    "bulk_trend":  round(bulk_trend,  4),
                    "zim_trend":   round(zim_trend,   4),
                    "disruption":  round(disruption,  4),
                    "community":   round(comm_sent,   3),
                },
            }
        return result
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/community/recent")
def get_community_recent(ticker: str = "ZIM", size: int = 10):
    try:
        resp = es_post("/shipping-community-sentiment/_search", {
            "query": {"bool": {"must": [
                {"term": {"ticker": ticker}},
                {"range": {"indexed_at": {"gte": "now-48h"}}},
            ]}},
            "sort": [{"indexed_at": {"order": "desc"}}],
            "size": size,
        })
        return [h["_source"] for h in resp["hits"]["hits"]]
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/ai/insights")
def get_ai_insights():
    if not INSIGHTS_PATH.exists():
        return {"summary": None, "generated_at": None, "meta": {}}
    try:
        return json.loads(INSIGHTS_PATH.read_text())
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/api/ai/refresh")
async def refresh_ai_insights():
    import asyncio
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY not configured on server")
    try:
        import sys
        sys.path.insert(0, str(BASE_DIR))
        from src.processing.ai_summarizer import generate_and_save
        result = await asyncio.to_thread(generate_and_save, api_key)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class PredictionRequest(BaseModel):
    oil_price:       float
    dry_bulk_index:  float
    sentiment_score: float
    horizon_days:    int = 7


@app.post("/api/predict")
def predict_freight_rate(req: PredictionRequest):
    base_rate        = 2200
    oil_effect       = (req.oil_price - 80) * 8.5
    bulk_effect      = (req.dry_bulk_index - 27) * 15.0   # SBLK/EGLE composite ≈ 27 baseline
    sentiment_effect = req.sentiment_score * 150
    predicted        = base_rate + oil_effect + bulk_effect + sentiment_effect
    confidence       = max(0.55, min(0.92, 0.75 + abs(req.sentiment_score) * 0.1))
    return {
        "predicted_rate_usd_per_teu": round(predicted, 0),
        "confidence":  round(confidence, 3),
        "horizon_days": req.horizon_days,
        "components": {
            "base_rate":              base_rate,
            "oil_contribution":       round(oil_effect, 1),
            "bulk_stock_contribution": round(bulk_effect, 1),
            "sentiment_contribution": round(sentiment_effect, 1),
        },
    }
