import asyncio
import time
import statistics
import traceback
from collections import defaultdict
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

# ================= 配置区域 =================
CONCURRENCY_LEVEL = 1  # 同时进行的并发请求数
TOTAL_REQUESTS = 200     # 总共要执行的请求数
TEST_URL = "https://github.com/kebijuelun/Awesome-LLM-Learning/tree/main/3.%E5%A4%A7%E8%AF%AD%E8%A8%80%E6%A8%A1%E5%9E%8B%E5%9F%BA%E7%A1%80%E7%9F%A5%E8%AF%86"
# ===========================================

class StressTester:
    def __init__(self, client, concurrency, total):
        self.client = client
        self.concurrency = concurrency
        self.total = total
        self.semaphore = asyncio.Semaphore(concurrency)
        self.results = []
        self.errors = defaultdict(int)
        self.completed_count = 0

    async def single_request(self, req_id):
        """执行单个请求并记录数据"""
        async with self.semaphore:  # 限制并发
            start_time = time.time()
            status = "failed"
            error_msg = None
            
            try:
                # 打印进度（可选，为了不刷屏每完成几个打印一次）
                # print(f"Starting request {req_id}...")
                # 调用 MCP 工具
                result = await self.client.call_tool_mcp(
                    "fetch_url",
                    {"url": [TEST_URL]}
                )
                import pdb;pdb.set_trace()
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
                
                # # 简单的验证逻辑：如果有返回内容且不报错视为成功
                # # 根据您的实际工具返回结构，这里可能需要调整判断条件
                # if result: 
                #     status = "success"
                # else:
                #     error_msg = "Empty result"
                    
            except Exception as e:
                error_msg = str(e)
                # 记录具体的错误类型以便分析
                error_type = type(e).__name__
                self.errors[f"{error_type}: {str(e)[:50]}..."] += 1
            
            duration = time.time() - start_time
            self.completed_count += 1
            print(f"[{self.completed_count}/{self.total}] Request {req_id}: {status} ({duration:.2f}s)")
            
            return {
                "id": req_id,
                "status": status,
                "duration": duration,
                "error": error_msg
            }

    async def run(self):
        print(f"🚀 开始压力测试: 总请求数={self.total}, 并发数={self.concurrency}")
        
        start_total = time.time()
        
        # 创建所有任务
        tasks = [self.single_request(i) for i in range(self.total)]
        
        # 并发执行
        self.results = await asyncio.gather(*tasks)
        
        end_total = time.time()
        total_duration = end_total - start_total
        
        self.print_report(total_duration)

    def print_report(self, total_duration):
        success_list = [r for r in self.results if r['status'] == 'success']
        failed_list = [r for r in self.results if r['status'] == 'failed']
        durations = [r['duration'] for r in success_list]

        print("\n" + "="*50)
        print("📊 测试报告 (Test Report)")
        print("="*50)
        print(f"总耗时: {total_duration:.2f} 秒")
        print(f"吞吐量 (QPS): {len(success_list) / total_duration:.2f} req/s")
        print("-" * 20)
        print(f"请求总数: {self.total}")
        print(f"成功: {len(success_list)} ({len(success_list)/self.total*100:.1f}%)")
        print(f"失败: {len(failed_list)} ({len(failed_list)/self.total*100:.1f}%)")
        
        if durations:
            print("-" * 20)
            print(f"平均耗时: {statistics.mean(durations):.4f} s")
            print(f"中位数耗时: {statistics.median(durations):.4f} s")
            print(f"P95 耗时: {statistics.quantiles(durations, n=20)[-1]:.4f} s")
            print(f"最快请求: {min(durations):.4f} s")
            print(f"最慢请求: {max(durations):.4f} s")
        
        if self.errors:
            print("-" * 20)
            print("❌ 错误分布:")
            for err, count in self.errors.items():
                print(f"  - {count}次: {err}")
        print("="*50)

async def main():
    # 配置 Transport
    transport = StdioTransport(
        command="bash",
        args=[
            "-c",
            "export PLAYWRIGHT_BROWSERS_PATH=/mnt/afs_agents/fengxuyu/workspace/mcp_tools/pw_browsers && "
            "uv run --isolated --no-project "
            "--with /mnt/afs_agents/fengxuyu/workspace/mcp_tools/dist/mcp_tools-0.38.1-py3-none-any.whl "
            "mcp-tools-server --config /mnt/afs_agents/fengxuyu/workspace/mcp_tools/mcp_tools/config_custom_fetch_2_img.yaml "
            "2>> /mnt/afs_agents/fengxuyu/workspace/mcp_tools/logs/mcp_server.log"
        ]
    )

    client = Client(transport)

    try:
        # 使用 client 上下文，确保连接保持打开
        async with client:
            # 预热一次（可选，防止冷启动影响第一次请求的统计）
            print("正在预热 Server...")
            await client.call_tool_mcp("fetch_url", {"url": [TEST_URL]})
            print("预热完成，开始测试...")

            tester = StressTester(client, CONCURRENCY_LEVEL, TOTAL_REQUESTS)
            await tester.run()
            
    except Exception as e:
        print(f"Fatal Error during test: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())