"""
FastAPI 後端：為 Streamlit Dashboard 提供預測結果與歷史數據 API
"""
import urllib.request
import json
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from influxdb_client import InfluxDBClient

INFLUX_URL    = "http://localhost:8086"
INFLUX_TOKEN  = "shipping-super-secret-token"
INFLUX_ORG    = "shipping-org"
INFLUX_BUCKET = "shipping-metrics"
ES_HOST       = "http://localhost:9200"
ES_INDEX      = "shipping-news-index"

app = FastAPI(title="海運運價預測 API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def influx_query(flux: str):
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    tables = client.query_api().query(flux)
    client.close()
    return tables


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/metrics/latest")
def get_latest_metrics():
    try:
        def last_val(measurement):
            flux = f'''
            from(bucket:"{INFLUX_BUCKET}")
              |> range(start: -7d)
              |> filter(fn:(r) => r._measurement == "{measurement}" and r._field == "value")
              |> last()
            '''
            tables = influx_query(flux)
            for t in tables:
                for r in t.records:
                    return r.get_value()
            return None

        return {
            "oil_price_usd":  last_val("oil_price"),
            "bdi_index":      last_val("bdi_index"),
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/metrics/extras")
def get_extras():
    """回傳 BDRY ETF 等補充指標的最新值"""
    try:
        def last_close(source_tag: str):
            flux = f'''
            from(bucket:"{INFLUX_BUCKET}")
              |> range(start: -7d)
              |> filter(fn:(r) => r._measurement == "bdi_proxy_etf" and r["source"] == "{source_tag}" and r._field == "close")
              |> last()
            '''
            for t in influx_query(flux):
                for r in t.records:
                    return round(r.get_value(), 3)
            return None

        def last_stock(source_tag: str):
            flux = f'''
            from(bucket:"{INFLUX_BUCKET}")
              |> range(start: -7d)
              |> filter(fn:(r) => r["source"] == "{source_tag}" and r._field == "close")
              |> last()
            '''
            for t in influx_query(flux):
                for r in t.records:
                    return round(r.get_value(), 2)
            return None

        return {
            "bdry_etf":  last_close("bdry"),
            "zim_stock": last_stock("zim"),
            "sblk_stock": last_stock("star_bulk"),
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/metrics/history")
def get_history(days: int = 30):
    try:
        result = {"oil": [], "bdi": [], "shipping_stocks": []}

        # 油價（WTI）
        flux_oil = f'''
        from(bucket:"{INFLUX_BUCKET}")
          |> range(start: -{days}d)
          |> filter(fn:(r) => r._measurement == "oil_price" and r._field == "value")
          |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)
        '''
        for t in influx_query(flux_oil):
            for r in t.records:
                result["oil"].append({
                    "time":  r.get_time().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "value": round(r.get_value(), 2) if r.get_value() else None,
                })

        # BDI 估算（來自 bdi_index measurement）
        flux_bdi = f'''
        from(bucket:"{INFLUX_BUCKET}")
          |> range(start: -{days}d)
          |> filter(fn:(r) => r._measurement == "bdi_index" and r._field == "value")
          |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)
        '''
        for t in influx_query(flux_bdi):
            for r in t.records:
                result["bdi"].append({
                    "time":  r.get_time().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "value": round(r.get_value(), 0) if r.get_value() else None,
                })

        # ZIM 航運股（代表貨櫃市場景氣）
        flux_zim = f'''
        from(bucket:"{INFLUX_BUCKET}")
          |> range(start: -{days}d)
          |> filter(fn:(r) => r["source"] == "zim" and r._field == "close")
          |> aggregateWindow(every: 1d, fn: mean, createEmpty: false)
        '''
        for t in influx_query(flux_zim):
            for r in t.records:
                result["shipping_stocks"].append({
                    "time":  r.get_time().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "value": round(r.get_value(), 2) if r.get_value() else None,
                })

        return result
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/news/latest")
def get_latest_news():
    try:
        query = json.dumps({
            "query": {"match_all": {}},
            "sort": [{"published": {"order": "desc"}}],
            "size": 10,
        }).encode()
        req = urllib.request.Request(
            f"{ES_HOST}/{ES_INDEX}/_search",
            data=query, headers={"Content-Type": "application/json"}, method="POST",
        )
        resp = json.loads(urllib.request.urlopen(req).read())
        return [h["_source"] for h in resp["hits"]["hits"]]
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/sentiment/summary")
def get_sentiment_summary():
    try:
        query = json.dumps({
            "size": 0,
            "aggs": {
                "by_sentiment": {
                    "terms": {"field": "sentiment"},
                    "aggs": {"avg_score": {"avg": {"field": "score"}}},
                }
            },
        }).encode()
        req = urllib.request.Request(
            f"{ES_HOST}/{ES_INDEX}/_search",
            data=query, headers={"Content-Type": "application/json"}, method="POST",
        )
        resp = json.loads(urllib.request.urlopen(req).read())
        buckets = resp["aggregations"]["by_sentiment"]["buckets"]
        return {b["key"]: {"count": b["doc_count"], "avg_score": round(b["avg_score"]["value"] or 0, 3)}
                for b in buckets}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


class PredictionRequest(BaseModel):
    oil_price: float
    bdi_index: float
    sentiment_score: float
    horizon_days: int = 7


@app.post("/api/predict")
def predict_freight_rate(req: PredictionRequest):
    base_rate        = 2200
    oil_effect       = (req.oil_price - 80) * 8.5
    bdi_effect       = (req.bdi_index - 1800) * 0.4
    sentiment_effect = req.sentiment_score * 150
    predicted        = base_rate + oil_effect + bdi_effect + sentiment_effect
    confidence       = max(0.55, min(0.92, 0.75 + abs(req.sentiment_score) * 0.1))
    return {
        "predicted_rate_usd_per_teu": round(predicted, 0),
        "confidence": round(confidence, 3),
        "horizon_days": req.horizon_days,
        "components": {
            "base_rate":            base_rate,
            "oil_contribution":     round(oil_effect, 1),
            "bdi_contribution":     round(bdi_effect, 1),
            "sentiment_contribution": round(sentiment_effect, 1),
        },
    }
