"""
注入 Mock 數據到 InfluxDB 與 Elasticsearch，讓 Dashboard 有內容可顯示
"""
import random
from datetime import datetime, timezone, timedelta

# ── InfluxDB ──────────────────────────────────────────────────
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

INFLUX_URL   = "http://localhost:8086"
INFLUX_TOKEN = "shipping-super-secret-token"
INFLUX_ORG   = "shipping-org"
INFLUX_BUCKET = "shipping-metrics"

def seed_influxdb():
    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    write_api = client.write_api(write_options=SYNCHRONOUS)
    points = []
    now = datetime.now(timezone.utc)

    oil_base, bdi_base, rate_base = 82.5, 1850, 2200
    for i in range(90):
        ts = now - timedelta(days=89 - i)
        oil  = round(oil_base  + random.gauss(0, 3),   2)
        bdi  = int  (bdi_base  + random.gauss(0, 120))
        rate = round(rate_base + (oil - 82.5) * 9 + (bdi - 1850) * 0.35 + random.gauss(0, 80), 0)
        oil_base  = oil
        bdi_base  = bdi
        rate_base = rate

        points += [
            Point("oil_price").tag("source","eia").field("value", oil).time(ts),
            Point("bdi_index").tag("source","baltic").field("value", float(bdi)).time(ts),
            Point("freight_rate").tag("route","asia_europe").field("value_usd_teu", rate).time(ts),
        ]

    write_api.write(bucket=INFLUX_BUCKET, record=points)
    client.close()
    print(f"  ✓ InfluxDB：已寫入 {len(points)} 筆時序數據（90 天歷史）")

# ── Elasticsearch ─────────────────────────────────────────────
from elasticsearch import Elasticsearch

ES_HOST = "http://localhost:9200"
ES_INDEX = "shipping-news-index"

MOCK_NEWS = [
    {"title": "Red Sea Crisis: Freight Rates Surge 180% on Asia-Europe Routes",
     "content": "Houthi attacks force major shipping companies to reroute vessels around Cape of Good Hope, adding 14 days to transit times. Container spot rates have surged dramatically.",
     "sentiment": "negative", "score": -0.87, "source": "TradeWinds"},
    {"title": "OPEC+ Extends Production Cuts, Bunker Costs to Rise",
     "content": "Oil prices climbed 2.3% after OPEC+ announced extension of production cuts through Q2. Shipping companies expect bunker fuel surcharges to increase by 15-20%.",
     "sentiment": "negative", "score": -0.52, "source": "Lloyd's List"},
    {"title": "Port Congestion in Shanghai Easing After Strike Resolution",
     "content": "Container backlogs at Shanghai port are clearing following resolution of labor disputes. Trans-Pacific spot rates expected to normalize within three weeks.",
     "sentiment": "positive", "score": +0.64, "source": "Splash247"},
    {"title": "Baltic Dry Index Recovers as Grain Shipments Pick Up",
     "content": "BDI rose 8.2% this week driven by increased dry bulk demand from Brazil and Australia. Capesize rates leading the recovery with strong iron ore shipments.",
     "sentiment": "positive", "score": +0.71, "source": "Seatrade"},
    {"title": "Panama Canal Restrictions Lifted, Normalcy Returns",
     "content": "Water levels at Gatun Lake have recovered sufficiently to allow full draft transits. Panama Canal Authority confirms return to 36 daily crossings from next week.",
     "sentiment": "positive", "score": +0.58, "source": "Maritime Executive"},
    {"title": "Global Container Demand Weakens Amid Economic Uncertainty",
     "content": "Weak consumer spending in Europe and US leading to lower container bookings. Analysts warn of potential overcapacity as new vessel deliveries continue through 2024.",
     "sentiment": "negative", "score": -0.43, "source": "Alphaliner"},
    {"title": "Maersk Reports Strong Q1 on Spot Market Volatility",
     "content": "Shipping giant Maersk reported better-than-expected Q1 results, citing elevated spot rates from Red Sea disruptions. Long-term contract rates remain under pressure.",
     "sentiment": "neutral", "score": +0.12, "source": "Reuters"},
]

def seed_elasticsearch():
    import urllib.request, json as _json
    base = ES_HOST
    now  = datetime.now(timezone.utc)

    # 建立 index（ignore 400 = already exists）
    mapping = _json.dumps({
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": {"properties": {
            "title":      {"type": "text",    "analyzer": "english"},
            "content":    {"type": "text",    "analyzer": "english"},
            "sentiment":  {"type": "keyword"},
            "score":      {"type": "float"},
            "source":     {"type": "keyword"},
            "published":  {"type": "date"},
            "indexed_at": {"type": "date"},
        }},
    }).encode()
    req = urllib.request.Request(
        f"{base}/{ES_INDEX}", data=mapping,
        headers={"Content-Type": "application/json"}, method="PUT",
    )
    try:
        urllib.request.urlopen(req)
    except Exception:
        pass  # index 已存在時會丟 400，直接忽略

    # 寫入文章
    for i, article in enumerate(MOCK_NEWS):
        article["published"]  = (now - timedelta(hours=i*6)).isoformat()
        article["indexed_at"] = now.isoformat()
        data = _json.dumps(article).encode()
        req2 = urllib.request.Request(
            f"{base}/{ES_INDEX}/_doc", data=data,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        urllib.request.urlopen(req2)

    print(f"  ✓ Elasticsearch：已寫入 {len(MOCK_NEWS)} 篇新聞（含情緒標籤）")

if __name__ == "__main__":
    print("[Seed] 注入 Mock 數據...")
    seed_influxdb()
    seed_elasticsearch()
    print("[Seed] 完成！")
