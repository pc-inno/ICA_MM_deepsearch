# mcp/http_api.py
from contextlib import asynccontextmanager
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .server import MCPToolsServer  
from ..sandbox.manager import sandbox_manager


class ToolCallBody(BaseModel):
    name: str
    arguments: Dict[str, Any]
    sandbox_id: str


def create_http_app(server: MCPToolsServer) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        """确保服务启动时工具已加载"""
        await server._load_tools()
        yield

    app = FastAPI(
        title="MCP-Tools-HTTP",
        version="0.1.0",
        lifespan=lifespan,
    )

    # ---------------- 工具列表 ----------------
    @app.get("/tools")
    async def list_tools() -> List[Dict[str, Any]]:
        """返回当前已注册且启用的工具列表"""
        tools = []
        for name, instance in server.tool_registry.get_all_tools().items():
            if not server._is_tool_enabled(name):
                continue
            schema = instance.get_schema()
            tools.append(
                {
                    "name": schema.name,
                    "description": schema.description,
                    "inputSchema": schema.input_schema,
                }
            )
        return tools

    # ---------------- 工具调用 ----------------
    @app.post("/tools/call")
    async def call_tool(body: ToolCallBody) -> Dict[str, Any]:
        """
        异步执行工具，返回统一格式
        {"success":bool, "data":Any, "error":str}
        """
        name = body.name
        arguments = body.arguments
        sandbox_id = body.sandbox_id

        # 1. 工具存在性 & 启用检查
        tool_instance = server.tool_registry.get_tool(name)
        if not tool_instance:
            raise HTTPException(status_code=404, detail=f"Tool '{name}' not found")
        if not server._is_tool_enabled(name):
            raise HTTPException(status_code=403, detail=f"Tool '{name}' is disabled")

        # 2. 若工具需要 sandbox，提前初始化
        if tool_instance.requires_sandbox:
            if not sandbox_id:
                raise HTTPException(status_code=400, detail="sandbox_id is required for this tool")
            sandbox_manager.get_sandbox(sandbox_id)

        # 3. 执行
        try:
            result = await tool_instance(arguments, sandbox_id=sandbox_id)   
        except Exception as exc:
            server.logger.exception("Tool execution error")
            return {"success": False, "data": None, "error": str(exc)}

        # 4. 返回
        if result["success"]:
            return {"success": True, "data": result.get("data"), "error": None}
        else:
            return {"success": False, "data": None, "error": result.get("error")}

    @app.get("/health")
    def health() -> Dict[str, Any]:
        return {"status": "ok", "info": server.get_server_info()}

    return app