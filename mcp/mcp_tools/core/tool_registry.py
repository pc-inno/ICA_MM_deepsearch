"""Tool registry for managing available tools."""

from typing import Dict, Optional
from .base_tool import BaseTool


class ToolRegistry:
    """Registry for managing and accessing MCP tools."""
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
    
    def register_tool(self, tool: BaseTool):
        """Register a new tool."""
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        
        self._tools[tool.name] = tool
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def get_all_tools(self) -> Dict[str, BaseTool]:
        """Get all registered tools."""
        return self._tools.copy()
    
    def list_tool_names(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())
    
    def unregister_tool(self, name: str) -> bool:
        """Unregister a tool."""
        if name in self._tools:
            del self._tools[name]
            return True
        return False
    
    def clear(self):
        """Clear all registered tools."""
        self._tools.clear()