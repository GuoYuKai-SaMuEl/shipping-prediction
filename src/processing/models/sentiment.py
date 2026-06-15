"""
情緒分析模型封裝
生產環境：載入 ProsusAI/finbert（金融領域 BERT）
輕量模式：使用關鍵字規則引擎（無 GPU 環境的後備方案）
"""
import os
import re

POSITIVE_KEYWORDS = [
    "easing", "resolut", "normaliz", "declin", "drop", "fall", "decrease",
    "recover", "improve", "clearing", "reopen", "stabiliz",
]
NEGATIVE_KEYWORDS = [
    "surge", "escalat", "crisis", "attack", "disrupt", "congestion", "delay",
    "strike", "sanction", "ban", "clos", "block", "war", "conflict", "reroute",
]

_transformer_pipeline = None


def _load_transformer():
    global _transformer_pipeline
    if _transformer_pipeline is None:
        try:
            from transformers import pipeline
            _transformer_pipeline = pipeline(
                "text-classification",
                model="ProsusAI/finbert",
                device=-1,
            )
        except Exception:
            _transformer_pipeline = "rule_based"
    return _transformer_pipeline


def _rule_based_sentiment(text: str) -> tuple[str, float]:
    text_lower = text.lower()
    pos = sum(1 for kw in POSITIVE_KEYWORDS if kw in text_lower)
    neg = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text_lower)
    if neg > pos:
        score = min(-0.3 - (neg - pos) * 0.1, -0.95)
        return "negative", score
    elif pos > neg:
        score = min(0.3 + (pos - neg) * 0.1, 0.95)
        return "positive", score
    return "neutral", 0.0


def analyze_sentiment(text: str, use_transformer: bool = False) -> tuple[str, float]:
    if use_transformer and os.getenv("USE_TRANSFORMER", "false").lower() == "true":
        pipe = _load_transformer()
        if pipe != "rule_based":
            result = pipe(text[:512])[0]
            label = result["label"].lower()
            score = result["score"] if label == "positive" else -result["score"]
            return label, round(score, 4)
    return _rule_based_sentiment(text)
