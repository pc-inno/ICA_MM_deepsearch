import asyncio
import time
import os
from fastmcp import Client
from fastmcp.client.transports import SSETransport

# =================配置区域=================
# 结果保存路径
SAVE_DIR = "./fetch_results"
os.makedirs(SAVE_DIR, exist_ok=True)

# MCP 服务器地址
SERVER_SSE_URL = "http://localhost:8001/sse"
# =========================================

async def call_fetch_task(index, client, goal, url):
    """单个抓取任务：调用 fetch 工具并保存文本结果"""
    start_time = time.time()
    try:
        print(f"🚀 [Task {index}] Sending request for goal: '{goal}'...")

        args = {
            "goal": goal,
            "url": url
        }

        result = await client.call_tool_mcp(
            "fetch_url", 
            arguments=args, 
            timeout=60 
        )

        if not result.content:
            print(f"⚠️ [Task {index}] Finished but content is empty.")
            return False
            
        final_text = result.content[0].text
        import pdb;pdb.set_trace()
        content_length = len(final_text)
        print(f"📦 [Task {index}] Received response. Length: {content_length} chars.")

        filename = f"{SAVE_DIR}/task_{index}_{int(time.time())}.md"
        
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"# Task {index} Result\n")
                f.write(f"- **Query**: {query}\n")
                f.write(f"- **URLs**: {urls}\n")
                f.write(f"- **Time**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("-" * 40 + "\n\n")
                f.write(final_text)
            
            print(f"💾 [Task {index}] Saved to {filename}")
            
        except Exception as e:
            print(f"❌ [Task {index}] Failed to save file: {e}")
            return False

        duration = time.time() - start_time
        print(f"✅ [Task {index}] Success! Time: {duration:.2f}s")
        return True

    except Exception as e:
        print(f"❌ [Task {index}] Failed: {str(e)}")
        return False

async def sequential_test():
    print(f"🔌 Connecting to SSE Server at {SERVER_SSE_URL}...")
    
    try:
        transport = SSETransport(url=SERVER_SSE_URL)
        client = Client(transport)
    except Exception as e:
        print(f"❌ Connection setup failed: {e}")
        return

    # 测试数据准备
    test_scenarios = [
        {
            "goal": "LLM agent architecture",
            "url": ["https://lilianweng.github.io/posts/2023-06-23-agent/"]
        },
        {
            "goal": "Python asyncio tutorial",
            "url": ["https://docs.python.org/3/library/asyncio.html"]
        },
        {
            "goal": "Transformer model attention mechanism",
            "url": ["https://arxiv.org/abs/1706.03762", "https://jalammar.github.io/illustrated-transformer/"]
        }
    ]

    print("🔥 Starting Sequential Test...")
    
    async with client:
        success_count = 0
        for i, scenario in enumerate(test_scenarios):
            result = await call_fetch_task(
                index=i, 
                client=client, 
                goal=scenario["goal"], 
                url=scenario["url"]
            )
            if result:
                success_count += 1
        
        print(f"\n📊 Test Summary: {success_count}/{len(test_scenarios)} succeeded.")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(sequential_test())
