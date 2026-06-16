#!/usr/bin/env bash
# ==============================================================
# ShipPulse — 一鍵啟動所有服務
# 使用方式：./start.sh
# ==============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python3"
VENV_ACTIVATE="$SCRIPT_DIR/.venv/bin/activate"
LOGS="$SCRIPT_DIR/logs"
PIDS="$SCRIPT_DIR/.pids"

# ── 顏色輸出 ──────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[  ✓ ]${NC} $*"; }
warn()    { echo -e "${YELLOW}[ !! ]${NC} $*"; }
die()     { echo -e "${RED}[FAIL]${NC} $*" >&2; exit 1; }

echo -e "${BOLD}======================================${NC}"
echo -e "${BOLD}  ShipPulse — 啟動所有服務${NC}"
echo -e "${BOLD}======================================${NC}"

# ── 前置檢查 ──────────────────────────────────────────────────
[ -d "$SCRIPT_DIR/.venv" ] || die "找不到 .venv，請先執行：python3 -m venv .venv && pip install -r requirements.txt"
command -v docker >/dev/null 2>&1 || die "找不到 docker 指令"
command -v docker compose >/dev/null 2>&1 || die "找不到 docker compose 指令（需要 Compose V2）"

# ── 讀取 .env 取得 API 金鑰 ───────────────────────────────────
if [ -f "$SCRIPT_DIR/.env" ]; then
    # 只匯出非空、非註解行；不覆蓋已設定的環境變數
    set -a
    # shellcheck disable=SC1090
    source "$SCRIPT_DIR/.env"
    set +a
fi

# 宿主機行程使用 localhost 連接 Docker 映射出來的埠
export KAFKA_BROKER="localhost:9092"
export ES_HOST="http://localhost:9200"
export INFLUXDB_URL="http://localhost:8086"

mkdir -p "$LOGS" "$PIDS"

# ── 步驟 1：Docker Compose 基礎設施 ──────────────────────────
echo
echo -e "${BOLD}[1/3] 啟動 Docker Compose 基礎設施${NC}"
docker compose -f deploy/docker-compose.yml up -d
success "Docker Compose 指令已送出"

# 等待 Elasticsearch 就緒（最多 90 秒）
info "等待 Elasticsearch 就緒..."
for i in $(seq 1 45); do
    if curl -sf http://localhost:9200 > /dev/null 2>&1; then
        success "Elasticsearch 已就緒"
        break
    fi
    if [ "$i" -eq 45 ]; then
        warn "Elasticsearch 90 秒後仍未就緒，繼續啟動（請稍後確認 docker logs shipping-es）"
    fi
    sleep 2
done

# 等待 InfluxDB 就緒（最多 60 秒）
info "等待 InfluxDB 就緒..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:8086/ping > /dev/null 2>&1; then
        success "InfluxDB 已就緒"
        break
    fi
    if [ "$i" -eq 30 ]; then
        warn "InfluxDB 60 秒後仍未就緒，繼續啟動"
    fi
    sleep 2
done

# ── 步驟 2：Python 資料接入 Daemon ────────────────────────────
echo
echo -e "${BOLD}[2/3] 啟動資料接入 Workers${NC}"
# shellcheck disable=SC1090
source "$VENV_ACTIVATE"

start_daemon() {
    local name="$1"; shift
    local logfile="$LOGS/${name}.log"
    local pidfile="$PIDS/${name}.pid"

    # 如果已有執行中的 PID，先跳過
    if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
        warn "$name 已在執行中（PID $(cat "$pidfile")）"
        return
    fi

    nohup "$VENV_PYTHON" "$@" >> "$logfile" 2>&1 &
    echo $! > "$pidfile"
    success "$name 已啟動（PID $!，log: logs/${name}.log）"
}

start_daemon "fetcher" \
    src/ingestion/timeseries_producer.py --interval 300

start_daemon "news_fetcher" \
    src/ingestion/real_news_fetcher.py --interval 600

start_daemon "community" \
    src/ingestion/community_sentiment.py --interval 900

if [ -n "${GEMINI_API_KEY:-}" ]; then
    start_daemon "ai_summarizer" \
        -m src.processing.ai_summarizer --interval 14400
else
    warn "GEMINI_API_KEY 未設定，略過 AI Summarizer（請在 .env 中設定後重跑）"
fi

# ── 步驟 3：FastAPI + Streamlit ───────────────────────────────
echo
echo -e "${BOLD}[3/3] 啟動 FastAPI 與 Streamlit Dashboard${NC}"

# FastAPI
FASTAPI_PID="$PIDS/fastapi.pid"
if [ -f "$FASTAPI_PID" ] && kill -0 "$(cat "$FASTAPI_PID")" 2>/dev/null; then
    warn "FastAPI 已在執行中（PID $(cat "$FASTAPI_PID")）"
else
    nohup "$SCRIPT_DIR/.venv/bin/uvicorn" \
        src.dashboard.api.main:app \
        --host 0.0.0.0 --port 8000 \
        >> "$LOGS/fastapi.log" 2>&1 &
    echo $! > "$FASTAPI_PID"
    success "FastAPI 已啟動（PID $!，log: logs/fastapi.log）"
fi

# Streamlit
STREAMLIT_PID="$PIDS/streamlit.pid"
if [ -f "$STREAMLIT_PID" ] && kill -0 "$(cat "$STREAMLIT_PID")" 2>/dev/null; then
    warn "Streamlit 已在執行中（PID $(cat "$STREAMLIT_PID")）"
else
    nohup "$SCRIPT_DIR/.venv/bin/streamlit" run \
        src/dashboard/app.py \
        --server.port 8501 \
        --server.headless true \
        --server.address 0.0.0.0 \
        >> "$LOGS/streamlit.log" 2>&1 &
    echo $! > "$STREAMLIT_PID"
    success "Streamlit 已啟動（PID $!，log: logs/streamlit.log）"
fi

# ── 完成 ──────────────────────────────────────────────────────
HOST_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")
echo
echo -e "${BOLD}======================================${NC}"
echo -e "${GREEN}${BOLD}  ✅ 所有服務已啟動完成${NC}"
echo -e "${BOLD}======================================${NC}"
echo -e "  Dashboard  : ${BLUE}http://${HOST_IP}:8501${NC}"
echo -e "  API Docs   : ${BLUE}http://${HOST_IP}:8000/docs${NC}"
echo -e "  Flink UI   : ${BLUE}http://${HOST_IP}:8081${NC}"
echo -e "  MinIO UI   : ${BLUE}http://${HOST_IP}:9001${NC}"
echo
echo -e "  Logs       : ${SCRIPT_DIR}/logs/"
echo -e "  停止服務   : ${YELLOW}./stop.sh${NC}"
echo
