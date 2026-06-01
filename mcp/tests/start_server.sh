cd /mnt/afs/fengxuyu/workspace/hqy_workspace/feng/mmrl/yuannang_mcp_tools/mcp_tools
uv sync
# uv add fetch_url_package tiktoken
source .venv/bin/activate
# uv add playwright==1.51.0 chardet Pillow
export PLAYWRIGHT_BROWSERS_PATH=/mnt/afs_agents/fengxuyu/workspace/mcp_tools/pw_browsers

mcp-tools-server --config /mnt/afs/fengxuyu/workspace/hqy_workspace/feng/mmrl/yuannang_mcp_tools/mcp_tools/mcp_tools/config_custom.yaml
# 快照工具
mcp-tools-server --config /mnt/afs_agents/fengxuyu/workspace/mcp_tools/mcp_tools/config_custom_fetch_2_img.yaml