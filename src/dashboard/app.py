"""
Streamlit Dashboard：海運運價預測 & 壓力測試模擬器
"""
import pandas as pd
import requests
import streamlit as st

API = "http://localhost:8000"

st.set_page_config(
    page_title="海運運價預測系統",
    page_icon="🚢",
    layout="wide",
)

st.title("🚢 多源大數據海運運價即時預測系統")
st.caption("數據來源：WTI 原油期貨 (Yahoo Finance) × BDI 估算 (BDRY ETF) × 新聞情緒分析")
st.divider()

# ── 即時指標卡 ─────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
try:
    m   = requests.get(f"{API}/api/metrics/latest", timeout=5).json()
    oil = m.get("oil_price_usd")
    bdi = m.get("bdi_index")
except Exception:
    oil, bdi = None, None

with col1:
    st.metric("🛢️ WTI 原油", f"${oil:.2f} / 桶" if oil else "N/A",
              help="來源：Yahoo Finance CL=F 期貨收盤價（即時）")
with col2:
    st.metric("📦 BDI 估算值", f"{bdi:,.0f} pts" if bdi else "N/A",
              help="⚠️ 由 BDRY ETF 價格換算估算（非官方 Baltic Exchange 數據），趨勢參考用")
with col3:
    try:
        extras = requests.get(f"{API}/api/metrics/extras", timeout=5).json()
        bdry   = extras.get("bdry_etf")
        st.metric("🚢 BDRY ETF", f"${bdry:.2f}" if bdry else "N/A",
                  help="Breakwave Dry Bulk Shipping ETF，追蹤 BDI 期貨")
    except Exception:
        st.metric("🚢 BDRY ETF", "N/A")
with col4:
    if oil and bdi:
        try:
            r = requests.post(f"{API}/api/predict", json={
                "oil_price": oil, "bdi_index": bdi,
                "sentiment_score": 0.0, "horizon_days": 7,
            }, timeout=5).json()
            st.metric("🔮 預測運價（7天）", f"${r['predicted_rate_usd_per_teu']:,.0f} / TEU")
        except Exception:
            st.metric("🔮 預測運價（7天）", "計算中...")
    else:
        st.metric("🔮 預測運價（7天）", "N/A")

st.divider()

# ── 歷史走勢圖 ─────────────────────────────────────────────────
st.subheader("📈 歷史走勢（真實市場數據）")
days = st.slider("顯示天數", 7, 88, 30)

try:
    hist = requests.get(f"{API}/api/metrics/history", params={"days": days}, timeout=10).json()

    tab1, tab2, tab3 = st.tabs(["🛢️ 原油價格 (WTI)", "📦 BDI 估算走勢", "🚢 航運股走勢"])

    def make_chart(data, caption):
        if data:
            df = pd.DataFrame(data).set_index("time")
            df.index = pd.to_datetime(df.index, format="%Y-%m-%dT%H:%M:%SZ", utc=True)
            df = df.sort_index()
            st.line_chart(df["value"], height=280)
            st.caption(caption)
        else:
            st.info("暫無數據")

    with tab1:
        make_chart(hist.get("oil", []), "WTI 原油期貨收盤價 (USD/桶)｜來源：Yahoo Finance CL=F")

    with tab2:
        make_chart(hist.get("bdi", []),
                   "BDI 估算值 (BDRY ETF × 140)｜⚠️ 趨勢方向具參考性，絕對數值為估算")

    with tab3:
        make_chart(hist.get("shipping_stocks", []),
                   "ZIM 貨櫃航運股價 (USD)｜代表貨櫃運力市場景氣")

except Exception as e:
    st.error(f"無法載入歷史數據：{e}")

st.divider()

# ── 壓力測試模擬器 ─────────────────────────────────────────────
st.subheader("⚡ 情境壓力測試模擬器")
st.caption("調整參數，模擬極端市況下的運價預測")

c1, c2, c3 = st.columns(3)
with c1:
    sim_oil  = st.slider("油價情境 (USD/桶)", 40.0, 150.0, float(oil) if oil else 80.0, 0.5)
with c2:
    sim_bdi  = st.slider("BDI 情境 (pts)", 300, 5000, int(bdi) if bdi else 1800, 50)
with c3:
    sim_sent = st.slider("市場情緒分數", -1.0, 1.0, 0.0, 0.05,
                         help="-1 = 極度悲觀（如紅海危機），+1 = 極度樂觀")

sentiment_label = "🔴 負面" if sim_sent < -0.3 else "🟢 正面" if sim_sent > 0.3 else "🟡 中性"
st.caption(f"當前情緒設定：{sentiment_label}（{sim_sent:+.2f}）")

if st.button("執行預測", type="primary", use_container_width=True):
    try:
        resp = requests.post(f"{API}/api/predict", json={
            "oil_price": sim_oil, "bdi_index": sim_bdi,
            "sentiment_score": sim_sent, "horizon_days": 7,
        }, timeout=5).json()

        rate       = resp["predicted_rate_usd_per_teu"]
        confidence = resp["confidence"]
        c_data     = resp["components"]

        st.success(f"### 預測運價：USD **{rate:,.0f}** / TEU　｜　信心度：{confidence:.1%}")
        col_a, col_b, col_c, col_d = st.columns(4)
        col_a.metric("基準運價",  f"${c_data['base_rate']:,}")
        col_b.metric("油價貢獻",  f"${c_data['oil_contribution']:+,.0f}", delta_color="inverse")
        col_c.metric("BDI 貢獻",  f"${c_data['bdi_contribution']:+,.0f}")
        col_d.metric("情緒貢獻",  f"${c_data['sentiment_contribution']:+,.0f}")
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
            pct  = data["count"] / total * 100 if total else 0
            st.progress(pct / 100, text=f"{icon} {label.upper()}：{data['count']} 篇 ({pct:.0f}%)")
    except Exception:
        st.info("情緒統計載入中...")

# ── 數據透明度聲明 ────────────────────────────────────────────
st.divider()
with st.expander("📋 數據來源說明"):
    st.markdown("""
| 指標 | 來源 | 說明 |
|------|------|------|
| WTI 原油價格 | Yahoo Finance `CL=F` | 即時期貨收盤價，**真實數據** |
| Brent 原油價格 | Yahoo Finance `BZ=F` | 即時期貨收盤價，**真實數據** |
| BDI (波羅的海乾散指數) | BDRY ETF × 140 換算 | ⚠️ **估算值**，官方 BDI 需付費訂閱 Baltic Exchange |
| ZIM / SBLK / EGLE | Yahoo Finance | 航運股即時股價，**真實數據** |
| 新聞情緒 | RSS + 規則引擎 | Mock 示範數據 |
    """)
