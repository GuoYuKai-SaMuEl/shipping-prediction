"""
真實航運新聞接入器
來源：Google News RSS、Splash247、The Loadstar、Hellenic Shipping News
將新聞寫入 Elasticsearch，並附上規則引擎情緒分析結果
"""
import hashlib
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.processing.models.sentiment import analyze_sentiment

ES_HOST  = "http://localhost:9200"
ES_INDEX = "shipping-news-index"

RSS_FEEDS = [
    {
        "url":    "https://news.google.com/rss/search?q=shipping+freight+rate+container+bulk&hl=en&gl=US&ceid=US:en",
        "source": "Google News",
        "limit":  15,
    },
    {
        "url":    "https://splash247.com/feed/",
        "source": "Splash247",
        "limit":  10,
    },
    {
        "url":    "https://theloadstar.com/feed/",
        "source": "The Loadstar",
        "limit":  10,
    },
    {
        "url":    "https://www.hellenicshippingnews.com/feed/",
        "source": "Hellenic Shipping News",
        "limit":  10,
    },
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ShippingBot/1.0; +https://github.com/GuoYuKai-SaMuEl/shipping-prediction)",
}


def _strip_html(text: str) -> str:
    import re
    text = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(text).strip()


def fetch_rss(feed: dict) -> list[dict]:
    try:
        req  = urllib.request.Request(feed["url"], headers=HEADERS)
        xml  = urllib.request.urlopen(req, timeout=10).read()
        root = ET.fromstring(xml)
        ns   = {"atom": "http://www.w3.org/2005/Atom"}

        articles = []
        for item in root.iter("item"):
            title   = _strip_html(item.findtext("title", ""))
            desc    = _strip_html(item.findtext("description", ""))
            link    = item.findtext("link", "")
            pub     = item.findtext("pubDate", datetime.now(timezone.utc).isoformat())
            if not title:
                continue
            articles.append({
                "title":     title,
                "content":   desc[:1000],
                "url":       link,
                "source":    feed["source"],
                "published": pub,
            })
            if len(articles) >= feed["limit"]:
                break
        return articles
    except Exception as e:
        print(f"  ✗ {feed['source']}: {e}")
        return []


def enrich_with_sentiment(articles: list[dict]) -> list[dict]:
    for a in articles:
        text = f"{a['title']} {a['content']}"
        label, score = analyze_sentiment(text)
        a["sentiment"] = label
        a["score"]     = round(score, 4)
    return articles


def index_to_es(articles: list[dict]):
    import json
    now = datetime.now(timezone.utc).isoformat()
    ok  = 0
    for a in articles:
        a["indexed_at"] = now
        doc_id = hashlib.md5(a["title"].encode()).hexdigest()[:16]
        data   = json.dumps(a).encode()
        req = urllib.request.Request(
            f"{ES_HOST}/{ES_INDEX}/_doc/{doc_id}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="PUT",
        )
        try:
            urllib.request.urlopen(req, timeout=8)
            ok += 1
        except Exception as e:
            print(f"    ES 寫入失敗：{e}")
    return ok


def ensure_index():
    import json
    mapping = json.dumps({
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": {"properties": {
            "title":      {"type": "text",    "analyzer": "english"},
            "content":    {"type": "text",    "analyzer": "english"},
            "sentiment":  {"type": "keyword"},
            "score":      {"type": "float"},
            "source":     {"type": "keyword"},
            "url":        {"type": "keyword"},
            "published":  {"type": "text"},
            "indexed_at": {"type": "date"},
        }},
    }).encode()
    req = urllib.request.Request(
        f"{ES_HOST}/{ES_INDEX}",
        data=mapping, headers={"Content-Type": "application/json"}, method="PUT",
    )
    try:
        urllib.request.urlopen(req, timeout=8)
    except Exception:
        pass  # 已存在則忽略


def run(interval: int = 600):
    ensure_index()
    while True:
        print(f"\n[News] {datetime.now():%Y-%m-%d %H:%M:%S} 開始抓取...")
        total = 0
        for feed in RSS_FEEDS:
            articles = fetch_rss(feed)
            if articles:
                enrich_with_sentiment(articles)
                ok = index_to_es(articles)
                print(f"  ✓ {feed['source']:30s} {ok}/{len(articles)} 篇已寫入（負:{sum(1 for a in articles if a['sentiment']=='negative')} 正:{sum(1 for a in articles if a['sentiment']=='positive')}）")
                total += ok
        print(f"  → 本次共寫入 {total} 篇新聞")
        if interval == 0:
            break
        time.sleep(interval)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--once",     action="store_true", help="只跑一次不循環")
    p.add_argument("--interval", type=int, default=600, help="循環間隔秒數")
    args = p.parse_args()
    run(interval=0 if args.once else args.interval)
