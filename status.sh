#!/usr/bin/env bash
# ==============================================================
# ShipPulse — 查看所有服務狀態
# 使用方式：./status.sh
# ==============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PIDS="$SCRIPT_DIR/.pids"

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; GRAY='\033[0;90m'; NC='\033[0m'

running() { echo -e "  ${GREEN}● 執行中${NC}  $*"; }
stopped() { echo -e "  ${RED}○ 未執行${NC}  $*"; }
unknown() { echo -e "  ${YELLOW}? 未知${NC}    $*"; }

check_pid() {
    local name="$1"
    local display="$2"
    local pidfile="$PIDS/${name}.pid"
    if [ -f "$pidfile" ]; then
        local pid; pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            running "$display ${GRAY}(PID $pid)${NC}"
        else
            stopped "$display ${GRAY}(PID 檔存在但行程已死：$pid)${NC}"
        fi
    else
        stopped "$display"
    fi
}

check_http() {
    local url="$1"
    local label="$2"
    if curl -sf "$url" > /dev/null 2>&1; then
        running "$label ${GRAY}($url)${NC}"
    else
        stopped "$label ${GRAY}($url)${NC}"
    fi
}

echo -e "${BOLD}======================================${NC}"
echo -e "${BOLD}  ShipPulse — 服務狀態總覽${NC}"
echo -e "${BOLD}======================================${NC}"

echo
echo -e "${BOLD}── Docker 基礎設施 ─────────────────${NC}"
if command -v docker >/dev/null 2>&1; then
    for container in shipping-kafka shipping-es shipping-influxdb shipping-minio \
                     shipping-flink-jm shipping-flink-tm; do
        status=$(docker inspect -f '{{.State.Status}}' "$container" 2>/dev/null || echo "not_found")
        case "$status" in
            running) running "$container" ;;
            not_found) stopped "$container ${GRAY}(容器不存在)${NC}" ;;
            *) unknown "$container ${GRAY}(狀態: $status)${NC}" ;;
        esac
    done
else
    unknown "Docker 指令不可用"
fi

echo
echo -e "${BOLD}── 基礎設施 HTTP 端點 ──────────────${NC}"
check_http "http://localhost:9200"         "Elasticsearch      :9200"
check_http "http://localhost:8086/ping"    "InfluxDB           :8086"
check_http "http://localhost:9000/minio/health/live" "MinIO             :9000"
check_http "http://localhost:8081"         "Flink UI           :8081"

echo
echo -e "${BOLD}── Python 行程 ─────────────────────${NC}"
check_pid "fastapi"       "FastAPI (port 8000)"
check_pid "streamlit"     "Streamlit (port 8501)"
check_pid "fetcher"       "市場數據接入 (timeseries_producer)"
check_pid "news_fetcher"  "新聞接入 (real_news_fetcher)"
check_pid "community"     "社群情緒接入 (community_sentiment)"
check_pid "ai_summarizer" "AI 摘要 Daemon (ai_summarizer)"

echo
echo -e "${BOLD}── API 端點狀態 ─────────────────────${NC}"
check_http "http://localhost:8000/api/metrics/latest" "FastAPI /api/metrics/latest"
check_http "http://localhost:8000/api/ai/insights"    "FastAPI /api/ai/insights"
check_http "http://localhost:8501"                    "Streamlit Dashboard"

echo
echo -e "${BOLD}── 最新日誌尾 (logs/) ──────────────${NC}"
for logfile in fastapi streamlit fetcher news_fetcher community ai_summarizer; do
    f="$SCRIPT_DIR/logs/${logfile}.log"
    if [ -f "$f" ]; then
        last=$(tail -1 "$f" 2>/dev/null || true)
        echo -e "  ${GRAY}${logfile}.log:${NC} ${last:0:80}"
    fi
done

echo
