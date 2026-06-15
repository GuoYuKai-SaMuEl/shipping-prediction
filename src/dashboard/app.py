"""
ShipPulse v3 — Maritime Intelligence Platform
Multi-page dashboard: sidebar navigation, English UI, Gemini AI integration
"""
import html
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

API           = "http://localhost:8000"
INSIGHTS_PATH = Path(__file__).resolve().parents[2] / "data" / "ai_insights.json"

st.set_page_config(
    page_title="ShipPulse — Maritime Intelligence",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@400;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Rajdhani', 'Share Tech Mono', monospace; }

section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #03090f 0%, #050d1a 100%);
  border-right: 1px solid #0d2040;
}

.main > div:first-child { border-top: 2px solid #00d4ff; }

[data-testid="metric-container"] {
  background: linear-gradient(135deg, #0a1628 0%, #0d1e38 100%);
  border: 1px solid #1a3a5c;
  border-left: 3px solid #00d4ff;
  border-radius: 6px;
  padding: 12px 16px;
}
[data-testid="metric-container"]:hover { border-left-color: #00ffaa; }

.predict-card {
  background: linear-gradient(135deg, #0a1628 0%, #0c1830 100%);
  border: 1px solid #1a3a5c;
  border-radius: 8px;
  padding: 14px 18px;
  margin: 4px 0;
  transition: border-color 0.2s ease;
}
.predict-card:hover { border-color: #00d4ff; box-shadow: 0 0 12px rgba(0,212,255,0.12); }

.signal-up3   { color:#ff4d4d; font-size:1.6rem; font-weight:700; }
.signal-up2   { color:#ff8c42; font-size:1.4rem; font-weight:700; }
.signal-up1   { color:#ffd166; font-size:1.2rem; font-weight:600; }
.signal-flat  { color:#8899aa; font-size:1.2rem; font-weight:500; }
.signal-down1 { color:#90e0ef; font-size:1.2rem; font-weight:600; }
.signal-down2 { color:#48cae4; font-size:1.4rem; font-weight:700; }
.signal-down3 { color:#00b4d8; font-size:1.6rem; font-weight:700; }

.mag-bar { display:inline-block; height:8px; border-radius:4px; margin-right:4px; }

.divider-glow {
  border: 0; height: 1px;
  background: linear-gradient(90deg, transparent, #00d4ff55, transparent);
  margin: 16px 0;
}

.section-title {
  font-family: 'Rajdhani', sans-serif;
  font-size: 1.05rem; color: #00d4ff;
  letter-spacing: 3px; text-transform: uppercase;
  margin-bottom: 8px;
}

.page-header {
  font-family: 'Rajdhani', sans-serif;
  font-size: 1.8rem; font-weight: 700;
  color: #c9d8f0; letter-spacing: 2px;
  margin-bottom: 2px;
}
.page-sub {
  font-size: 0.78rem; color: #5a7a95;
  letter-spacing: 2px; margin-bottom: 20px;
}

.ticker-badge {
  background: #0d1e38; border: 1px solid #1a3a5c;
  border-radius: 4px; padding: 2px 8px;
  font-size: 0.8rem; color: #00d4ff;
}

.news-item {
  background: #080f1c;
  border: 1px solid #12253a;
  border-radius: 6px;
  padding: 10px 14px;
  margin: 5px 0;
  line-height: 1.5;
}

.ai-card {
  background: linear-gradient(135deg, #081a0f 0%, #0a2015 100%);
  border: 1px solid #1a5c3a;
  border-left: 3px solid #00ffaa;
  border-radius: 8px;
  padding: 20px 24px;
  margin: 8px 0;
}

.comm-card {
  background: linear-gradient(135deg, #0a1628 0%, #0d1e38 100%);
  border: 1px solid #1a3a5c;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 8px;
  text-align: center;
}
</style>
""", unsafe_allow_html=True)


# ── Shared constants & helpers ────────────────────────────────

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(5,13,26,0.8)",
    font=dict(family="Share Tech Mono, monospace", color="#8899aa", size=10),
    margin=dict(l=0, r=0, t=28, b=0),
    height=210,
    showlegend=False,
    xaxis=dict(showgrid=True, gridcolor="#0d1e38", gridwidth=1, zeroline=False,
               fixedrange=True, tickfont=dict(size=9)),
    yaxis=dict(showgrid=True, gridcolor="#0d1e38", gridwidth=1, zeroline=False,
               fixedrange=True, autorange=True, tickfont=dict(size=9)),
)
CHART_CFG = dict(scrollZoom=False, displayModeBar=False)

ARROW = {
    ("up",   3): ("↑↑↑", "signal-up3",   "Strong Upside",    "#ff4d4d"),
    ("up",   2): ("↑↑",  "signal-up2",   "Moderate Upside",  "#ff8c42"),
    ("up",   1): ("↑",   "signal-up1",   "Slight Upside",    "#ffd166"),
    ("flat", 1): ("→",   "signal-flat",  "Sideways",         "#8899aa"),
    ("flat", 2): ("→",   "signal-flat",  "Sideways",         "#8899aa"),
    ("flat", 3): ("→",   "signal-flat",  "Sideways",         "#8899aa"),
    ("down", 1): ("↓",   "signal-down1", "Slight Decline",   "#90e0ef"),
    ("down", 2): ("↓↓",  "signal-down2", "Moderate Decline", "#48cae4"),
    ("down", 3): ("↓↓↓", "signal-down3", "Sharp Decline",    "#00b4d8"),
}

TICKER_DESC = {
    "ZIM":  "ZIM Integrated Shipping",
    "SBLK": "Star Bulk Carriers",
    "EGLE": "Eagle Bulk Shipping",
    "BDRY": "Breakwave Dry Bulk ETF",
}


def api_get(path: str, params: dict | None = None, timeout: int = 6):
    try:
        return requests.get(f"{API}{path}", params=params, timeout=timeout).json()
    except Exception:
        return None


def make_chart(data, title, color="#00d4ff", fill="rgba(0,212,255,0.06)", height=210):
    if not data:
        return None
    df = pd.DataFrame(data)
    df["time"] = pd.to_datetime(df["time"], format="%Y-%m-%dT%H:%M:%SZ", utc=True)
    df = df.sort_values("time").dropna(subset=["value"])
    if df.empty:
        return None
    vmin, vmax = df["value"].min(), df["value"].max()
    pad = max((vmax - vmin) * 0.08, abs(vmax) * 0.005)
    base = [vmin - pad] * len(df)
    fig  = go.Figure()
    fig.add_trace(go.Scatter(x=df["time"], y=base,
                             mode="lines", line=dict(width=0),
                             showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=df["time"], y=df["value"],
                             mode="lines", line=dict(color=color, width=1.8),
                             fill="tonexty", fillcolor=fill,
                             hovertemplate="%{x|%m/%d}<br><b>%{y:.2f}</b><extra></extra>"))
    layout = {
        **PLOTLY_LAYOUT, "height": height,
        "title": dict(text=title, font=dict(size=11, color="#5a7a95"), x=0),
        "yaxis": {**PLOTLY_LAYOUT["yaxis"], "range": [vmin - pad, vmax + pad], "autorange": False},
    }
    fig.update_layout(**layout)
    return fig


def render_route_card(r):
    d, mag = r["direction"], r["magnitude"]
    arrow, css, label, _ = ARROW.get((d, mag), ("→", "signal-flat", "Sideways", "#8899aa"))
    drv  = r["drivers"]
    bars = "".join(
        f'<span class="mag-bar" style="width:18px;background:'
        f'{"#ff8c42" if i <= mag and d == "up" else "#48cae4" if i <= mag and d == "down" else "#1a3a5c"}'
        f';"></span>'
        for i in range(1, 4)
    )
    driver_txt = (
        f"Oil: {drv['oil_trend']:+.1%} &nbsp; "
        f"Bulk: {drv['bulk_trend']:+.1%} &nbsp; "
        f"ZIM: {drv['zim_trend']:+.1%} &nbsp; "
        f"News: {drv['disruption']:+.2f}"
    )
    st.markdown(f"""
    <div class="predict-card">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <div>
          <span style="font-size:0.7rem;color:#5a7a95;letter-spacing:2px;">{r['name_en'].upper()}</span><br>
          <span style="font-size:0.95rem;font-weight:700;color:#c9d8f0;">{r['desc']}</span>
        </div>
        <div style="text-align:right;">
          <span class="{css}">{arrow}</span>
          <span style="font-size:0.78rem;color:#8899aa;margin-left:8px;">{label}</span><br>
          <div style="margin-top:4px;">{bars}</div>
        </div>
      </div>
      <div style="margin-top:6px;font-size:0.7rem;color:#5a7a95;">{driver_txt}</div>
    </div>""", unsafe_allow_html=True)


def load_ai_insights() -> dict | None:
    if INSIGHTS_PATH.exists():
        try:
            return json.loads(INSIGHTS_PATH.read_text())
        except Exception:
            pass
    return None


def fmt_age(iso_ts: str) -> tuple[str, str]:
    """Returns (label, color) based on how old the timestamp is."""
    try:
        t   = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - t).total_seconds() / 3600
        label = f"{age:.0f}h ago" if age >= 1 else f"{age * 60:.0f}m ago"
        color = "#00ffaa" if age < 4 else "#ffd166" if age < 12 else "#ff4d4d"
        return label, color
    except Exception:
        return "unknown", "#8899aa"


# ── Sidebar ───────────────────────────────────────────────────

with st.sidebar:
    st.markdown("""
    <div style="padding:16px 8px 10px 8px;">
      <div style="font-family:'Rajdhani',sans-serif;font-size:1.5rem;font-weight:700;
                  color:#00d4ff;letter-spacing:3px;">⬡ SHIPPULSE</div>
      <div style="font-size:0.65rem;color:#4e7a9a;letter-spacing:3px;margin-top:2px;">
        MARITIME INTELLIGENCE PLATFORM
      </div>
    </div>
    <hr style="border:0;height:1px;background:#0d2040;margin:4px 0 8px 0;">
    """, unsafe_allow_html=True)

    page = st.radio(
        "nav",
        ["📊  Overview",
         "📈  Market Intelligence",
         "📰  News & Sentiment",
         "💬  Community Pulse",
         "🤖  AI Market Brief"],
        label_visibility="collapsed",
    )

    st.markdown('<hr style="border:0;height:1px;background:#0d2040;margin:8px 0;">', unsafe_allow_html=True)

    # Live quick-stats
    m = api_get("/api/metrics/latest")
    if m:
        st.markdown('<div style="font-size:0.62rem;color:#4e7a9a;letter-spacing:2px;margin-bottom:6px;">LIVE PRICES</div>',
                    unsafe_allow_html=True)
        oil  = m.get("oil_price_usd")
        bdry = m.get("bdry_etf")
        zim  = m.get("zim_stock")
        sblk = m.get("sblk")
        if oil:  st.markdown(f'<div style="font-size:0.82rem;color:#ff8c42;padding:2px 0;">🛢 WTI &nbsp;&nbsp;&nbsp; <b style="color:#e0a060;">${oil:.2f}</b></div>', unsafe_allow_html=True)
        if bdry: st.markdown(f'<div style="font-size:0.82rem;color:#00a8cc;padding:2px 0;">🚢 BDRY &nbsp;&nbsp; <b style="color:#00c8ee;">${bdry:.3f}</b></div>', unsafe_allow_html=True)
        if zim:  st.markdown(f'<div style="font-size:0.82rem;color:#00cc88;padding:2px 0;">📦 ZIM &nbsp;&nbsp;&nbsp; <b style="color:#00eeaa;">${zim:.2f}</b></div>', unsafe_allow_html=True)
        if sblk: st.markdown(f'<div style="font-size:0.82rem;color:#9988cc;padding:2px 0;">⚓ SBLK &nbsp;&nbsp; <b style="color:#bbaae8;">${sblk:.2f}</b></div>', unsafe_allow_html=True)

    st.markdown('<hr style="border:0;height:1px;background:#0d2040;margin:8px 0;">', unsafe_allow_html=True)

    # AI brief freshness
    ai = load_ai_insights()
    if ai and ai.get("generated_at"):
        label, color = fmt_age(ai["generated_at"])
        st.markdown(f"""
        <div style="font-size:0.62rem;color:#4e7a9a;letter-spacing:2px;margin-bottom:4px;">AI BRIEF</div>
        <div style="font-size:0.78rem;color:{color};">● Updated {label}</div>
        """, unsafe_allow_html=True)
    else:
        st.markdown('<div style="font-size:0.75rem;color:#4e7a9a;">AI Brief: not generated</div>',
                    unsafe_allow_html=True)

    st.markdown("""
    <div style="position:fixed;bottom:12px;left:0;right:0;width:260px;
                text-align:center;font-size:0.6rem;color:#4a6a80;">
      ShipPulse v3 · Real-time Maritime Data
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
#  PAGE 1 — Overview
# ══════════════════════════════════════════════════════════════
if page == "📊  Overview":
    st.markdown('<p class="page-header">MARKET OVERVIEW</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-sub">REAL-TIME MARITIME SHIPPING INTELLIGENCE DASHBOARD</p>', unsafe_allow_html=True)

    # Metric cards
    m    = api_get("/api/metrics/latest") or {}
    oil  = m.get("oil_price_usd")
    bdry = m.get("bdry_etf")
    zim  = m.get("zim_stock")
    bulk = m.get("dry_bulk_composite")
    sblk = m.get("sblk")
    egle = m.get("egle")

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("🛢 WTI CRUDE",     f"${oil:.2f}"  if oil  else "—", help="Yahoo Finance CL=F futures")
    c2.metric("🚢 BDRY ETF",      f"${bdry:.3f}" if bdry else "—", help="Breakwave Dry Bulk ETF")
    c3.metric("📦 ZIM SHIPPING",  f"${zim:.2f}"  if zim  else "—", help="ZIM Integrated Shipping")
    c4.metric("⚓ DRY BULK IDX",  f"${bulk:.2f}" if bulk else "—", help="(SBLK+EGLE)/2 proxy")
    c5.metric("🌊 SBLK",         f"${sblk:.2f}" if sblk else "—", help="Star Bulk Carriers")
    c6.metric("🔱 EGLE",         f"${egle:.2f}" if egle else "—", help="Eagle Bulk Shipping")

    st.markdown('<hr class="divider-glow">', unsafe_allow_html=True)

    # Route predictions
    st.markdown('<p class="section-title">◈ 7-Day Freight Rate Outlook</p>', unsafe_allow_html=True)
    routes = api_get("/api/predict/routes", timeout=10)
    if routes:
        c_routes = {k: v for k, v in routes.items() if v["type"] == "container"}
        b_routes = {k: v for k, v in routes.items() if v["type"] == "dry_bulk"}
        col_c, col_b = st.columns(2)
        with col_c:
            st.markdown('<span style="font-size:0.7rem;color:#5a7a95;letter-spacing:2px;">◆ CONTAINER SHIPPING</span>',
                        unsafe_allow_html=True)
            for r in c_routes.values():
                render_route_card(r)
        with col_b:
            st.markdown('<span style="font-size:0.7rem;color:#5a7a95;letter-spacing:2px;">◆ DRY BULK SHIPPING</span>',
                        unsafe_allow_html=True)
            for r in b_routes.values():
                render_route_card(r)
    else:
        st.warning("Prediction service unavailable. Make sure the FastAPI backend is running.")

    st.markdown('<hr class="divider-glow">', unsafe_allow_html=True)

    # Bottom row: headlines + AI preview
    col_news, col_ai = st.columns([3, 2])

    with col_news:
        st.markdown('<p class="section-title">◈ Latest Headlines</p>', unsafe_allow_html=True)
        news = api_get("/api/news/latest", params={"size": 6})
        if news:
            for a in news[:6]:
                score = a.get("score", 0)
                icon  = "🔴" if score < -0.2 else "🟢" if score > 0.2 else "🟡"
                title = html.escape(a.get("title", ""))
                url   = a.get("url", "")
                src   = html.escape(a.get("source", ""))
                link  = f'<a href="{url}" target="_blank" style="color:#b0c8e0;text-decoration:none;">{title}</a>' if url else f'<span style="color:#b0c8e0;">{title}</span>'
                st.markdown(
                    f'<div class="news-item">{icon} {link}'
                    f'<div style="font-size:0.7rem;color:#5a7a95;margin-top:4px;">'
                    f'📌 {src} &nbsp;|&nbsp; score: <code style="color:#5588aa;">{score:+.2f}</code></div></div>',
                    unsafe_allow_html=True,
                )
        else:
            st.info("News unavailable")

    with col_ai:
        st.markdown('<p class="section-title">◈ AI Brief Preview</p>', unsafe_allow_html=True)
        ai = load_ai_insights()
        if ai and ai.get("summary"):
            preview = ai["summary"][:420].rsplit(" ", 1)[0] + " ..."
            ts_str  = ai.get("generated_at", "")
            label, color = fmt_age(ts_str) if ts_str else ("—", "#8899aa")
            st.markdown(
                f'<div class="ai-card">'
                f'<div style="font-size:0.62rem;color:#00ffaa;letter-spacing:2px;margin-bottom:8px;">🤖 GEMINI AI · {label}</div>'
                f'<div style="font-size:0.82rem;color:#b0c8e0;line-height:1.7;">{html.escape(preview)}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.caption("→ See full analysis on the AI Market Brief page")
        else:
            st.markdown(
                '<div class="ai-card">'
                '<div style="color:#5a7a95;font-size:0.82rem;line-height:1.7;">'
                'No AI brief generated yet.<br>'
                'Go to <b style="color:#00ffaa;">AI Market Brief</b> page and click Refresh to generate.'
                '</div></div>',
                unsafe_allow_html=True,
            )


# ══════════════════════════════════════════════════════════════
#  PAGE 2 — Market Intelligence
# ══════════════════════════════════════════════════════════════
elif page == "📈  Market Intelligence":
    st.markdown('<p class="page-header">MARKET INTELLIGENCE</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-sub">HISTORICAL PRICE ANALYSIS · TREND INDICATORS · SCENARIO SIMULATOR</p>',
                unsafe_allow_html=True)

    days = st.slider("History window (days)", 7, 88, 30, label_visibility="collapsed")

    CHART_SPECS = [
        ("oil",  "WTI Crude Oil (USD/bbl)",       "#ff8c42", "rgba(255,140,66,0.06)"),
        ("bdry", "BDRY Dry Bulk ETF (USD)",        "#00d4ff", "rgba(0,212,255,0.06)"),
        ("zim",  "ZIM Container Shipping (USD)",   "#00ffaa", "rgba(0,255,170,0.06)"),
        ("sblk", "SBLK Star Bulk Carriers (USD)",  "#a78bfa", "rgba(167,139,250,0.06)"),
        ("egle", "EGLE Eagle Bulk Shipping (USD)", "#f472b6", "rgba(244,114,182,0.06)"),
    ]

    st.markdown('<p class="section-title">◈ Price History</p>', unsafe_allow_html=True)
    hist = api_get("/api/metrics/history", params={"days": days}, timeout=12)

    if hist:
        for i in range(0, len(CHART_SPECS), 2):
            row = st.columns(2)
            for j, (key, title, color, fill) in enumerate(CHART_SPECS[i:i+2]):
                with row[j]:
                    fig = make_chart(hist.get(key, []), title, color, fill)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True, config=CHART_CFG)
                    else:
                        st.info(f"No data for {key.upper()}")
    else:
        st.error("Failed to load history data")

    # Trend summary table
    st.markdown('<hr class="divider-glow">', unsafe_allow_html=True)
    st.markdown('<p class="section-title">◈ Trend Summary</p>', unsafe_allow_html=True)

    m   = api_get("/api/metrics/latest") or {}
    KEY_MAP = {"oil": "oil_price_usd", "bdry": "bdry_etf", "zim": "zim_stock",
               "sblk": "sblk", "egle": "egle"}
    rows = []
    if hist:
        for key, label, _, _ in CHART_SPECS:
            series = hist.get(key, [])
            vals   = [r["value"] for r in series if r.get("value") is not None]
            if not vals:
                continue
            cur   = m.get(KEY_MAP.get(key, ""))
            n7    = min(7,  len(vals))
            n30   = min(30, len(vals))
            avg7  = sum(vals[-n7:])  / n7
            avg30 = sum(vals[-n30:]) / n30
            chg7  = (vals[-1] - vals[-n7])  / vals[-n7]  * 100 if vals[-n7]  else 0
            chg30 = (vals[-1] - vals[-n30]) / vals[-n30] * 100 if vals[-n30] else 0
            trend = "↑" if chg7 > 0.5 else "↓" if chg7 < -0.5 else "→"
            rows.append({
                "Indicator":   label.split("(")[0].strip(),
                "Current":     f"${cur:.2f}"      if cur   else f"${vals[-1]:.2f}",
                "7d Avg":      f"${avg7:.2f}",
                "30d Avg":     f"${avg30:.2f}",
                "7d Change":   f"{chg7:+.1f}%",
                "30d Change":  f"{chg30:+.1f}%",
                "Trend":       trend,
            })
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # Scenario simulator
    st.markdown('<hr class="divider-glow">', unsafe_allow_html=True)
    st.markdown('<p class="section-title">◈ Scenario Simulator</p>', unsafe_allow_html=True)
    st.caption("Model how changes in market conditions affect container freight rates")

    oil_v  = m.get("oil_price_usd")
    bulk_v = m.get("dry_bulk_composite")

    sa, sb, sc = st.columns(3)
    with sa: sim_oil  = st.slider("Oil Price (USD/bbl)",    40.0, 150.0, float(oil_v)  if oil_v  else 80.0, 0.5)
    with sb: sim_bulk = st.slider("Dry Bulk Composite (USD)", 5.0, 80.0, float(bulk_v) if bulk_v else 27.0, 0.5)
    with sc: sim_sent = st.slider("Sentiment Score",         -1.0,  1.0, 0.0, 0.05)

    if st.button("▶  RUN SIMULATION", type="primary", use_container_width=True):
        try:
            r = requests.post(f"{API}/api/predict", json={
                "oil_price": sim_oil, "dry_bulk_index": sim_bulk,
                "sentiment_score": sim_sent, "horizon_days": 7,
            }, timeout=5).json()
            rate = r["predicted_rate_usd_per_teu"]
            c    = r["components"]
            pa, pb, pc, pd_ = st.columns(4)
            pa.metric("PREDICTED RATE",    f"USD {rate:,.0f} /TEU")
            pb.metric("OIL CONTRIBUTION",  f"{c['oil_contribution']:+,.0f}")
            pc.metric("BULK CONTRIBUTION", f"{c['bulk_stock_contribution']:+,.0f}")
            pd_.metric("SENTIMENT EFFECT",  f"{c['sentiment_contribution']:+,.0f}")
            st.caption(f"Model confidence: {r['confidence']:.1%}  |  Horizon: {r['horizon_days']} days")
        except Exception as e:
            st.error(f"Simulation failed: {e}")


# ══════════════════════════════════════════════════════════════
#  PAGE 3 — News & Sentiment
# ══════════════════════════════════════════════════════════════
elif page == "📰  News & Sentiment":
    st.markdown('<p class="page-header">NEWS & SENTIMENT</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-sub">REAL-TIME SHIPPING NEWS · NLP SENTIMENT SCORING · SOURCE BREAKDOWN</p>',
                unsafe_allow_html=True)

    # Sentiment summary bar
    ns = api_get("/api/news/sentiment")
    if ns:
        avg     = ns.get("avg_score", 0)
        overall = ns.get("overall", {})
        tot     = sum(overall.values())
        pos     = overall.get("positive", 0)
        neg     = overall.get("negative", 0)
        neu     = overall.get("neutral", 0)
        tone    = "BEARISH" if avg < -0.1 else "BULLISH" if avg > 0.1 else "NEUTRAL"
        tc      = "#ff4d4d" if avg < -0.1 else "#00ffaa" if avg > 0.1 else "#ffd166"

        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("MARKET TONE",    tone)
        k2.metric("AVG SCORE",      f"{avg:+.3f}")
        k3.metric("POSITIVE",       str(pos))
        k4.metric("NEGATIVE",       str(neg))
        k5.metric("TOTAL ARTICLES", str(tot))

        by_src = ns.get("by_source", [])
        if by_src:
            st.markdown('<hr class="divider-glow">', unsafe_allow_html=True)
            st.markdown('<p class="section-title">◈ By Source</p>', unsafe_allow_html=True)
            scols = st.columns(max(len(by_src), 1))
            for i, src in enumerate(by_src):
                sc_val = src.get("avg_score", 0)
                sc_col = "#ff4d4d" if sc_val < -0.1 else "#00ffaa" if sc_val > 0.1 else "#ffd166"
                with scols[i % len(scols)]:
                    st.markdown(f"""
                    <div style="background:#080f1c;border:1px solid #12253a;border-radius:6px;
                                padding:14px;text-align:center;">
                      <div style="font-size:0.7rem;color:#5a7a95;letter-spacing:1px;margin-bottom:6px;">
                        {html.escape(src['source'][:22])}
                      </div>
                      <div style="font-size:1.6rem;font-weight:700;color:{sc_col};">{sc_val:+.3f}</div>
                      <div style="font-size:0.72rem;color:#8899aa;">{src['count']} articles</div>
                    </div>""", unsafe_allow_html=True)

    st.markdown('<hr class="divider-glow">', unsafe_allow_html=True)

    # Filter controls
    fa, fb = st.columns([4, 1])
    with fa:
        src_opts = ["Google News", "Splash247", "The Loadstar", "Hellenic Shipping News"]
        src_sel  = st.multiselect("Filter by source", src_opts, default=src_opts,
                                   label_visibility="collapsed")
    with fb:
        n_news = st.selectbox("Show", [10, 20, 30], index=1, label_visibility="collapsed")

    st.markdown('<p class="section-title">◈ News Feed</p>', unsafe_allow_html=True)

    news = api_get("/api/news/latest", params={"size": n_news})
    if news:
        shown = 0
        for a in news:
            if a.get("source") not in src_sel:
                continue
            score   = a.get("score", 0)
            icon    = "🔴" if score < -0.2 else "🟢" if score > 0.2 else "🟡"
            title   = html.escape(a.get("title", "No title"))
            url     = a.get("url", "")
            src     = html.escape(a.get("source", ""))
            pub     = a.get("published", a.get("indexed_at", ""))[:16].replace("T", " ")
            sent_l  = "NEGATIVE" if score < -0.2 else "POSITIVE" if score > 0.2 else "NEUTRAL"
            sent_c  = "#ff4d4d" if score < -0.2 else "#00ffaa" if score > 0.2 else "#ffd166"
            link    = (f'<a href="{url}" target="_blank" style="color:#b0c8e0;text-decoration:none;">{title}</a>'
                       if url else f'<span style="color:#b0c8e0;">{title}</span>')
            st.markdown(f"""
            <div class="news-item">
              <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;">
                <div style="flex:1;font-size:0.88rem;">{icon} {link}</div>
                <span style="color:{sent_c};font-size:0.68rem;letter-spacing:1px;
                             flex-shrink:0;margin-top:2px;">{sent_l} {score:+.2f}</span>
              </div>
              <div style="font-size:0.7rem;color:#5a7a95;margin-top:5px;">
                📌 {src} &nbsp;·&nbsp; {pub}
              </div>
            </div>""", unsafe_allow_html=True)
            shown += 1
            if shown >= n_news:
                break
        if shown == 0:
            st.info("No articles match the selected sources.")
    else:
        st.error("News feed unavailable")


# ══════════════════════════════════════════════════════════════
#  PAGE 4 — Community Pulse
# ══════════════════════════════════════════════════════════════
elif page == "💬  Community Pulse":
    st.markdown('<p class="page-header">COMMUNITY PULSE</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-sub">STOCKTWITS SENTIMENT · SHIPPING STOCK DISCUSSIONS · 48H WINDOW</p>',
                unsafe_allow_html=True)

    comm = api_get("/api/community/sentiment")
    if comm:
        st.markdown('<p class="section-title">◈ Sentiment Overview (Last 48h)</p>', unsafe_allow_html=True)
        cols = st.columns(4)
        for i, (ticker, data) in enumerate(comm.items()):
            total  = data.get("total", 0)
            avg    = data.get("avg_score", 0)
            pos    = data.get("positive", 0)
            neg    = data.get("negative", 0)
            neu    = data.get("neutral", 0)
            bull   = pos / total if total else 0
            bc     = "#00ffaa" if avg > 0.1 else "#ff4d4d" if avg < -0.1 else "#8899aa"
            sig    = "BULLISH" if avg > 0.1 else "BEARISH" if avg < -0.1 else "NEUTRAL"
            with cols[i % 4]:
                st.markdown(f"""
                <div class="comm-card" style="border-top:3px solid {bc};">
                  <div style="font-size:1.05rem;font-weight:700;color:#00d4ff;">${ticker}</div>
                  <div style="font-size:0.68rem;color:#5a7a95;margin-bottom:10px;">
                    {html.escape(TICKER_DESC.get(ticker, ''))}
                  </div>
                  <div style="font-size:1.8rem;font-weight:700;color:{bc};">{avg:+.3f}</div>
                  <div style="font-size:0.7rem;color:{bc};letter-spacing:2px;margin-bottom:10px;">{sig}</div>
                  <div style="font-size:0.72rem;color:#8899aa;">
                    ▲ {pos} bull &nbsp; ▼ {neg} bear &nbsp; — {neu} neutral
                  </div>
                  <div style="font-size:0.68rem;color:#5a7a95;margin-top:4px;">{total} messages analyzed</div>
                </div>""", unsafe_allow_html=True)
                st.progress(bull, text="")
    else:
        st.error("Community data unavailable")

    st.markdown('<hr class="divider-glow">', unsafe_allow_html=True)
    st.markdown('<p class="section-title">◈ Recent Posts</p>', unsafe_allow_html=True)

    ca, _ = st.columns([2, 5])
    with ca:
        sel = st.selectbox("Select ticker", ["ZIM", "SBLK", "EGLE", "BDRY"],
                            label_visibility="collapsed")

    posts = api_get("/api/community/recent", params={"ticker": sel, "size": 12})
    if posts:
        for p in posts:
            sc    = p.get("score", 0)
            icon  = "🟢" if sc > 0.1 else "🔴" if sc < -0.1 else "🟡"
            sc_c  = "#00ffaa" if sc > 0.1 else "#ff4d4d" if sc < -0.1 else "#8899aa"
            body  = html.escape(p.get("body", "")[:220])
            likes = p.get("likes", 0)
            st.markdown(f"""
            <div class="news-item">
              <div style="display:flex;justify-content:space-between;gap:12px;">
                <div style="flex:1;font-size:0.84rem;color:#b0c8e0;">{icon} {body}</div>
                <div style="text-align:right;flex-shrink:0;">
                  <div style="color:{sc_c};font-size:0.82rem;font-weight:700;">{sc:+.2f}</div>
                  <div style="color:#5a7a95;font-size:0.68rem;">♥ {likes}</div>
                </div>
              </div>
            </div>""", unsafe_allow_html=True)
    else:
        st.info(f"No recent posts found for ${sel}")


# ══════════════════════════════════════════════════════════════
#  PAGE 5 — AI Market Brief
# ══════════════════════════════════════════════════════════════
elif page == "🤖  AI Market Brief":
    st.markdown('<p class="page-header">AI MARKET BRIEF</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-sub">POWERED BY GOOGLE GEMINI · NEWS + MARKET DATA + COMMUNITY SYNTHESIS</p>',
                unsafe_allow_html=True)

    ai = load_ai_insights()

    # Status bar
    hdr_l, hdr_r = st.columns([5, 1])
    with hdr_l:
        if ai and ai.get("generated_at"):
            label, color = fmt_age(ai["generated_at"])
            ts = datetime.fromisoformat(ai["generated_at"].replace("Z", "+00:00"))
            next_refresh = ts.replace(hour=((ts.hour // 4 + 1) * 4) % 24, minute=0, second=0, microsecond=0)
            st.markdown(
                f'<span style="color:{color};font-size:0.85rem;">● Last updated: '
                f'{ts.strftime("%Y-%m-%d %H:%M")} UTC &nbsp;({label})</span>'
                f'<span style="color:#4e7a9a;font-size:0.78rem;margin-left:16px;">'
                f'⏱ Auto-refresh every 4 hours</span>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<span style="color:#5a7a95;font-size:0.85rem;">● No brief generated yet</span>'
                '<span style="color:#4e7a9a;font-size:0.78rem;margin-left:16px;">⏱ Auto-refresh every 4 hours once configured</span>',
                unsafe_allow_html=True,
            )
    with hdr_r:
        force_now = st.button("⚡ Generate Now", type="secondary", use_container_width=True,
                              help="Trigger an immediate update (bypasses the 4h schedule)")

    if force_now:
        with st.spinner("Calling Gemini — this takes ~10 seconds..."):
            try:
                r = requests.post(f"{API}/api/ai/refresh", timeout=120)
                if r.status_code == 200:
                    st.success("Brief updated!")
                    st.rerun()
                elif r.status_code == 503:
                    detail = r.json().get("detail", "")
                    st.error(f"API key not configured: {detail}")
                else:
                    st.error(f"Error {r.status_code}: {r.text[:300]}")
            except requests.exceptions.Timeout:
                st.error("Request timed out — Gemini API may be slow. Try again.")
            except Exception as e:
                st.error(f"Connection failed: {e}")

    st.markdown('<hr class="divider-glow">', unsafe_allow_html=True)

    if ai and ai.get("summary"):
        summary = ai["summary"]
        meta    = ai.get("meta", {})

        st.markdown(
            f'<div class="ai-card">'
            f'<div style="font-size:0.65rem;color:#00ffaa;letter-spacing:2px;margin-bottom:14px;">'
            f'🤖 GEMINI AI ANALYSIS &nbsp;·&nbsp; MODEL: {html.escape(meta.get("model", "gemini-2.0-flash"))}'
            f'</div>'
            f'<div style="font-size:0.9rem;color:#c0d8f0;line-height:1.85;white-space:pre-wrap;">'
            f'{html.escape(summary)}'
            f'</div></div>',
            unsafe_allow_html=True,
        )

        if meta:
            st.markdown('<hr class="divider-glow">', unsafe_allow_html=True)
            st.markdown('<p class="section-title">◈ Data Used in This Analysis</p>', unsafe_allow_html=True)
            ma, mb, mc, md = st.columns(4)
            ma.metric("News Articles",        str(meta.get("news_count", "—")))
            mb.metric("Community Posts",      str(meta.get("community_msgs", "—")))
            mc.metric("Market Indicators",    str(meta.get("indicators", "—")))
            md.metric("AI Model",             meta.get("model", "—"))

    else:
        # Setup guide
        st.markdown("""
        <div class="ai-card">
          <div style="font-size:0.82rem;color:#b0c8e0;line-height:2.0;">
            <b style="color:#00ffaa;font-size:1rem;">⬡ Setup Required — Google AI Studio API Key</b><br><br>
            <b style="color:#5588aa;">Step 1.</b> Get a free API key at
            <a href="https://aistudio.google.com" target="_blank" style="color:#00d4ff;">aistudio.google.com</a>
            → Get API key<br>
            <b style="color:#5588aa;">Step 2.</b> SSH into the server and add the key + restart services:<br>
            <code style="color:#ffd166;background:#050d1a;padding:6px 10px;border-radius:4px;display:block;margin:6px 0;font-size:0.78rem;">
echo 'GEMINI_API_KEY=your_key_here' &gt;&gt; ~/homework/shipping-prediction/.env<br>
cd ~/homework/shipping-prediction &amp;&amp; source .env &amp;&amp; export GEMINI_API_KEY<br>
source .venv/bin/activate<br>
fuser -k 8000/tcp<br>
nohup uvicorn src.dashboard.api.main:app --host 0.0.0.0 --port 8000 &gt; logs/fastapi.log 2&gt;&amp;1 &amp;
            </code>
            <b style="color:#5588aa;">Step 3.</b> Start the auto-refresh daemon (generates a new brief every 4 hours):<br>
            <code style="color:#ffd166;background:#050d1a;padding:6px 10px;border-radius:4px;display:block;margin:6px 0;font-size:0.78rem;">
nohup python -m src.processing.ai_summarizer --interval 14400 &gt; logs/ai.log 2&gt;&amp;1 &amp;
            </code>
            <span style="color:#4e7a9a;font-size:0.78rem;">
              The daemon runs in the background and saves the brief to disk every 4 hours.<br>
              Use the <b style="color:#c9d8f0;">⚡ Generate Now</b> button above to force an immediate update.
            </span>
          </div>
        </div>""", unsafe_allow_html=True)

        # Show what data is ready
        st.markdown('<hr class="divider-glow">', unsafe_allow_html=True)
        st.markdown('<p class="section-title">◈ Data Ready for Analysis</p>', unsafe_allow_html=True)
        d1, d2, d3 = st.columns(3)
        m    = api_get("/api/metrics/latest") or {}
        news = api_get("/api/news/latest", params={"size": 1}) or []
        comm = api_get("/api/community/sentiment") or {}
        with d1:
            oil_v = m.get("oil_price_usd")
            st.markdown(f"""<div style="background:#080f1c;border:1px solid #12253a;border-radius:6px;padding:14px;">
              <div style="color:#00d4ff;font-size:0.72rem;letter-spacing:1px;margin-bottom:8px;">MARKET DATA</div>
              <div style="color:#b0c8e0;font-size:0.82rem;line-height:1.8;">
                WTI Crude: ${m.get('oil_price_usd','N/A')}<br>
                BDRY ETF: ${m.get('bdry_etf','N/A')}<br>
                ZIM: ${m.get('zim_stock','N/A')}<br>
                SBLK: ${m.get('sblk','N/A')}
              </div>
            </div>""", unsafe_allow_html=True)
        with d2:
            st.markdown(f"""<div style="background:#080f1c;border:1px solid #12253a;border-radius:6px;padding:14px;">
              <div style="color:#00d4ff;font-size:0.72rem;letter-spacing:1px;margin-bottom:8px;">NEWS FEED</div>
              <div style="color:#b0c8e0;font-size:0.82rem;line-height:1.8;">
                Sources: 4 publications<br>
                Google News<br>Splash247<br>The Loadstar
              </div>
            </div>""", unsafe_allow_html=True)
        with d3:
            total_c = sum(v.get("total", 0) for v in comm.values())
            st.markdown(f"""<div style="background:#080f1c;border:1px solid #12253a;border-radius:6px;padding:14px;">
              <div style="color:#00d4ff;font-size:0.72rem;letter-spacing:1px;margin-bottom:8px;">COMMUNITY</div>
              <div style="color:#b0c8e0;font-size:0.82rem;line-height:1.8;">
                {total_c} StockTwits posts<br>
                ZIM · SBLK · EGLE · BDRY<br>
                48h rolling window
              </div>
            </div>""", unsafe_allow_html=True)
