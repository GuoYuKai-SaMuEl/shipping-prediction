"""
Flink-style 串流消費者：從 Kafka 消費新聞 → NLP 情緒分析 → 寫入 Elasticsearch + MinIO
在單機環境使用 Python thread-based 模擬 Flink Speed Layer 行為
"""
import json
import os
from datetime import datetime, timezone

from src.utils.kafka_client import get_consumer
from src.utils.es_client import index_news_article
from src.processing.models.sentiment import analyze_sentiment

TOPIC = os.getenv("KAFKA_TOPIC_NEWS", "shipping-news")
GROUP_ID = "nlp-sentiment-group"


def process_message(msg: dict) -> dict:
    sentiment, score = analyze_sentiment(
        text=f"{msg.get('title', '')} {msg.get('content', '')}"
    )
    return {
        **msg,
        "sentiment": sentiment,
        "score": score,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }


def run():
    consumer = get_consumer(TOPIC, GROUP_ID)
    print(f"[Processing] 情緒分析消費者啟動 — 監聽 Topic: {TOPIC}")

    for msg in consumer:
        try:
            article = msg.value
            enriched = process_message(article)
            result = index_news_article(enriched)
            print(f"  ✓ [{enriched['sentiment']:8s} {enriched['score']:+.3f}] "
                  f"{enriched.get('title', '')[:55]}... → ES:{result}")
        except Exception as e:
            print(f"  ✗ 處理失敗: {e}")


if __name__ == "__main__":
    run()
