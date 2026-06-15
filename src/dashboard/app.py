"""
Streamlit Dashboard：運價預測曲線 & 壓力測試模擬器
"""
import requests
import streamlit as st

API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="海運運價預測儀表板",
    page_icon="🚢",
    layout="wide",
)

st.title("🚢 多源大數據海運運價即時預測系統")
st.markdown("---")

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("📊 即時指標")
    try:
        metrics = requests.get(f"{API_BASE}/api/metrics/latest", timeout=3).json()
        st.metric("WTI 原油 (USD/桶)", f"${metrics.get('oil_price_usd', 'N/A')}")
        st.metric("波羅的海乾散貨指數 (BDI)", metrics.get("bdi_index", "N/A"))
    except Exception:
        st.warning("⚠️ 無法連接後端 API")

with col2:
    st.subheader("💬 市場情緒")
    try:
        sentiment = requests.get(f"{API_BASE}/api/sentiment/summary", timeout=3).json()
        for label, data in sentiment.items():
            st.metric(f"{label.upper()} 新聞", f"{data['count']} 篇",
                      delta=f"avg score: {data['avg_score']:.3f}" if data['avg_score'] else None)
    except Exception:
        st.info("情緒數據載入中...")

with col3:
    st.subheader("🔮 壓力測試模擬")
    oil_input = st.slider("油價情境 (USD/桶)", 50.0, 150.0, 82.5, 0.5)
    bdi_input = st.slider("BDI 情境", 500, 4000, 1850, 50)
    sentiment_input = st.slider("市場情緒分數", -1.0, 1.0, 0.0, 0.05)

    if st.button("執行預測", type="primary"):
        try:
            resp = requests.post(f"{API_BASE}/api/predict", json={
                "oil_price": oil_input,
                "bdi_index": bdi_input,
                "sentiment_score": sentiment_input,
                "horizon_days": 7,
            }, timeout=5).json()
            st.success(f"**預測運價：USD {resp['predicted_rate_usd_per_teu']:,.0f} / TEU**")
            st.json(resp["components"])
            st.caption(f"信心度：{resp['confidence']:.1%}")
        except Exception as e:
            st.error(f"預測失敗：{e}")

st.markdown("---")
st.subheader("📰 最新航運新聞情緒")
try:
    news = requests.get(f"{API_BASE}/api/news/latest", timeout=3).json()
    for article in news[:5]:
        sentiment_color = {"positive": "🟢", "negative": "🔴", "neutral": "🟡"}.get(
            article.get("sentiment", "neutral"), "⚪")
        st.markdown(f"{sentiment_color} **{article.get('title', '')}**  "
                    f"(分數: `{article.get('score', 0):+.3f}`)")
except Exception:
    st.info("新聞數據載入中...")
