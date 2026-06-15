"""
新聞串流接入器：RSS Feed / Mock 新聞 → Kafka Topic: shipping-news
"""
import hashlib
import os
import time
from datetime import datetime, timezone

import feedparser

from src.utils.kafka_client import get_producer, send_message

TOPIC = os.getenv("KAFKA_TOPIC_NEWS", "shipping-news")

RSS_FEEDS = [
    "https://splash247.com/feed/",
    "https://www.seatrade-maritime.com/rss.xml",
]

MOCK_ARTICLES = [
    {"title": "Red Sea Crisis Escalates: Houthi Attacks Force Major Rerouting",
     "content": "Shipping companies are diverting vessels away from the Red Sea due to ongoing attacks. Freight rates on Asia-Europe routes have surged by 180% in the past two weeks.",
     "source": "mock_news"},
    {"title": "Oil Prices Rise on OPEC+ Supply Cut Extension",
     "content": "Crude oil prices climbed 2.3% after OPEC+ announced extension of production cuts through Q2. Bunker fuel costs expected to increase, pressuring shipping margins.",
     "source": "mock_news"},
    {"title": "Port Congestion in Shanghai Easing After Strike Resolution",
     "content": "Container backlogs at Shanghai port are clearing following resolution of labor disputes. Trans-Pacific spot rates expected to normalize within 3 weeks.",
     "source": "mock_news"},
]


def scrape_rss(url: str) -> list:
    feed = feedparser.parse(url)
    articles = []
    for entry in feed.entries[:5]:
        articles.append({
            "title": entry.get("title", ""),
            "content": entry.get("summary", ""),
            "source": url,
            "published": entry.get("published", datetime.now(timezone.utc).isoformat()),
            "url": entry.get("link", ""),
        })
    return articles


def run(interval: int = 300, mock: bool = False):
    producer = get_producer()
    print(f"[Ingestion] 新聞接入器啟動 — Topic: {TOPIC}, 間隔: {interval}s")

    while True:
        articles = []
        if mock:
            articles = MOCK_ARTICLES[:]
        else:
            for feed_url in RSS_FEEDS:
                try:
                    articles.extend(scrape_rss(feed_url))
                except Exception as e:
                    print(f"  ✗ RSS 抓取失敗 {feed_url}: {e}")

        for article in articles:
            article_id = hashlib.md5(article["title"].encode()).hexdigest()[:12]
            meta = send_message(producer, TOPIC, key=article_id, payload=article)
            print(f"  ✓ 新聞已送出: {article['title'][:60]}... → {meta}")

        time.sleep(interval)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=300)
    parser.add_argument("--mock", action="store_true", default=False)
    args = parser.parse_args()
    run(interval=args.interval, mock=args.mock)
