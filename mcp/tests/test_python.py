import json
import re
from fastmcp import Client
from fastmcp.client.transports import SSETransport, StdioTransport 
import asyncio 

async def test():
    transport = SSETransport(url="http://localhost:8001/sse")
    client = Client(transport)
    
    async with client:
        # 首先列出可用的工具
        # print("Listing available tools...")
        tools_resp = await client.list_tools_mcp()
        print(f"Available tools: {[tool.name for tool in tools_resp.tools]}")

        result = await client.call_tool_mcp(
            "python_execute",
            {
                "code": """
a = 1
b = 2
print("Sum:", a + b)
""", 
              "sandbox_id": 'sandbox_test',
              },
            timeout=60,
        )
        print("\nPython execute tool result:")
        print(result)
        if not result or not result.content:
            print("⚠️ Empty result")
            return
        tool_data = result.content[0].text
        response_data = json.loads(tool_data)
        stdout = response_data.get("stdout", "")
        stderr = response_data.get("stderr", "")
        return_code = response_data.get("return_code")
        print(f"Return Code: {return_code}")
        print(f"STDOUT:\n{stdout}")
        print(f"STDERR:\n{stderr}")


if __name__ == "__main__":
    asyncio.run(test())