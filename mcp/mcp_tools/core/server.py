"""MCP Server implementation for MCP Tools Framework."""

import asyncio
import logging
from typing import Dict, Any, List, Optional
import json

from .base_tool import BaseTool
from .tool_registry import ToolRegistry
from ..config.loader import config_loader
from ..sandbox.manager import sandbox_manager


class MCPToolsServer:
    """Main MCP server that manages tools and sandbox operations.
    
    Uses FastMCP (HTTP/SSE) transport mode.
    """
    
    def __init__(self, transport: str = "stdio"):
        self.config = config_loader.load_config()
        self.tool_registry = ToolRegistry()
        self.logger = logging.getLogger(__name__)
        
        # FastMCP adapter will be initialized lazily
        self._fastmcp_adapter = None
        self.transport = transport
    
    def _is_tool_enabled(self, tool_name: str) -> bool:
        """Check if a tool is enabled in configuration."""
        tool_config = self.config.tools.get(tool_name)
        return tool_config is None or tool_config.enabled
    
    def register_tool(self, tool: BaseTool):
        """Register a new tool with the server."""
        self.tool_registry.register_tool(tool)
        self.logger.info(f"Registered tool: {tool.name}")
    
    
    def start(self):
        """Start the MCP server with FastMCP transport."""
        import sys
        import traceback
        
        self.logger.info("Starting MCP Tools Server with FastMCP transport...")
        
        from .fastmcp_adapter import FastMCPAdapter
        
        try:
            self.logger.info("Starting FastMCP transport...")
            
            # Create and start FastMCP adapter
            adapter = FastMCPAdapter(transport=self.transport)
            self.logger.info("FastMCP adapter created successfully")
            
            adapter.run_sync()
        except Exception as e:
            self.logger.critical(f"Failed to start FastMCP adapter: {e}", exc_info=True)
            self.logger.critical("="*60)
            self.logger.critical("FASTMCP ADAPTER STARTUP FAILED!")
            self.logger.critical(f"Error type: {type(e).__name__}")
            self.logger.critical(f"Error message: {str(e)}")
            self.logger.critical("="*60)
            traceback.print_exc()
            sys.exit(1)
    
    def get_server_info(self) -> Dict[str, Any]:
        """Get server information."""
        return {
            'name': 'MCP Tools Server',
            'version': '0.2.5',
            'transport': 'fastmcp',
            'tools_count': len(self.tool_registry.get_all_tools()),
            'sandboxes_count': len(sandbox_manager.list_sandboxes()),
            'config': {
                'host': self.config.server.host,
                'port': self.config.server.port,
                'sandbox_path': self.config.sandbox.base_path
            }
        }