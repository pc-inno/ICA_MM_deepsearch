import asyncio
import json
import time
from fastmcp import Client
from fastmcp.client.transports import SSETransport

# 并发数配置
CONCURRENCY_LEVEL = 5

async def call_search(index, client, queries):
    """单个请求任务：适配 Search Batch 接口 (输入 query 列表，解析嵌套 text 列表)"""
    start_time = time.time()
    try:
        print(f"🚀 [Task {index}] Sending search request for: {queries}...")
        arguments={'query': ['rural district Qazvin province southern foothills of the Alborz Mountains 150 km northwest of Tehran populated place', 'village in Qazvin province near Alborz foothills 150 km from Tehran'], 'sandbox_id': '171a614afbd3423ba7b0d5cb5f88892b', 'question': 'Are a populated place in the rural district of Qazvin Province, situated in the northwestern part of Iran at the southern foothills of the Alborz Mountains and approximately 150 km northwest of Tehran, and a city in East Azerbaijan Province—located in the same country as the provincial divisions bordering the Caspian Sea to the south and sharing administrative classification within Iran’s northwestern region—both located in the same country?', 'is_self_summary': True, 'model_name': 'RUN_hfs/qwen3_30b_a3b_Thinking_2507_vit_1b_v2_2_browse_2_sft_v9_3_4_3_1200hf', 'addresses': ['10.119.18.50:44403', '10.119.18.50:53097'], 'start_idx': 0}
        arguments = {'query': ['filming location Friday the 13th 1980 Sean S. Cunningham', 'Camp Crystal Lake real location', 'Friday the 13th 1980 set construction', 'where was Friday the 13th 1980 filmed', 'Friday the 13th original movie location'], "start_idx":5}
        # =================================================================
        # [适配点 1] 参数名对应 SearchTool 的 schema: 'query' (List[str])
        # =================================================================
        result = await client.call_tool_mcp(
            "web_search", 
            arguments=arguments, 
            timeout=60 # 搜索通常比截图快，但保留充足时间
        )
        import pdb;pdb.set_trace()
        
        # 获取 Tool 返回的 JSON 字符串
        raw_response = result.content[0].text
        
        try:
            response_data = json.loads(raw_response)
        except json.JSONDecodeError:
            print(f"❌ [Task {index}] JSON Decode Error. Raw response: {raw_response[:100]}...")
            return False

        # =================================================================
        # [适配点 2] 解析结构
        # text: [[res1, res2...], [res1...]] (对应输入的 query 列表)
        # image: [] (搜索工具返回空列表)
        # =================================================================
        nested_results_list = response_data.get("text", [])
        image_list = response_data.get("image", []) # 预期为空
        import pdb;pdb.set_trace()
        if not nested_results_list:
            print(f"⚠️ [Task {index}] Finished but 'text' result list is empty.")
            return False

        # 统计总结果数
        total_items = sum(len(res) for res in nested_results_list)
        print(f"📦 [Task {index}] Received results for {len(nested_results_list)} queries, Total {total_items} items.")

        # =================================================================
        # [适配点 3] 遍历并打印结果摘要
        # =================================================================
        for q_idx, results in enumerate(nested_results_list):
            query_str = queries[q_idx]
            print(f"  🔎 Query [{q_idx}]: '{query_str}' -> Got {len(results)} results")
            
            # 打印前 1 个结果作为验证
            if results:
                first_res = results[0]
                title = first_res.get('title', 'No Title')
                link = first_res.get('link', 'No Link')
                print(f"     👉 Top 1: {title} ({link})")

        duration = time.time() - start_time
        print(f"✅ [Task {index}] Success! Time: {duration:.2f}s")
        return True

    except Exception as e:
        print(f"❌ [Task {index}] Failed: {str(e)}")
        return False

async def stress_test():
    # 请确认端口号 (通常是 8081)
    transport = SSETransport(url="http://localhost:8001/sse")
    client = Client(transport)
    
    # 测试数据：每个任务包含一个查询列表
    test_queries_batch = [
        ["latest ai news", "python 3.13 features"],
        ["weather in New York", "weather in London"],
        ["playwright python tutorial"],
        ["nvidia stock price", "apple stock price", "tesla stock price"], # 批量3个
        ["how to make coffee"]
    ]

    # 循环填充以满足并发数
    while len(test_queries_batch) < CONCURRENCY_LEVEL:
        test_queries_batch.extend(test_queries_batch)
    
    test_queries_batch = test_queries_batch[:CONCURRENCY_LEVEL]

    print(f"🔥 Starting Search Stress Test with {CONCURRENCY_LEVEL} concurrent requests...")
    
    async with client:
        tasks = []
        for i in range(CONCURRENCY_LEVEL):
            queries = test_queries_batch[i]
            # 加入一点随机延迟
            await asyncio.sleep(0.1) 
            tasks.append(call_search(i, client, queries))
        
        results = await asyncio.gather(*tasks)
        
        success_count = sum(1 for r in results if r)
        print(f"\n📊 Test Summary: {success_count}/{CONCURRENCY_LEVEL} succeeded.")

if __name__ == "__main__":
    asyncio.run(stress_test())