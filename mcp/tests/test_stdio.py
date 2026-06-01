# from fastmcp import Client
from fastmcp.client.transports import SSETransport, StdioTransport ,StreamableHttpTransport
from fastmcp import Client
# from fastmcp.client.transports import SSETransport
import asyncio 
import base64
import json,os
SAVE_DIR = "/mnt/afs_agents/fengxuyu/workspace/mcp_tools/screenshots"
# test
async def test():
    # 使用 StdioTransport 连接到 MCP 服务器
    transport = StdioTransport(
        command="bash",
        args=[
            "-c",
            "export PLAYWRIGHT_BROWSERS_PATH=/mnt/afs_agents/fengxuyu/workspace/mcp_tools/pw_browsers && "
            "UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple uv run --isolated --no-project "
            "--with /mnt/afs_agents/fengxuyu/workspace/mcp_tools/dist/mcp_tools-0.38.1-py3-none-any.whl "
            "mcp-tools-server --config /mnt/afs_agents/fengxuyu/workspace/mcp_tools/mcp_tools/config_custom_fetch_2_img.yaml "
            "2>> /mnt/afs_agents/fengxuyu/workspace/mcp_tools/logs/mcp_server——new.log"
        ]
    )

    client = Client(transport)
    # transport = SSETransport(url="http://localhost:8001/sse")
    # client = Client(transport)
    
    async def temp(client):
        async with client:

            import time
            start = time.time()
            result = await client.call_tool_mcp(
                "fetch_url",
                {
                    "url": ["https://arxiv.org/html/2510.14967v1#S4"]
                },
            )
            print(f"📡 调用成功...")
            # 5. 打印结果
            if result and result.content:
                # 获取 Tool 返回的 JSON 字符串
                raw_response = result.content[0].text
                try:
                    response_data = json.loads(raw_response)
                except json.JSONDecodeError:
                    print(f"❌ [Task] JSON Decode Error. Raw response: {raw_response[:100]}...")
                    return False

                # =================================================================
                # [修改点 2] 解析嵌套结构
                # image 现在的结构是: [[slice1, slice2], [slice1]] (对应输入的 url 列表)
                # =================================================================
                nested_images_list = response_data.get("image", [])
                text_json = response_data.get("text", "")
                for url_idx, slices in enumerate(nested_images_list):
                    for slice_idx, img_item in enumerate(slices):
                        try:
                            # 获取图片数据
                            img_content = img_item.get("image")
                            
                            if isinstance(img_content, str):
                                img_bytes = base64.b64decode(img_content)
                            elif isinstance(img_content, bytes):
                                img_bytes = img_content
                            elif isinstance(img_content, list):
                                img_bytes = bytes(img_content)
                            else:
                                print(f"❌ [Task ] Unknown image content type: {type(img_content)}")
                                continue

                            # 文件名格式：TaskID_UrlIndex_SliceIndex.jpg
                            filename = f"{SAVE_DIR}/task__url_{url_idx}_slice_{slice_idx}.jpg"
                            
                            with open(filename, "wb") as f:
                                f.write(img_bytes)
                            
                        except Exception as e:
                            print(f"❌ [Task] Failed to save url {url_idx} slice {slice_idx}: {e}")

                print("✅ 调用成功，返回结果：")
                # 打印文本内容（根据你的工具返回，可能是 JSON 字符串）
                print(result.content[0].text[:500] + "...") # 只打印前500字符避免刷屏
            else:
                print("⚠️ 返回结果为空")
    
    try:
        await temp(client)
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(test())
