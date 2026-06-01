#!/bin/bash
set -euo pipefail

# =============================================================================
#  run_inference.sh — 启动 MCP 工具 + 推理
#
#  用法:
#    bash run_inference.sh
#    VLLM_PORT=8001 CONCURRENCY=8 bash run_inference.sh
# =============================================================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$PROJECT_DIR/.env" ]; then
  set -a
  source "$PROJECT_DIR/.env"
  set +a
fi
# ----------------------------- 可配置参数 -------------------------------------
VLLM_MODEL_NAME=${VLLM_MODEL_NAME:-Qwen3-VL-30B-A3B}
VLLM_HOST=${VLLM_HOST:-10.120.2.179}
VLLM_PORT=${VLLM_PORT:-8080}
API_KEY=${API_KEY:-EMPTY}

INPUT_FILE=${INPUT_FILE:-$PROJECT_DIR/data/BrowseComp_subset_debug.jsonl}
OUTPUT_FILE=${OUTPUT_FILE:-$PROJECT_DIR/outputs/results.jsonl}
CONCURRENCY=${CONCURRENCY:-10}
LIMIT=${LIMIT:-0}
THINK_MODE=${THINK_MODE:-true}

# ----------------------------- 环境变量 ---------------------------------------
export UV_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
export UV_CACHE_DIR=$PROJECT_DIR/mcp/.cache/uv
export PLAYWRIGHT_BROWSERS_PATH=$PROJECT_DIR/mcp/pw_browsers

MCP_WHL_PATH=$PROJECT_DIR/mcp/dist/mcp_tools-0.40.1-py3-none-any.whl
MCP_CONFIG_PATH=$PROJECT_DIR/mcp/mcp_tools/config_custom_fetch_2_img.yaml
export MCP_WHL_PATH MCP_CONFIG_PATH
export MCP_LOG_FILE=$PROJECT_DIR/logs/mcp_server.log

# 让 Python 在 mcp/ 目录下找到 mcp_tools 包
export PYTHONPATH="$PROJECT_DIR/mcp:${PYTHONPATH:-}"

export VLLM_MODEL_NAME

# ----------------------------- MCP 启动 ---------------------------------------
MCP_MODE=${MCP_MODE:-embedded-stdio}
MCP_HOST=127.0.0.1
MCP_START_PORT=18601
MCP_PORT_COUNT=1

MCP_PIDS=""
MCP_URLS=""

cleanup() {
  if [ -n "$MCP_PIDS" ]; then
    echo "[cleanup] Stopping MCP servers..."
    kill $MCP_PIDS 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

mkdir -p "$PROJECT_DIR/logs"

if [ "$MCP_MODE" = "external-sse" ]; then
  echo "============================================"
  echo " Starting MCP server (external-sse)"
  echo "============================================"

  for idx in $(seq 0 $((MCP_PORT_COUNT - 1))); do
    port=$((MCP_START_PORT + idx))
    mcp_log="$PROJECT_DIR/logs/mcp_node_${port}.log"
    echo "  Launching MCP on ${MCP_HOST}:${port}"

    uv run --isolated --no-project --with "$MCP_WHL_PATH" mcp-tools-server \
      --config "$MCP_CONFIG_PATH" \
      --host "$MCP_HOST" \
      --port "$port" \
      --transport sse \
      > "$mcp_log" 2>&1 &

    pid=$!
    MCP_PIDS="$MCP_PIDS $pid"

    url="http://${MCP_HOST}:${port}/sse/"
    MCP_URLS="${MCP_URLS:+$MCP_URLS,}$url"
  done

  echo "Waiting for MCP servers..."
  IFS=',' read -ra URLS <<< "$MCP_URLS"
  for url in "${URLS[@]}"; do
    port="${url##*:}"; port="${port%/sse/}"
    for retry in $(seq 1 180); do
      if python -c "import socket,sys; s=socket.socket(); s.settimeout(1.5); s.connect(('$MCP_HOST',${port})); s.close()" 2>/dev/null; then
        echo "  ✅ Ready: $url"
        break
      fi
      if [ "$retry" -eq 180 ]; then
        echo "  ❌ MCP not ready: $url"; tail -30 "$PROJECT_DIR/logs/mcp_node_${port}.log"; exit 1
      fi
      sleep 1
    done
  done

  echo "MCP_URLS=$MCP_URLS"
else
  echo "MCP mode: embedded-stdio (auto-launched per call)"
fi

# =============================================================================
# 推理
# =============================================================================
echo "============================================"
echo " Running inference"
echo "   Input : $INPUT_FILE"
echo "   Output: $OUTPUT_FILE"
echo "   API   : http://${VLLM_HOST}:${VLLM_PORT}/v1"
echo "   Model : $VLLM_MODEL_NAME"
echo "   Concurrency: $CONCURRENCY"
echo "============================================"

mkdir -p "$(dirname "$OUTPUT_FILE")"

EXTRA_ARGS=""
if [ "$LIMIT" -gt 0 ] 2>/dev/null; then
  EXTRA_ARGS="$EXTRA_ARGS --limit $LIMIT"
fi
if [ "$THINK_MODE" = "false" ]; then
  EXTRA_ARGS="$EXTRA_ARGS --no-think"
fi

python "$PROJECT_DIR/run_inference.py" \
  --input "$INPUT_FILE" \
  --output "$OUTPUT_FILE" \
  --api-base "http://${VLLM_HOST}:${VLLM_PORT}/v1" \
  --api-key "${API_KEY:-dummy}" \
  --concurrency "$CONCURRENCY" \
  $EXTRA_ARGS

echo "✅ Done. Results saved to: $OUTPUT_FILE"
