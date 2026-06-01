# import asyncio
# import base64
# import json
# import time
# import os
# from fastmcp import Client
# from fastmcp.client.transports import SSETransport

# # 并发数配置
# CONCURRENCY_LEVEL = 10 

# # 图片保存路径
# SAVE_DIR = "/mnt/afs/fengxuyu/workspace/hqy_workspace/feng/mmrl/mcp_tools/tests/screenshots"
# os.makedirs(SAVE_DIR, exist_ok=True)

# async def call_screenshot(index, client, url):
#     """单个请求任务：适配 Batch 接口 (输入 urls 列表，解析嵌套 image 列表)"""
#     start_time = time.time()
#     try:
#         print(f"🚀 [Task {index}] Sending request for {url}...")
        
#         # =================================================================
#         # [修改点 1] 参数名改为 'urls'，且必须是列表
#         # 即使只测试一个 URL，也要写成 [url]
#         # =================================================================
#         a = {'urls': ['https://www.statmuse.com/nba/ask/highest-scoring-games-by-lebron']}
#         result = await client.call_tool_mcp(
#             "fetch_url", 
#             arguments=a, 
#             timeout=120
#         )
        
#         # 获取 Tool 返回的 JSON 字符串
#         raw_response = result.content[0].text
#         import pdb;pdb.set_trace()
#         try:
#             response_data = json.loads(raw_response)
#         except json.JSONDecodeError:
#             print(f"❌ [Task {index}] JSON Decode Error. Raw response: {raw_response[:100]}...")
#             return False

#         # =================================================================
#         # [修改点 2] 解析嵌套结构
#         # image 现在的结构是: [[slice1, slice2], [slice1]] (对应输入的 url 列表)
#         # =================================================================
#         nested_images_list = response_data.get("image", [])
#         text_json = response_data.get("text", "")
#         import pdb;pdb.set_trace()
#         if not nested_images_list:
#             print(f"⚠️ [Task {index}] Finished but 'image' list is empty.")
#             return False

#         # 统计总切片数用于日志
#         total_slices = sum(len(slices) for slices in nested_images_list)
#         print(f"📦 [Task {index}] Received {len(nested_images_list)} URL results, Total {total_slices} slices.")

#         # =================================================================
#         # [修改点 3] 双层循环保存图片
#         # 外层循环：遍历 URL (这里因为我们只发了1个，所以只有1次)
#         # 内层循环：遍历该 URL 的切片
#         # =================================================================
#         saved_count = 0
        
#         for url_idx, slices in enumerate(nested_images_list):
#             for slice_idx, img_item in enumerate(slices):
#                 try:
#                     # 获取图片数据
#                     img_content = img_item.get("image")
                    
#                     if isinstance(img_content, str):
#                         img_bytes = base64.b64decode(img_content)
#                     elif isinstance(img_content, bytes):
#                         img_bytes = img_content
#                     elif isinstance(img_content, list):
#                         img_bytes = bytes(img_content)
#                     else:
#                         print(f"❌ [Task {index}] Unknown image content type: {type(img_content)}")
#                         continue

#                     # 文件名格式：TaskID_UrlIndex_SliceIndex.jpg
#                     filename = f"{SAVE_DIR}/task_{index}_url_{url_idx}_slice_{slice_idx}.jpg"
                    
#                     with open(filename, "wb") as f:
#                         f.write(img_bytes)
                    
#                     saved_count += 1
                    
#                 except Exception as e:
#                     print(f"❌ [Task {index}] Failed to save url {url_idx} slice {slice_idx}: {e}")

#         duration = time.time() - start_time
#         print(f"✅ [Task {index}] Success! Saved {saved_count} images. Time: {duration:.2f}s")
#         return True

#     except Exception as e:
#         print(f"❌ [Task {index}] Failed: {str(e)}")
#         return False

# async def stress_test():
#     # 请确认端口号 (8001 或 8081)
#     transport = SSETransport(url="http://localhost:8081/sse")
#     client = Client(transport)
    
#     test_urls = [[
#         "https://github.com",
#         "https://huggingface.co",
#         "https://arxiv.org/html/2510.18234v1", # 长文测试
#     ] for _ in range(5)]

#     print(f"🔥 Starting Stress Test with {CONCURRENCY_LEVEL} concurrent requests...")
    
#     async with client:
#         tasks = []
#         for i in range(CONCURRENCY_LEVEL):
#             url = test_urls[i % len(test_urls)]
#             await asyncio.sleep(0.2) 
#             tasks.append(call_screenshot(i, client, url))
        
#         results = await asyncio.gather(*tasks)
        
#         success_count = sum(1 for r in results if r)
#         print(f"\n📊 Test Summary: {success_count}/{CONCURRENCY_LEVEL} succeeded.")

# if __name__ == "__main__":
#     asyncio.run(stress_test())
import asyncio
import json
import pdb
from fastmcp import Client
# from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.client.transports import SSETransport

def call_fetch_url_sync():
    # 1. 配置服务器地址 (使用 StreamableHttpTransport 对应的 /mcp 路径)
    mcp_url = "http://localhost:8001/sse" 
    
    # 2. 准备参数
    tool_name = "fetch_url"
    arguments = {
        "urls": ["https://www.zhihu.com/search?q=%E4%B8%9C%E9%83%A8%E6%88%98%E5%8C%BA%E5%BC%80%E5%B1%95%E6%AD%A3%E4%B9%89%E4%BD%BF%E5%91%BD-2025%E6%BC%94%E4%B9%A0&search_source=Trending&utm_content=search_hot&utm_medium=organic&utm_source=zhihu&type=content"]
    }

    # 3. 定义内部异步逻辑
    async def _run():
        # 初始化客户端 (使用之前模板中的 StreamableHttpTransport)
        transport = SSETransport(url=mcp_url)
        client = Client(transport)
        
        try:
            async with client:
                # 调用工具
                result = await client.call_tool(
                    name=tool_name, 
                    arguments=arguments
                )
                return result
        except Exception as e:
            print(f"❌ 内部调用出错: {e}")
            raise e

    # 4. 使用 asyncio.run 实现“同步”阻塞调用
    try:
        print(f"📡 正在调用 {tool_name}...")
        result = asyncio.run(_run())
        
        # 5. 处理结果
        if result and result.content:
            raw_response = result.content[0].text
            try:
                # 尝试解析 JSON (集成你的解析逻辑)
                # 根据 ToolOutput，这里的 raw_response 应该是 {"text": "...", "image": ...} 的 JSON 字符串
                response_data = json.loads(raw_response)
                
                nested_images_list = response_data.get("image", [])
                text_json = response_data.get("text", "")
                
                print(f"✅ 解析成功: 包含 {len(nested_images_list)} 组图片")
                
                # 进入断点调试
                print("⏸️  进入 PDB 调试模式...")

            except json.JSONDecodeError:
                print(f"❌ JSON Decode Error. Raw response: {raw_response[:100]}...")
                return False

            print("✅ 流程结束，原始返回预览：")
            print(raw_response[:500] + "...") 
        else:
            print("⚠️ 返回结果为空")
            
    except Exception as e:
        print(f"❌ 调用失败: {e}")

if __name__ == "__main__":
    call_fetch_url_sync()