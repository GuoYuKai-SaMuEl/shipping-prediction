"""
Streamlit Dashboard v3 — 海運運價預測系統
深色科技主題 + Plotly 圖表 + 多航線漲跌預測信號
"""
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

API = "http://localhost:8000"

st.set_page_config(
    page_title="ShipPulse — 海運運價預測系統",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── 全域 CSS（強化科技感） ─────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@400;600;700&display=swap');

  html, body, [class*="css"] { font-family: 'Rajdhani', 'Share Tech Mono', monospace; }

  /* 頂部 header 線條 */
  .main > div:first-child { border-top: 2px solid #00d4ff; }

  /* 指標卡科技感 */
  [data-testid="metric-container"] {
    background: linear-gradient(135deg, #0a1628 0%, #0d1e38 100%);
    border: 1px solid #1a3a5c;
    border-left: 3px solid #00d4ff;
    border-radius: 6px;
    padding: 12px 16px;
  }
  [data-testid="metric-container"]:hover { border-left-color: #00ffaa; }

  /* 預測卡 */
  .predict-card {
    background: linear-gradient(135deg, #0a1628 0%, #0c1830 100%);
    border: 1px solid #1a3a5c;
    border-radius: 8px;
    padding: 14px 18px;
    margin: 4px 0;
    transition: all 0.2s ease;
  }
  .predict-card:hover { border-color: #00d4ff; box-shadow: 0 0 12px rgba(0,212,255,0.15); }

  .signal-up3   { color:#ff4d4d; font-size:1.6rem; font-weight:700; }
  .signal-up2   { color:#ff8c42; font-size:1.4rem; font-weight:700; }
  .signal-up1   { color:#ffd166; font-size:1.2rem; font-weight:600; }
  .signal-flat  { color:#8899aa; font-size:1.2rem; font-weight:500; }
  .signal-down1 { color:#90e0ef; font-size:1.2rem; font-weight:600; }
  .signal-down2 { color:#48cae4; font-size:1.4rem; font-weight:700; }
  .signal-down3 { color:#00b4d8; font-size:1.6rem; font-weight:700; }

  .mag-bar { display:inline-block; height:8px; border-radius:4px; margin-right:4px; }
  .divider-glow { border:0; height:1px; background: linear-gradient(90deg,transparent,#00d4ff,transparent); margin:16px 0; }
  .section-title { font-family:'Rajdhani',sans-serif; font-size:1.1rem; color:#00d4ff; letter-spacing:3px; text-transform:uppercase; margin-bottom:8px; }
  .ticker-badge { background:#0d1e38; border:1px solid #1a3a5c; border-radius:4px; padding:2px 8px; font-size:0.8rem; color:#00d4ff; }
</style>
""", unsafe_allow_html=True)

# ── 頁首 ──────────────────────────────────────────────────────
st.markdown('<p class="section-title">⬡ ShipPulse — 多源大數據海運運價即時預測系統</p>', unsafe_allow_html=True)
st.markdown('<hr class="divider-glow">', unsafe_allow_html=True)

# ── 即時指標 ──────────────────────────────────────────────────
try:
    m    = requests.get(f"{API}/api/metrics/latest", timeout=5).json()
    oil  = m.get("oil_price_usd")
    bdry = m.get("bdry_etf")
    zim  = m.get("zim_stock")
    bulk = m.get("dry_bulk_composite")
except Exception:
    oil = bdry = zim = bulk = None

c1, c2, c3, c4 = st.columns(4)
c1.metric("🛢️  WTI CRUDE",       f"${oil:.2f}"  if oil  else "—", help="Yahoo Finance CL=F 即時期貨")
c2.metric("🚢  BDRY ETF",         f"${bdry:.3f}" if bdry else "—", help="Breakwave Dry Bulk ETF")
c3.metric("📦  ZIM SHIPPING",     f"${zim:.2f}"  if zim  else "—", help="ZIM 貨櫃航運股")
c4.metric("⚓  DRY BULK INDEX",   f"${bulk:.2f}" if bulk else "—", help="(SBLK+EGLE)/2 散貨綜合")

st.markdown('<hr class="divider-glow">', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
#  主視覺：多航線漲跌預測
# ══════════════════════════════════════════════════════════════
st.markdown('<p class="section-title">◈ 7-Day Freight Rate Outlook</p>', unsafe_allow_html=True)

ARROW = {
    ("up",   3): ("↑↑↑", "signal-up3",   "顯著上漲",  "#ff4d4d"),
    ("up",   2): ("↑↑",  "signal-up2",   "中等上漲",  "#ff8c42"),
    ("up",   1): ("↑",   "signal-up1",   "輕微上漲",  "#ffd166"),
    ("flat", 1): ("→",   "signal-flat",  "橫盤整理",  "#8899aa"),
    ("flat", 2): ("→",   "signal-flat",  "橫盤整理",  "#8899aa"),
    ("flat", 3): ("→",   "signal-flat",  "橫盤整理",  "#8899aa"),
    ("down", 1): ("↓",   "signal-down1", "輕微下跌",  "#90e0ef"),
    ("down", 2): ("↓↓",  "signal-down2", "中等下跌",  "#48cae4"),
    ("down", 3): ("↓↓↓", "signal-down3", "顯著下跌",  "#00b4d8"),
}

try:
    routes = requests.get(f"{API}/api/predict/routes", timeout=8).json()

    container_routes = {k: v for k, v in routes.items() if v["type"] == "container"}
    bulk_routes      = {k: v for k, v in routes.items() if v["type"] == "dry_bulk"}

    def render_route_card(key, r):
        d, mag = r["direction"], r["magnitude"]
        arrow, css_cls, label, color = ARROW.get((d, mag), ("→", "signal-flat", "橫盤", "#8899aa"))
        score  = r["score"]
        drv    = r["drivers"]

        # 幅度條（mag 1-3 填色）
        bars = ""
        for i in range(1, 4):
            filled = "#00d4ff" if i <= mag and d == "up" else \
                     "#00b4d8" if i <= mag and d == "down" else "#1a3a5c"
            bars += f'<span class="mag-bar" style="width:18px;background:{filled};"></span>'

        driver_text = (
            f"油:{drv['oil_trend']:+.1%} &nbsp; "
            f"散貨股:{drv['bulk_trend']:+.1%} &nbsp; "
            f"ZIM:{drv['zim_trend']:+.1%} &nbsp; "
            f"新聞:{drv['disruption']:+.2f}"
        )

        st.markdown(f"""
        <div class="predict-card">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
              <span style="font-size:0.75rem;color:#5588aa;letter-spacing:2px;">{r['name_en'].upper()}</span><br>
              <span style="font-size:1.05rem;font-weight:700;color:#c9d8f0;">{r['name']}</span>
              <span style="font-size:0.78rem;color:#445566;margin-left:8px;">{r['desc']}</span>
            </div>
            <div style="text-align:right;">
              <span class="{css_cls}">{arrow}</span>
              <span style="font-size:0.85rem;color:#8899aa;margin-left:8px;">{label}</span><br>
              <div style="margin-top:4px;">{bars}</div>
            </div>
          </div>
          <div style="margin-top:8px;font-size:0.72rem;color:#445566;">{driver_text}</div>
        </div>
        """, unsafe_allow_html=True)

    col_con, col_bulk = st.columns(2)
    with col_con:
        st.markdown('<span style="font-size:0.75rem;color:#5588aa;letter-spacing:2px;">CONTAINER SHIPPING</span>', unsafe_allow_html=True)
        for k, r in container_routes.items():
            render_route_card(k, r)
    with col_bulk:
        st.markdown('<span style="font-size:0.75rem;color:#5588aa;letter-spacing:2px;">DRY BULK SHIPPING</span>', unsafe_allow_html=True)
        for k, r in bulk_routes.items():
            render_route_card(k, r)

except Exception as e:
    st.error(f"預測服務暫時不可用：{e}")

st.markdown('<hr class="divider-glow">', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
#  歷史走勢（Plotly）
# ══════════════════════════════════════════════════════════════
st.markdown('<p class="section-title">◈ Market History</p>', unsafe_allow_html=True)
days = st.slider("顯示天數", 7, 88, 30, label_visibility="collapsed")

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(5,13,26,0.8)",
    font=dict(family="Share Tech Mono, monospace", color="#8899aa", size=11),
    margin=dict(l=0, r=0, t=28, b=0),
    height=220,
    showlegend=False,
    xaxis=dict(
        showgrid=True, gridcolor="#0d1e38", gridwidth=1,
        zeroline=False, fixedrange=True,
        tickfont=dict(size=9),
    ),
    yaxis=dict(
        showgrid=True, gridcolor="#0d1e38", gridwidth=1,
        zeroline=False, fixedrange=True,
        autorange=True,
        tickfont=dict(size=9),
    ),
)
CHART_CFG = dict(scrollZoom=False, displayModeBar=False)


def make_plotly(data, title, color="#00d4ff", fill_color="rgba(0,212,255,0.06)"):
    if not data:
        return None
    df = pd.DataFrame(data)
    df["time"] = pd.to_datetime(df["time"], format="%Y-%m-%dT%H:%M:%SZ", utc=True)
    df = df.sort_values("time").dropna(subset=["value"])

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["time"], y=df["value"],
        mode="lines",
        line=dict(color=color, width=1.8),
        fill="tozeroy", fillcolor=fill_color,
        hovertemplate="%{x|%m/%d}<br><b>%{y:.2f}</b><extra></extra>",
    ))
    layout = {**PLOTLY_LAYOUT, "title": dict(text=title, font=dict(size=11, color="#5588aa"), x=0)}
    fig.update_layout(**layout)
    return fig


try:
    hist = requests.get(f"{API}/api/metrics/history", params={"days": days}, timeout=10).json()

    t1, t2, t3, t4, t5 = st.tabs(["WTI Crude", "BDRY ETF", "ZIM", "SBLK", "EGLE"])

    specs = [
        ("oil",  "WTI Crude Oil (USD/bbl)",  "#ff8c42", "rgba(255,140,66,0.06)", t1),
        ("bdry", "BDRY Dry Bulk ETF (USD)",   "#00d4ff", "rgba(0,212,255,0.06)",  t2),
        ("zim",  "ZIM Container Shipping",    "#00ffaa", "rgba(0,255,170,0.06)",  t3),
        ("sblk", "SBLK Star Bulk (USD)",       "#a78bfa", "rgba(167,139,250,0.06)", t4),
        ("egle", "EGLE Eagle Bulk (USD)",      "#f472b6", "rgba(244,114,182,0.06)", t5),
    ]
    for key, title, color, fill, tab in specs:
        with tab:
            fig = make_plotly(hist.get(key, []), title, color, fill)
            if fig:
                st.plotly_chart(fig, use_container_width=True, config=CHART_CFG)
            else:
                st.info("暫無數據")

except Exception as e:
    st.error(f"圖表載入失敗：{e}")

st.markdown('<hr class="divider-glow">', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
#  壓力測試模擬器
# ══════════════════════════════════════════════════════════════
st.markdown('<p class="section-title">◈ Scenario Simulator</p>', unsafe_allow_html=True)

ca, cb, cc = st.columns(3)
with ca: sim_oil  = st.slider("Oil Price (USD/bbl)", 40.0, 150.0, float(oil)  if oil  else 80.0, 0.5)
with cb: sim_bulk = st.slider("Dry Bulk Index (USD)", 5.0, 80.0,  float(bulk) if bulk else 27.0, 0.5)
with cc: sim_sent = st.slider("Sentiment Score",     -1.0, 1.0, 0.0, 0.05)

if st.button("▶  RUN PREDICTION", type="primary", use_container_width=True):
    try:
        r  = requests.post(f"{API}/api/predict", json={
            "oil_price": sim_oil, "dry_bulk_index": sim_bulk,
            "sentiment_score": sim_sent, "horizon_days": 7,
        }, timeout=5).json()
        rate = r["predicted_rate_usd_per_teu"]
        c    = r["components"]
        col_a, col_b, col_c, col_d = st.columns(4)
        col_a.metric("PREDICTED RATE",   f"USD {rate:,.0f}/TEU")
        col_b.metric("OIL EFFECT",       f"{c['oil_contribution']:+,.0f}")
        col_c.metric("BULK EFFECT",      f"{c['bulk_stock_contribution']:+,.0f}")
        col_d.metric("SENTIMENT EFFECT", f"{c['sentiment_contribution']:+,.0f}")
        st.caption(f"Confidence: {r['confidence']:.1%}  |  Horizon: {r['horizon_days']}d")
    except Exception as e:
        st.error(f"預測失敗：{e}")

st.markdown('<hr class="divider-glow">', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════
#  新聞 + 社群情緒
# ══════════════════════════════════════════════════════════════
col_l, col_r = st.columns([3, 2])

with col_l:
    st.markdown('<p class="section-title">◈ Live News Feed</p>', unsafe_allow_html=True)
    src_opts = ["Google News", "Splash247", "The Loadstar", "Hellenic Shipping News"]
    src_sel  = st.multiselect("Sources", src_opts, default=src_opts, label_visibility="collapsed")
    try:
        news = requests.get(f"{API}/api/news/latest?size=20", timeout=5).json()
        shown = 0
        for a in news:
            if a.get("source") not in src_sel:
                continue
            score = a.get("score", 0)
            icon  = "🔴" if score < -0.2 else "🟢" if score > 0.2 else "🟡"
            url   = a.get("url", "")
            title = a.get("title", "")
            link  = f"[{title}]({url})" if url else title
            st.markdown(
                f"{icon} {link}  \n"
                f"<small style='color:#445566'>📌 {a.get('source','')} &nbsp;|&nbsp; score: <code>{score:+.2f}</code></small>",
                unsafe_allow_html=True,
            )
            shown += 1
            if shown >= 10:
                break
        try:
            ns  = requests.get(f"{API}/api/news/sentiment", timeout=5).json()
            avg = ns.get("avg_score", 0)
            tot = sum(ns.get("overall", {}).values())
            pos = ns.get("overall", {}).get("positive", 0)
            neg = ns.get("overall", {}).get("negative", 0)
            mkt = "🔴 BEARISH" if avg < -0.1 else "🟢 BULLISH" if avg > 0.1 else "🟡 NEUTRAL"
            st.info(f"Overall Sentiment: **{mkt}** &nbsp; avg={avg:+.3f} &nbsp; pos={pos} neg={neg} total={tot}")
        except Exception:
            pass
    except Exception:
        st.info("新聞載入中...")

with col_r:
    st.markdown('<p class="section-title">◈ StockTwits Pulse</p>', unsafe_allow_html=True)
    try:
        comm = requests.get(f"{API}/api/community/sentiment", timeout=5).json()
        for ticker, data in comm.items():
            total = data.get("total", 0)
            if total == 0:
                continue
            avg   = data.get("avg_score", 0)
            bull  = data.get("positive", 0) / total if total else 0
            bear  = data.get("negative", 0) / total if total else 0
            bar_c = "#00ffaa" if avg > 0.1 else "#ff4d4d" if avg < -0.1 else "#8899aa"
            st.markdown(
                f'<span class="ticker-badge">${ticker}</span> &nbsp;'
                f'<code style="color:{bar_c}">{avg:+.3f}</code> &nbsp;'
                f'<small style="color:#445566">▲{bull:.0%} ▼{bear:.0%} ({total} msgs)</small>',
                unsafe_allow_html=True,
            )
            st.progress(bull, text="")
            st.write("")
    except Exception:
        st.info("社群數據載入中...")

    st.markdown("---")
    sel = st.selectbox("Recent Posts", ["ZIM", "SBLK", "EGLE", "BDRY"], label_visibility="visible")
    try:
        posts = requests.get(f"{API}/api/community/recent?ticker={sel}&size=4", timeout=5).json()
        for p in posts:
            sc   = p.get("score", 0)
            icon = "🟢" if sc > 0.1 else "🔴" if sc < -0.1 else "🟡"
            st.markdown(f"{icon} `{sc:+.2f}` {p.get('body','')[:100]}...", unsafe_allow_html=True)
    except Exception:
        pass
