#!/usr/bin/env bash
# ==============================================================
# ShipPulse — 一鍵關閉所有服務
# 使用方式：./stop.sh
#           ./stop.sh --keep-docker   （只停 Python，保留 Docker）
# ==============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PIDS="$SCRIPT_DIR/.pids"
KEEP_DOCKER=false

# 解析旗標
for arg in "$@"; do
    case "$arg" in
        --keep-docker) KEEP_DOCKER=true ;;
    esac
done

# ── 顏色輸出 ──────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

success() { echo -e "${GREEN}[  ✓ ]${NC} $*"; }
warn()    { echo -e "${YELLOW}[ -- ]${NC} $*"; }

echo -e "${BOLD}======================================${NC}"
echo -e "${BOLD}  ShipPulse — 停止所有服務${NC}"
echo -e "${BOLD}======================================${NC}"

# ── 步驟 1：停止 Python 行程 ──────────────────────────────────
echo
echo -e "${BOLD}[1/2] 停止 Python 服務${NC}"

PYTHON_PROCS=(fastapi streamlit fetcher news_fetcher community ai_summarizer)

for name in "${PYTHON_PROCS[@]}"; do
    pidfile="$PIDS/${name}.pid"
    if [ -f "$pidfile" ]; then
        pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null && success "已停止 $name（PID $pid）" \
                || warn "無法傳送 SIGTERM 給 $name（PID $pid），嘗試 SIGKILL"
            # 給 2 秒讓行程正常結束，否則強制終止
            sleep 0.5
            if kill -0 "$pid" 2>/dev/null; then
                sleep 1.5
                kill -9 "$pid" 2>/dev/null || true
                warn "已強制終止 $name（SIGKILL）"
            fi
        else
            warn "$name 的 PID 檔存在但行程不在（PID $pid 已結束）"
        fi
        rm -f "$pidfile"
    fi
done

# 補網：搜尋殘留的 uvicorn / streamlit 行程（以防 PID 檔遺失）
for pat in "uvicorn src.dashboard" "streamlit run src/dashboard" \
           "src/ingestion/timeseries_producer" "src/ingestion/real_news_fetcher" \
           "src/ingestion/community_sentiment" "src.processing.ai_summarizer"; do
    pids_found=$(pgrep -f "$pat" 2>/dev/null || true)
    if [ -n "$pids_found" ]; then
        echo "$pids_found" | xargs kill 2>/dev/null || true
        warn "已清理殘留行程：$pat"
    fi
done

success "Python 服務已全部停止"

# ── 步驟 2：停止 Docker Compose ──────────────────────────────
echo
if [ "$KEEP_DOCKER" = true ]; then
    warn "已跳過 Docker Compose 停止（--keep-docker）"
else
    echo -e "${BOLD}[2/2] 停止 Docker Compose 基礎設施${NC}"
    docker compose -f deploy/docker-compose.yml down
    success "Docker Compose 已停止"
fi

# ── 完成 ──────────────────────────────────────────────────────
echo
echo -e "${BOLD}======================================${NC}"
echo -e "${GREEN}${BOLD}  ✅ 所有服務已停止${NC}"
echo -e "${BOLD}======================================${NC}"
if [ "$KEEP_DOCKER" = true ]; then
    echo -e "  ${YELLOW}Docker 容器仍在執行中（--keep-docker）${NC}"
    echo -e "  完整關閉請執行：${YELLOW}docker compose -f deploy/docker-compose.yml down${NC}"
fi
echo
