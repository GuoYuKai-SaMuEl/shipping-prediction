import os
from datetime import datetime, timezone
from elasticsearch import Elasticsearch


def get_client() -> Elasticsearch:
    return Elasticsearch(
        hosts=[os.getenv("ES_HOST", "http://localhost:9200")],
        request_timeout=30,
        max_retries=3,
        retry_on_timeout=True,
    )


def ensure_news_index(client: Elasticsearch, index: str):
    if not client.indices.exists(index=index):
        client.indices.create(index=index, body={
            "settings": {"number_of_shards": 1, "number_of_replicas": 0},
            "mappings": {
                "properties": {
                    "title":      {"type": "text",    "analyzer": "english"},
                    "content":    {"type": "text",    "analyzer": "english"},
                    "source":     {"type": "keyword"},
                    "sentiment":  {"type": "keyword"},
                    "score":      {"type": "float"},
                    "published":  {"type": "date"},
                    "indexed_at": {"type": "date"},
                }
            },
        })


def index_news_article(article: dict):
    client = get_client()
    index = os.getenv("ES_INDEX_NEWS", "shipping-news-index")
    ensure_news_index(client, index)
    article["indexed_at"] = datetime.now(timezone.utc).isoformat()
    resp = client.index(index=index, document=article)
    client.close()
    return resp["result"]


def search_news(query: str, size: int = 10) -> list:
    client = get_client()
    index = os.getenv("ES_INDEX_NEWS", "shipping-news-index")
    resp = client.search(index=index, body={
        "query": {"multi_match": {"query": query, "fields": ["title^2", "content"]}},
        "sort": [{"published": {"order": "desc"}}],
        "size": size,
    })
    client.close()
    return [hit["_source"] for hit in resp["hits"]["hits"]]
