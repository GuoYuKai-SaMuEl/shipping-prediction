"""
Kafka 連通性驗證腳本
發送一條「油價上漲」Mock 事件，並從下游消費確認基礎設施連通
執行方式：python deploy/test_kafka_connectivity.py
"""
import json
import sys
import time
from datetime import datetime, timezone

BROKER = "localhost:9092"
TOPIC  = "shipping-metrics"


def test_produce_consume():
    try:
        from kafka import KafkaProducer, KafkaConsumer
        from kafka.errors import NoBrokersAvailable
    except ImportError:
        print("✗ 缺少 kafka-python，請先執行：pip install kafka-python")
        sys.exit(1)

    # ── 建立 Producer ─────────────────────────────────────────
    print(f"[1/3] 連線至 Kafka Broker: {BROKER}")
    try:
        producer = KafkaProducer(
            bootstrap_servers=[BROKER],
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            request_timeout_ms=10000,
        )
    except NoBrokersAvailable:
        print(f"  ✗ 無法連線到 {BROKER}，請確認 Kafka 容器已啟動")
        sys.exit(1)

    # ── 發送 Mock 事件 ────────────────────────────────────────
    payload = {
        "event": "oil_price_spike",
        "metric": "wti_crude_oil_usd",
        "value": 97.35,
        "change_pct": +18.2,
        "reason": "OPEC+ 宣布緊急減產，Red Sea 緊張局勢升溫",
        "unit": "USD/barrel",
        "source": "mock_stress_test",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    print(f"[2/3] 發送 Mock 事件：{payload['event']} → {payload['value']} USD")
    future = producer.send(TOPIC, key=b"wti_crude_oil_usd", value=payload)
    record = future.get(timeout=10)
    producer.flush()
    print(f"  ✓ 已送達 → topic={record.topic}, partition={record.partition}, offset={record.offset}")

    # ── 消費驗證 ──────────────────────────────────────────────
    print(f"[3/3] 從 Topic 消費驗證（timeout 15s）...")
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=[BROKER],
        auto_offset_reset="earliest",
        consumer_timeout_ms=15000,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        group_id="connectivity-test-group",
    )
    received = None
    for msg in consumer:
        data = msg.value
        if data.get("source") == "mock_stress_test":
            received = data
            break
    consumer.close()

    if received:
        print(f"  ✓ 消費成功！收到事件：{received['event']} = {received['value']} {received['unit']}")
        print(f"\n{'='*55}")
        print("  🟢 Kafka 基礎設施連通性驗證通過！")
        print(f"{'='*55}")
        return True
    else:
        print("  ✗ 未收到預期訊息，請檢查 Consumer 設定")
        return False


if __name__ == "__main__":
    success = test_produce_consume()
    sys.exit(0 if success else 1)
