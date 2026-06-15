"""
FastAPI 後端：運價預測 API
數據來源：InfluxDB（市場時序）+ Elasticsearch（新聞 & 社群情緒）
"""
import json
import urllib.request
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from influxdb_client import InfluxDBClient
from pydantic import BaseModel

INFLUX_URL    = "http://localhost:8086"
INFLUX_TOKEN  = "shipping-super-secret-token"
INFLUX_ORG    = "shipping-org"
INFLUX_BUCKET = "shipping-metrics"
ES_HOST       = "http://localhost:9200"

app = FastAPI(title="海運運價預測 API", version="2.0.0")
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
