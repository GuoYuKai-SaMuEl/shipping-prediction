"""
Streamlit Dashboard v2 — 海運運價預測系統
移除 BDI 估算，改用真實市場指標 + 真實新聞 + StockTwits 社群情緒
"""
import pandas as pd
import requests
import streamlit as st

API = "http://localhost:8000"

st.set_page_config(page_title="海運運價預測系統", page_icon="🚢", layout="wide")
st.title("🚢 多源大數據海運運價即時預測系統")
st.caption("數據來源：Yahoo Finance（WTI/航運股）× 真實新聞 RSS × StockTwits 社群情緒")
st.divider()

# ── 即時指標卡 ─────────────────────────────────────────────────
try:
    m    = requests.get(f"{API}/api/metrics/latest", timeout=5).json()
    oil  = m.get("oil_price_usd")
    bdry = m.get("bdry_etf")
    zim  = m.get("zim_stock")
    bulk = m.get("dry_bulk_composite")  # (SBLK+EGLE)/2
except Exception:
    oil = bdry = zim = bulk = None

c1, c2, c3, c4 = st.columns(4)
c1.metric("🛢️ WTI 原油",       f"${oil:.2f}/桶"  if oil  else "N/A", help="Yahoo Finance CL=F 期貨收盤")
c2.metric("🚢 BDRY ETF",       f"${bdry:.2f}"    if bdry else "N/A", help="Breakwave Dry Bulk ETF，追蹤散貨運費期貨")
c3.metric("📦 ZIM 貨櫃航運",   f"${zim:.2f}"     if zim  else "N/A", help="ZIM Integrated Shipping 股價，代表貨櫃市場景氣")
c4.metric("⚓ 散貨航運指數",    f"${bulk:.2f}"    if bulk else "N/A", help="SBLK + EGLE 平均股價，與乾散貨運費高度相關")

st.divider()

# ── 歷史走勢 ───────────────────────────────────────────────────
st.subheader("📈 歷史走勢（真實市場數據）")
days = st.slider("顯示天數", 7, 88, 30)

try:
    hist = requests.get(f"{API}/api/metrics/history", params={"days": days}, timeout=10).json()

    def chart(data, caption, color=None):
        if data:
            df = pd.DataFrame(data).set_index("time")
            df.index = pd.to_datetime(df.index, format="%Y-%m-%dT%H:%M:%SZ", utc=True)
            df = df.sort_index().dropna()
            st.line_chart(df["value"], height=260)
            st.caption(caption)
        else:
            st.info("暫無數據")

    t1, t2, t3, t4, t5 = st.tabs(["🛢️ WTI 原油", "🚢 BDRY ETF", "📦 ZIM", "⚓ SBLK", "⚓ EGLE"])
    with t1: chart(hist.get("oil",  []), "WTI 原油期貨收盤 (USD/桶)")
    with t2: chart(hist.get("bdry", []), "BDRY Dry Bulk ETF (USD) — 散貨運費趨勢代理指標")
    with t3: chart(hist.get("zim",  []), "ZIM 貨櫃航運股 (USD) — 貨櫃市場景氣指標")
    with t4: chart(hist.get("sblk", []), "SBLK Star Bulk (USD) — 散貨巨頭，BDI 高相關")
    with t5: chart(hist.get("egle", []), "EGLE Eagle Bulk (USD) — 散貨，BDI 高相關")

except Exception as e:
    st.error(f"無法載入歷史數據：{e}")

st.divider()

# ── 壓力測試 ───────────────────────────────────────────────────
st.subheader("⚡ 情境壓力測試模擬器")
ca, cb, cc = st.columns(3)
with ca: sim_oil  = st.slider("油價 (USD/桶)", 40.0, 150.0, float(oil)  if oil  else 80.0, 0.5)
with cb: sim_bulk = st.slider("散貨股指數 (USD)", 5.0, 80.0, float(bulk) if bulk else 27.0, 0.5,
                               help="SBLK+EGLE 均值，數值越高代表散貨市場越熱")
with cc: sim_sent = st.slider("市場情緒分數", -1.0, 1.0, 0.0, 0.05,
                               help="-1=極度悲觀  0=中性  +1=極度樂觀")

icon = "🔴" if sim_sent < -0.3 else "🟢" if sim_sent > 0.3 else "🟡"
st.caption(f"情緒設定：{icon} {sim_sent:+.2f}")

if st.button("執行預測", type="primary", use_container_width=True):
    try:
        r = requests.post(f"{API}/api/predict", json={
            "oil_price": sim_oil, "dry_bulk_index": sim_bulk,
            "sentiment_score": sim_sent, "horizon_days": 7,
        }, timeout=5).json()
        rate = r["predicted_rate_usd_per_teu"]
        c    = r["components"]
        st.success(f"### 預測運價：USD **{rate:,.0f}** / TEU　｜　信心度：{r['confidence']:.1%}")
        col_a, col_b, col_c, col_d = st.columns(4)
        col_a.metric("基準運價",     f"${c['base_rate']:,}")
        col_b.metric("油價貢獻",     f"${c['oil_contribution']:+,.0f}", delta_color="inverse")
        col_c.metric("散貨股貢獻",   f"${c['bulk_stock_contribution']:+,.0f}")
        col_d.metric("情緒貢獻",     f"${c['sentiment_contribution']:+,.0f}")
    except Exception as e:
        st.error(f"預測失敗：{e}")

