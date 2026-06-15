"""
時序數據接入器：油價 / BDI 運費指數 / 運量 → Kafka Topic: shipping-metrics
支援真實 API 與 Mock 兩種模式（透過 --mock 旗標切換）
"""
import argparse
import os
import random
import time
from datetime import datetime, timezone

import requests

from src.utils.kafka_client import get_producer, send_message

TOPIC = os.getenv("KAFKA_TOPIC_METRICS", "shipping-metrics")


def fetch_oil_price_mock() -> dict:
    base = 82.5
    return {
        "metric": "wti_crude_oil_usd",
        "value": round(base + random.uniform(-3.0, 3.0), 2),
        "unit": "USD/barrel",
        "source": "mock",
    }


def fetch_bdi_mock() -> dict:
    base = 1850
    return {
        "metric": "baltic_dry_index",
        "value": int(base + random.uniform(-120, 120)),
        "unit": "points",
        "source": "mock",
    }


def fetch_shipping_volume_mock() -> dict:
    return {
        "metric": "global_container_teu",
        "value": round(random.uniform(18.5, 22.0), 2),
        "unit": "million_teu",
        "source": "mock",
    }


def run(interval: int = 60, mock: bool = True):
    producer = get_producer()
    fetchers = [fetch_oil_price_mock, fetch_bdi_mock, fetch_shipping_volume_mock]
    print(f"[Ingestion] 時序接入器啟動 — Topic: {TOPIC}, 間隔: {interval}s")

    while True:
        for fetcher in fetchers:
            data = fetcher()
            data["timestamp"] = datetime.now(timezone.utc).isoformat()
            meta = send_message(producer, TOPIC, key=data["metric"], payload=data)
            print(f"  ✓ 已發送 {data['metric']}={data['value']} → {meta}")
        time.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--mock", action="store_true", default=True)
    args = parser.parse_args()
    run(interval=args.interval, mock=args.mock)
