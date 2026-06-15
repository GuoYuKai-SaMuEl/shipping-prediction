"""
Streamlit Dashboard：海運運價預測 & 壓力測試模擬器
"""
import requests
import streamlit as st

API = "http://localhost:8000"

st.set_page_config(
    page_title="海運運價預測系統",
    page_icon="🚢",
    layout="wide",
)

st.title("🚢 多源大數據海運運價即時預測系統")
st.caption("數據來源：油價（WTI）× 波羅的海乾散指數（BDI）× 新聞情緒分析")
st.divider()

# ── 即時指標卡 ─────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
try:
    m = requests.get(f"{API}/api/metrics/latest", timeout=5).json()
    oil = m.get("oil_price_usd")
    bdi = m.get("bdi_index")
except Exception:
    oil, bdi = None, None

with col1:
    st.metric("🛢️ WTI 原油價格", f"${oil:.2f} / 桶" if oil else "N/A")
with col2:
    st.metric("📦 波羅的海乾散指數 (BDI)", f"{bdi:,.0f} pts" if bdi else "N/A")
with col3:
    # 以當前指標做即時預測
    if oil and bdi:
        try:
            r = requests.post(f"{API}/api/predict", json={
                "oil_price": oil, "bdi_index": bdi,
                "sentiment_score": 0.0, "horizon_days": 7,
            }, timeout=5).json()
            predicted = r["predicted_rate_usd_per_teu"]
            st.metric("🔮 預測運價（7天）", f"${predicted:,.0f} / TEU")
        except Exception:
            st.metric("🔮 預測運價（7天）", "計算中...")
    else:
        st.metric("🔮 預測運價（7天）", "N/A")

st.divider()

# ── 歷史走勢圖 ─────────────────────────────────────────────────
st.subheader("📈 90 天歷史走勢")
days = st.slider("顯示天數", 7, 90, 30)

try:
    hist = requests.get(f"{API}/api/metrics/history", params={"days": days}, timeout=10).json()

    import pandas as pd

    tab1, tab2, tab3 = st.tabs(["原油價格", "BDI 指數", "歷史運價"])

    with tab1:
        if hist["oil"]:
            df = pd.DataFrame(hist["oil"]).set_index("time")
            df.index = pd.to_datetime(df.index)
            st.line_chart(df["value"], height=250)
            st.caption("WTI 原油 (USD/桶)")
        else:
            st.info("暫無數據")

    with tab2:
        if hist["bdi"]:
            df = pd.DataFrame(hist["bdi"]).set_index("time")
            df.index = pd.to_datetime(df.index)
            st.line_chart(df["value"], height=250)
            st.caption("波羅的海乾散貨指數 (BDI Points)")
        else:
            st.info("暫無數據")

    with tab3:
        if hist["rate"]:
            df = pd.DataFrame(hist["rate"]).set_index("time")
            df.index = pd.to_datetime(df.index)
            st.line_chart(df["value"], height=250)
            st.caption("亞歐航線貨櫃運價 (USD/TEU)")
        else:
            st.info("暫無數據")

except Exception as e:
    st.error(f"無法載入歷史數據：{e}")

st.divider()

# ── 壓力測試模擬器 ─────────────────────────────────────────────
st.subheader("⚡ 情境壓力測試模擬器")
st.caption("調整參數，模擬極端市況下的運價預測")

c1, c2, c3 = st.columns(3)
with c1:
    sim_oil = st.slider("油價情境 (USD/桶)", 40.0, 150.0, float(oil) if oil else 82.5, 0.5)
with c2:
    sim_bdi = st.slider("BDI 情境", 300, 5000, int(bdi) if bdi else 1850, 50)
with c3:
    sim_sent = st.slider("市場情緒分數", -1.0, 1.0, 0.0, 0.05,
                         help="-1 = 極度悲觀（紅海危機），+1 = 極度樂觀")

sentiment_label = "🔴 負面" if sim_sent < -0.3 else "🟢 正面" if sim_sent > 0.3 else "🟡 中性"
st.caption(f"當前情緒：{sentiment_label}（{sim_sent:+.2f}）")

if st.button("執行預測", type="primary", use_container_width=True):
    try:
        r = requests.post(f"{API}/api/predict", json={
            "oil_price": sim_oil, "bdi_index": sim_bdi,
            "sentiment_score": sim_sent, "horizon_days": 7,
        }, timeout=5).json()

        st.success(f"### 預測運價：USD **{r['predicted_rate_usd_per_teu']:,.0f}** / TEU　｜　信心度：{r['confidence']:.1%}")

        c = r["components"]
        col_a, col_b, col_c, col_d = st.columns(4)
        col_a.metric("基準運價",        f"${c['base_rate']:,}")
        col_b.metric("油價影響",         f"${c['oil_contribution']:+,.0f}",  delta_color="inverse")
        col_c.metric("BDI 影響",         f"${c['bdi_contribution']:+,.0f}")
        col_d.metric("情緒影響",         f"${c['sentiment_contribution']:+,.0f}")
    except Exception as e:
        st.error(f"預測失敗：{e}")

st.divider()

# ── 新聞情緒面板 ───────────────────────────────────────────────
st.subheader("📰 最新航運新聞情緒分析")

col_news, col_sent = st.columns([2, 1])

with col_news:
    try:
        news = requests.get(f"{API}/api/news/latest", timeout=5).json()
        for article in news:
            icon = {"positive": "🟢", "negative": "🔴", "neutral": "🟡"}.get(
                article.get("sentiment", "neutral"), "⚪")
            score = article.get("score", 0)
            st.markdown(
                f"{icon} **{article.get('title','')}**  \n"
                f"<small>來源：{article.get('source','')} ｜ 情緒分數：`{score:+.3f}`</small>",
                unsafe_allow_html=True,
            )
            st.write("")
    except Exception:
        st.info("新聞數據載入中...")

with col_sent:
    try:
        summary = requests.get(f"{API}/api/sentiment/summary", timeout=5).json()
        st.markdown("**情緒分佈**")
        total = sum(v["count"] for v in summary.values())
        for label, data in sorted(summary.items()):
            icon = {"positive": "🟢", "negative": "🔴", "neutral": "🟡"}.get(label, "⚪")
            pct = data["count"] / total * 100 if total else 0
            st.progress(pct / 100, text=f"{icon} {label.upper()}：{data['count']} 篇 ({pct:.0f}%)")
    except Exception:
        st.info("情緒統計載入中...")
