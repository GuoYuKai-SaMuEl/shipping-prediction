import json
import os
from datetime import datetime, timezone
from kafka import KafkaProducer, KafkaConsumer
from kafka.errors import KafkaError


def get_producer(broker: str = None) -> KafkaProducer:
    broker = broker or os.getenv("KAFKA_BROKER", "localhost:9092")
    return KafkaProducer(
        bootstrap_servers=[broker],
        value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8") if k else None,
        acks="all",
        retries=3,
    )


def get_consumer(topic: str, group_id: str, broker: str = None) -> KafkaConsumer:
    broker = broker or os.getenv("KAFKA_BROKER", "localhost:9092")
    return KafkaConsumer(
        topic,
        bootstrap_servers=[broker],
        group_id=group_id,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )


def send_message(producer: KafkaProducer, topic: str, key: str, payload: dict):
    payload["ingested_at"] = datetime.now(timezone.utc).isoformat()
    future = producer.send(topic, key=key, value=payload)
    try:
        record_metadata = future.get(timeout=10)
        return {
            "topic": record_metadata.topic,
            "partition": record_metadata.partition,
            "offset": record_metadata.offset,
        }
    except KafkaError as e:
        raise RuntimeError(f"Kafka 發送失敗: {e}") from e