st.divider()

# ── 雙欄：新聞情緒 + 社群情緒 ─────────────────────────────────
col_left, col_right = st.columns([3, 2])

with col_left:
    st.subheader("📰 最新航運新聞（真實 RSS）")

    # 來源篩選
    src_filter = st.multiselect(
        "篩選來源", ["Google News", "Splash247", "The Loadstar", "Hellenic Shipping News"],
        default=["Google News", "Splash247", "The Loadstar", "Hellenic Shipping News"],
    )
    try:
        news = requests.get(f"{API}/api/news/latest?size=20", timeout=5).json()
        filtered = [n for n in news if n.get("source") in src_filter] if src_filter else news
        for article in filtered[:12]:
            icon  = {"positive": "🟢", "negative": "🔴", "neutral": "🟡"}.get(article.get("sentiment", "neutral"), "⚪")
            score = article.get("score", 0)
            url   = article.get("url", "")
            title = article.get("title", "")
            link  = f"[{title}]({url})" if url else title
            st.markdown(
                f"{icon} {link}  \n"
                f"<small>📌 {article.get('source','')} ｜ 情緒：`{score:+.2f}`</small>",
                unsafe_allow_html=True,
            )
            st.write("")
    except Exception:
        st.info("新聞載入中...")

    # 新聞情緒摘要
    try:
        ns = requests.get(f"{API}/api/news/sentiment", timeout=5).json()
        total   = sum(ns.get("overall", {}).values())
        avg_sc  = ns.get("avg_score", 0)
        overall = ns.get("overall", {})
        pos_pct = overall.get("positive", 0) / total * 100 if total else 0
        neg_pct = overall.get("negative", 0) / total * 100 if total else 0

        mkt_icon = "🔴 偏空" if avg_sc < -0.1 else "🟢 偏多" if avg_sc > 0.1 else "🟡 中性"
        st.info(f"新聞情緒整體：{mkt_icon}（均分 {avg_sc:+.3f}）｜正面 {pos_pct:.0f}% / 負面 {neg_pct:.0f}%")
    except Exception:
        pass

with col_right:
    st.subheader("💬 StockTwits 社群情緒")
    st.caption("ZIM / SBLK / EGLE / BDRY 近 48 小時討論")

    try:
        comm = requests.get(f"{API}/api/community/sentiment", timeout=5).json()
        for ticker, data in comm.items():
            total = data.get("total", 0)
            if total == 0:
                continue
            avg   = data.get("avg_score", 0)
            pos   = data.get("positive", 0)
            neg   = data.get("negative", 0)
            bull_pct = pos / total if total else 0
            bear_pct = neg / total if total else 0
            icon  = "🟢" if avg > 0.1 else "🔴" if avg < -0.1 else "🟡"
            st.markdown(f"**{icon} ${ticker}** — {total} 則 ｜ 均分 `{avg:+.3f}`")
            cols = st.columns(2)
            cols[0].progress(bull_pct, text=f"看多 {pos} ({bull_pct:.0%})")
            cols[1].progress(bear_pct, text=f"看空 {neg} ({bear_pct:.0%})")
            st.write("")
    except Exception:
        st.info("社群情緒載入中...")

    # 最新貼文預覽
    st.markdown("---")
    st.caption("最新 StockTwits 討論（ZIM）")
    try:
        sel_ticker = st.selectbox("選擇股票", ["ZIM", "SBLK", "EGLE", "BDRY"], key="ticker_sel")
        posts = requests.get(f"{API}/api/community/recent?ticker={sel_ticker}&size=5", timeout=5).json()
        for p in posts:
            icon  = {"positive": "🟢", "negative": "🔴", "neutral": "🟡"}.get(p.get("sentiment"), "⚪")
            score = p.get("score", 0)
            st.markdown(f"{icon} `{score:+.2f}` {p.get('body','')[:120]}...")
            st.write("")
    except Exception:
        pass

# ── 數據來源聲明 ───────────────────────────────────────────────
st.divider()
with st.expander("📋 數據來源與說明"):
    st.markdown("""
| 指標 | 來源 | 說明 |
|------|------|------|
| WTI 原油 | Yahoo Finance `CL=F` | 期貨收盤，**真實數據**，每 5 分鐘更新 |
| BDRY ETF | Yahoo Finance `BDRY` | 散貨運費趨勢，**真實股價** |
| ZIM 股價 | Yahoo Finance `ZIM` | 貨櫃航運景氣，**真實股價** |
| SBLK / EGLE | Yahoo Finance | 散貨航運，與 BDI 高度相關，**真實股價** |
| 航運新聞 | Google News / Splash247 / The Loadstar / Hellenic Shipping News | **真實 RSS 新聞**，每 10 分鐘更新 |
| 社群情緒 | StockTwits | ZIM/SBLK/EGLE/BDRY 討論，**真實數據**，每 15 分鐘更新 |
    """)
