"""
社群情緒接入器 — StockTwits
監控航運相關股票（ZIM、SBLK、EGLE）的討論情緒
不需要 API Key，完全免費公開
"""
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.processing.models.sentiment import analyze_sentiment

ES_HOST        = "http://localhost:9200"
ES_INDEX_COMM  = "shipping-community-sentiment"

STOCKTWITS_TICKERS = {
    "ZIM":  "ZIM Integrated Shipping（貨櫃航運龍頭）",
    "SBLK": "Star Bulk Carriers（散貨，BDI 高相關）",
    "EGLE": "Eagle Bulk Shipping（散貨）",
    "BDRY": "Breakwave Dry Bulk ETF（BDI 代理）",
}

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ShippingBot/1.0)"}


def fetch_stocktwits(ticker: str, limit: int = 30) -> list[dict]:
    url = f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json?limit={limit}"
    try:
        req  = urllib.request.Request(url, headers=HEADERS)
        data = json.loads(urllib.request.urlopen(req, timeout=10).read())
        msgs = []
        for msg in data.get("messages", []):
            body     = msg.get("body", "")
            st_label = (msg.get("entities") or {}).get("sentiment") or {}
            # 優先用 StockTwits 自帶標籤，若無則用規則引擎
            if st_label.get("basic") in ("Bullish", "Bearish"):
                label = "positive" if st_label["basic"] == "Bullish" else "negative"
                score = 0.65 if label == "positive" else -0.65
            else:
                label, score = analyze_sentiment(body)
            msgs.append({
                "platform":   "StockTwits",
                "ticker":     ticker,
                "body":       body[:500],
                "sentiment":  label,
                "score":      round(score, 4),
                "likes":      msg.get("likes", {}).get("total", 0),
                "created_at": msg.get("created_at", datetime.now(timezone.utc).isoformat()),
                "msg_id":     str(msg.get("id", "")),
            })
        return msgs
    except Exception as e:
        print(f"  ✗ StockTwits {ticker}: {e}")
        return []


def ensure_index():
    mapping = json.dumps({
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": {"properties": {
            "platform":   {"type": "keyword"},
            "ticker":     {"type": "keyword"},
            "body":       {"type": "text", "analyzer": "english"},
            "sentiment":  {"type": "keyword"},
            "score":      {"type": "float"},
            "likes":      {"type": "integer"},
            "created_at": {"type": "text"},
            "indexed_at": {"type": "date"},
            "msg_id":     {"type": "keyword"},
        }},
    }).encode()
    req = urllib.request.Request(
        f"{ES_HOST}/{ES_INDEX_COMM}",
        data=mapping, headers={"Content-Type": "application/json"}, method="PUT",
    )
    try:
        urllib.request.urlopen(req, timeout=8)
    except Exception:
        pass


def index_messages(messages: list[dict]):
    now = datetime.now(timezone.utc).isoformat()
    ok  = 0
    for msg in messages:
        msg["indexed_at"] = now
        doc_id = f"{msg['platform']}_{msg['msg_id']}"
        data   = json.dumps(msg).encode()
        req    = urllib.request.Request(
            f"{ES_HOST}/{ES_INDEX_COMM}/_doc/{doc_id}",
            data=data, headers={"Content-Type": "application/json"}, method="PUT",
        )
        try:
            urllib.request.urlopen(req, timeout=8)
            ok += 1
        except Exception:
            pass
    return ok


def get_community_summary() -> dict:
    """查詢各 ticker 情緒聚合（供 API 呼叫）"""
    import urllib.request, json
    result = {}
    for ticker in STOCKTWITS_TICKERS:
        query = json.dumps({
            "size": 0,
            "query": {"bool": {"must": [
                {"term": {"ticker": ticker}},
                {"range": {"indexed_at": {"gte": "now-24h"}}},
            ]}},
            "aggs": {
                "sentiment_dist": {"terms": {"field": "sentiment"}},
                "avg_score":      {"avg":   {"field": "score"}},
            },
        }).encode()
        req = urllib.request.Request(
            f"{ES_HOST}/{ES_INDEX_COMM}/_search",
            data=query, headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            resp     = json.loads(urllib.request.urlopen(req, timeout=8).read())
            buckets  = resp["aggregations"]["sentiment_dist"]["buckets"]
            avg_sc   = resp["aggregations"]["avg_score"]["value"] or 0
            total    = sum(b["doc_count"] for b in buckets)
            dist     = {b["key"]: b["doc_count"] for b in buckets}
            result[ticker] = {
                "total":       total,
                "avg_score":   round(avg_sc, 3),
                "positive":    dist.get("positive", 0),
                "negative":    dist.get("negative", 0),
                "neutral":     dist.get("neutral",  0),
                "description": STOCKTWITS_TICKERS[ticker],
            }
        except Exception:
            result[ticker] = {"total": 0, "avg_score": 0}
    return result


def run(interval: int = 900):
    ensure_index()
    while True:
        print(f"\n[Community] {datetime.now():%Y-%m-%d %H:%M:%S} 抓取 StockTwits...")
        for ticker, desc in STOCKTWITS_TICKERS.items():
            msgs = fetch_stocktwits(ticker, limit=30)
            if msgs:
                ok  = index_messages(msgs)
                pos = sum(1 for m in msgs if m["sentiment"] == "positive")
                neg = sum(1 for m in msgs if m["sentiment"] == "negative")
                avg = sum(m["score"] for m in msgs) / len(msgs)
                print(f"  {ticker:5s} {desc:30s} {ok:2d} 則｜正:{pos} 負:{neg} 均分:{avg:+.2f}")
        if interval == 0:
            break
        time.sleep(interval)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--once",     action="store_true")
    p.add_argument("--interval", type=int, default=900)
    args = p.parse_args()
    run(interval=0 if args.once else args.interval)
