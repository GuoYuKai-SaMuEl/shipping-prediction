"""
真實市場數據接入器（無需 API Key）
數據來源：Yahoo Finance via yfinance

覆蓋指標：
  - WTI 原油期貨 (CL=F)
  - Brent 原油期貨 (BZ=F)
  - BDI 代理指標：BDRY ETF (追蹤 BDI 期貨) + SBLK/EGLE 散貨航運股
  - 貨櫃航運景氣：ZIM 股價
  - 歷史數據：最多抓 90 天
"""
import time
from datetime import datetime, timezone, timedelta
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import yfinance as yf

INFLUX_URL    = "http://localhost:8086"
INFLUX_TOKEN  = "shipping-super-secret-token"
INFLUX_ORG    = "shipping-org"
INFLUX_BUCKET = "shipping-metrics"

# BDRY 的歷史均值與 BDI 的對應關係（用於換算估計 BDI 數值）
BDRY_TO_BDI_RATIO = 140.0  # 約 1 BDRY ≈ 140 BDI points（歷史估算）

TICKERS = {
    "CL=F":  ("oil_price",       "wti_crude",    "USD/barrel"),
    "BZ=F":  ("brent_price",     "brent_crude",  "USD/barrel"),
    "BDRY":  ("bdi_proxy_etf",   "bdry",         "USD/share"),
    "SBLK":  ("shipping_stock",  "star_bulk",    "USD/share"),
    "EGLE":  ("shipping_stock",  "eagle_bulk",   "USD/share"),
    "ZIM":   ("container_stock", "zim",          "USD/share"),
}


def fetch_history(days: int = 90) -> dict:
    """抓取歷史數據，回傳 {ticker: DataFrame}"""
    period = f"{days}d"
    results = {}
    for sym in TICKERS:
        try:
            df = yf.Ticker(sym).history(period=period)
            if not df.empty:
                results[sym] = df
                print(f"  ✓ {sym}: {len(df)} 天數據，最新={float(df['Close'].iloc[-1]):.2f}")
            else:
                print(f"  ✗ {sym}: 無數據")
        except Exception as e:
            print(f"  ✗ {sym}: {e}")
    return results


def estimate_bdi(bdry_price: float) -> float:
    """由 BDRY ETF 價格估算 BDI 數值"""
    return round(bdry_price * BDRY_TO_BDI_RATIO, 0)


def write_to_influx(history: dict):
    """將歷史數據批量寫入 InfluxDB（只寫 88 天內的資料，配合 90 天保留政策）"""
    client     = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
    writer     = client.write_api(write_options=SYNCHRONOUS)
    points     = []
    total      = 0
    cutoff_utc = datetime.now(timezone.utc) - timedelta(days=88)

    for sym, df in history.items():
        measurement, tag_val, unit = TICKERS[sym]
        for ts, row in df.iterrows():
            close = float(row["Close"])
            if not close or close != close:  # NaN check
                continue
            ts_utc = ts.tz_convert("UTC") if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
            if ts_utc < cutoff_utc:          # 跳過超出保留政策的舊資料
                continue

            p = (Point(measurement)
                 .tag("ticker", sym)
                 .tag("source", tag_val)
                 .tag("unit", unit)
                 .field("close", close)
                 .field("volume", float(row.get("Volume", 0) or 0))
                 .time(ts_utc))
            points.append(p)

        # 對 BDRY 額外寫入估算 BDI
        if sym == "BDRY":
            for ts, row in df.iterrows():
                close = float(row["Close"])
                if not close or close != close:
                    continue
                ts_utc = ts.tz_convert("UTC") if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
                if ts_utc < cutoff_utc:
                    continue
                bdi_est = estimate_bdi(close)
                p = (Point("bdi_index")
                     .tag("source", "bdry_estimated")
                     .tag("note", "estimated_from_BDRY_ETF")
                     .field("value", bdi_est)
                     .time(ts_utc))
                points.append(p)

        # 對 CL=F 額外寫入標準 oil_price measurement（供 API 查詢用）
        if sym == "CL=F":
            for ts, row in df.iterrows():
                close = float(row["Close"])
                if not close or close != close:
                    continue
                ts_utc = ts.tz_convert("UTC") if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
                if ts_utc < cutoff_utc:
                    continue
                p = (Point("oil_price")
                     .tag("source", "eia_wti")
                     .field("value", close)
                     .time(ts_utc))
                points.append(p)

    # 批量寫入
    chunk = 500
    for i in range(0, len(points), chunk):
        writer.write(bucket=INFLUX_BUCKET, record=points[i:i+chunk])
        total += len(points[i:i+chunk])

    client.close()
    return total


def fetch_latest() -> dict:
    """只抓最新一筆，用於即時更新"""
    result = {}
    for sym in TICKERS:
        try:
            t = yf.Ticker(sym)
            h = t.history(period="2d")
            if not h.empty:
                result[sym] = float(h["Close"].iloc[-1])
        except Exception:
            pass
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=90, help="歷史天數")
    parser.add_argument("--watch", action="store_true", help="持續監控模式（每 5 分鐘更新）")
    args = parser.parse_args()

    if args.watch:
        print("[Fetcher] 持續監控模式啟動（每 5 分鐘更新一次）")
        while True:
            latest = fetch_latest()
            client  = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
            writer  = client.write_api(write_options=SYNCHRONOUS)
            now = datetime.now(timezone.utc)
            pts = []
            for sym, price in latest.items():
                m, tag_val, unit = TICKERS[sym]
                pts.append(Point(m).tag("ticker",sym).tag("source",tag_val).field("close",price).time(now))
                if sym == "CL=F":
                    pts.append(Point("oil_price").tag("source","eia_wti").field("value",price).time(now))
                if sym == "BDRY":
                    pts.append(Point("bdi_index").tag("source","bdry_estimated").field("value",estimate_bdi(price)).time(now))
            writer.write(bucket=INFLUX_BUCKET, record=pts)
            client.close()
            print(f"[{now:%H:%M:%S}] 更新 {len(pts)} 筆 | WTI={latest.get('CL=F','?'):.2f} | BDI≈{estimate_bdi(latest.get('BDRY',0)):.0f}")
            time.sleep(300)
    else:
        print(f"[Fetcher] 載入 {args.days} 天歷史真實數據...")
        history = fetch_history(args.days)
        total   = write_to_influx(history)
        print(f"[Fetcher] 完成，共寫入 {total} 筆至 InfluxDB")
