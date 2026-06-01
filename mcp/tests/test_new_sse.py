import asyncio
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.client.transports import SSETransport
import base64
import json,os
# 图片保存路径
SAVE_DIR = "/mnt/afs/fengxuyu/workspace/hqy_workspace/feng/mmrl/yuannang_mcp_tools/mcp_tools/screenshots"
os.makedirs(SAVE_DIR, exist_ok=True)

def call_fetch_url_sync():
    # 1. 配置服务器地址
    mcp_url = "http://localhost:8001/sse" 
    
    # 2. 准备参数 (注意：必须符合你工具定义的 Schema，这里是 urls 列表)
    tool_name = "fetch_url"
    arguments = {
        "urls": ["https://arxiv.org/html/1706.03762v7"]
    }

    # 3. 定义内部异步逻辑
    async def _run():
        # 初始化客户端
        transport = SSETransport(url=mcp_url)
        client = Client(transport)
        # import pdb;pdb.set_trace()
        try:
            async with client:
                # 调用工具
                result = await asyncio.wait_for(client.call_tool(
                    name=tool_name, 
                    arguments=arguments
                ),
                timeout=30
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
            
    except Exception as e:
        print(f"❌ 调用失败: {e}")

if __name__ == "__main__":
    call_fetch_url_sync()