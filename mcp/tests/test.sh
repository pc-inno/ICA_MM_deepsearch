#!/bin/bash
set -e
# 1. 激活环境 (为了能找到 playwright 命令)
export PATH=/mnt/afs1/luojiapeng/miniconda3/bin:$PATH
source activate
conda activate /mnt/afs/lianghongyu/.conda/envs/agent

# cd /mnt/afs/fengxuyu/workspace/hqy_workspace/feng/mmrl/mcp_tools
# uv sync
# source .venv/bin/activate
# uv add playwright chardet
# mcp-tools-server --config /mnt/afs/fengxuyu/workspace/hqy_workspace/feng/mmrl/mcp_tools/config_custom.yaml
# 2. 执行自动安装依赖命令
# 这会自动调用 apt-get 安装缺失的 libgbm, libnss 等所有库
pip install fastmcp
playwright install-deps

# --- 2. Playwright 配置 ---
# 依然建议把浏览器下载到当前目录，方便管理且不占系统盘
export PLAYWRIGHT_BROWSERS_PATH=$(pwd)/pw_browsers

# 安装浏览器二进制文件 (Chromium)
# 这一步很快，如果已经下过会自动跳过
echo "正在检查 Playwright 浏览器..."
playwright install chromium

# --- 3. 运行服务 ---
LOG_DIR=logs
mkdir -p $LOG_DIR
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

echo "开始运行服务..."

# 使用 -u 实时输出日志

python -u /mnt/afs/fengxuyu/workspace/hqy_workspace/feng/mmrl/mcp_tools/tests/test_sse.py \
  | tee "$LOG_DIR/run_${TIMESTAMP}.log"
