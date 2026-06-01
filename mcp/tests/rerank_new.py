import asyncio
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
import base64
import json,os

def call_fetch_url_sync():
    # 1. 配置服务器地址
    mcp_url = "http://localhost:8001/mcp" 
    
    # 2. 准备参数 (注意：必须符合你工具定义的 Schema，这里是 urls 列表)
    tool_name = "fetch_url"
    arguments = {
            "goal": "Transformer model attention mechanism",
            "url": ["https://arxiv.org/abs/1706.03762", "https://jalammar.github.io/illustrated-transformer/"]
        }

    # 3. 定义内部异步逻辑
    async def _run():
        # 初始化客户端
        transport = StreamableHttpTransport(url=mcp_url)
        client = Client(transport)
        # import pdb;pdb.set_trace()
        try:
            async with client:
                # 调用工具
                result = await client.call_tool(
                    name=tool_name, 
                    arguments=arguments
                )
                return result
        except Exception as e:
            print(e)

    # 4. 使用 asyncio.run 实现“同步”阻塞调用
    try:
        print(f"📡 正在调用 {tool_name}...")
        result = asyncio.run(_run())
        print(f"📡 调用成功 {tool_name}...")
        # 5. 打印结果
        if result and result.content:
            # 获取 Tool 返回的 JSON 字符串
            raw_response = result.content[0].text
            try:
                response_data = json.loads(raw_response)
                import pdb;pdb.set_trace()
            except json.JSONDecodeError:
                print(f"❌ [Task] JSON Decode Error. Raw response: {raw_response[:100]}...")
                return False
    except Exception as e:
        print(f"❌ 调用失败: {e}")

if __name__ == "__main__":
    call_fetch_url_sync()