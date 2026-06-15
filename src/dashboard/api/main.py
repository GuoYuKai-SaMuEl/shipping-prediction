"""
FastAPI 後端：為 Streamlit Dashboard 提供預測結果與歷史數據 API
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.utils.influxdb_client import query_latest
from src.utils.es_client import search_news, get_client as get_es

app = FastAPI(title="海運運價預測 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/metrics/latest")
def get_latest_metrics():
    try:
        oil = query_latest("oil_price", "value", "-1h")
        bdi = query_latest("bdi_index", "value", "-1h")
        return {
            "oil_price_usd": oil[-1] if oil else None,
            "bdi_index": bdi[-1] if bdi else None,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/news/latest")
def get_latest_news(q: str = "shipping freight rate", size: int = 10):
    try:
        return search_news(q, size=size)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/sentiment/summary")
def get_sentiment_summary():
    es = get_es()
    resp = es.search(index="shipping-news-index", body={
        "size": 0,
        "aggs": {
            "by_sentiment": {
                "terms": {"field": "sentiment"},
                "aggs": {"avg_score": {"avg": {"field": "score"}}},
            }
        },
    })
    es.close()
    buckets = resp["aggregations"]["by_sentiment"]["buckets"]
    return {b["key"]: {"count": b["doc_count"], "avg_score": b["avg_score"]["value"]}
            for b in buckets}


class PredictionRequest(BaseModel):
    oil_price: float
    bdi_index: float
    sentiment_score: float
    horizon_days: int = 7


@app.post("/api/predict")
def predict_freight_rate(req: PredictionRequest):
    # 簡化線性組合模型（待替換為真實 ML 模型）
    base_rate = 2200
    oil_effect = (req.oil_price - 80) * 8.5
    bdi_effect = (req.bdi_index - 1800) * 0.4
    sentiment_effect = req.sentiment_score * 150
    predicted = base_rate + oil_effect + bdi_effect + sentiment_effect
    confidence = max(0.55, min(0.92, 0.75 + abs(req.sentiment_score) * 0.1))
    return {
        "predicted_rate_usd_per_teu": round(predicted, 2),
        "confidence": round(confidence, 3),
        "horizon_days": req.horizon_days,
        "components": {
            "base": base_rate,
            "oil_contribution": round(oil_effect, 2),
            "bdi_contribution": round(bdi_effect, 2),
            "sentiment_contribution": round(sentiment_effect, 2),
        },
    }
