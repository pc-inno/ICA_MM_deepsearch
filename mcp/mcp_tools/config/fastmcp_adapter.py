"""FastMCP adapter for MCP Tools Framework.

This adapter provides HTTP/SSE based API server using FastMCP library.
"""

import asyncio
import logging
import inspect
import json
from typing import Dict, Any, List, Optional, Literal
from fastmcp import FastMCP, Context

from .base_tool import BaseTool
from .tool_registry import ToolRegistry
from ..config.loader import config_loader
from ..sandbox.manager import sandbox_manager


class FastMCPAdapter:
    """Adapter to run MCP Tools using FastMCP (HTTP/SSE) transport."""
    
    def __init__(self):
        self.config = config_loader.load_config()
        self.tool_registry = ToolRegistry()
        self.logger = logging.getLogger(__name__)
        
        # Create FastMCP server instance
        self.mcp = FastMCP("MCP Tools Server")
        
        # Setup will be done after tools are loaded
        self._setup_complete = False
    
    async def _load_tools(self):
        """Load all available tools."""
        # Load optional tools based on configuration
        await self._load_optional_tools()
    
    async def _load_optional_tools(self):
        """Load optional tools based on configuration."""
        from importlib import import_module

        for tool_name, tool_cfg in (self.config.tools or {}).items():
            enabled = True
            module_path = None
            class_name = None

            try:
                enabled = bool(tool_cfg.enabled)
            except Exception:
                enabled = True

            if not enabled:
                self.logger.info(f"Tool '{tool_name}' is disabled by configuration; skipping")
                continue

            # Try to read module/class from the tool's config dict
            try:
                cfg_dict = getattr(tool_cfg, 'config', {}) or {}
                module_path = cfg_dict.get('module')
                class_name = cfg_dict.get('class')
            except Exception:
                cfg_dict = {}

            # Perform dynamic import and registration
            try:
                if module_path.startswith('.'):
                    module = import_module(module_path, package='mcp_tools.core')
                else:
                    module = import_module(module_path)

                tool_class = getattr(module, class_name)
                tool_instance = tool_class()

                # Ensure no duplicate registration
                if self.tool_registry.get_tool(tool_instance.name):
                    self.logger.info(f"Tool '{tool_instance.name}' already registered; skipping")
                    continue

                self.register_tool(tool_instance)
            except ImportError as e:
                self.logger.warning(f"Failed to import tool '{tool_name}' from '{module_path}': {e}")
            except AttributeError as e:
                self.logger.warning(f"Tool class '{class_name}' not found in module '{module_path}': {e}")
            except Exception as e:
                self.logger.error(f"Error loading tool '{tool_name}': {e}")
    
    def _is_tool_enabled(self, tool_name: str) -> bool:
        """Check if a tool is enabled in configuration."""
        tool_config = self.config.tools.get(tool_name)
        return tool_config is None or tool_config.enabled
    
    def register_tool(self, tool: BaseTool):
        """Register a new tool with the server."""
        try:
            self.tool_registry.register_tool(tool)
            self.logger.info(f"Registered tool in FastMCP: {tool.name}")
            
            # Get tool schema
            schema = tool.get_schema()
            properties = schema.input_schema.get('properties', {})
            
            if schema.extra_schema:
                extra_properties = schema.extra_schema.get('properties', {})
                properties.update(extra_properties)

            self.logger.debug(f"Tool '{tool.name}' properties: {list(properties.keys())}")
            
            # Create wrapper function
            async def tool_wrapper(**kwargs):
                """Wrapper function to execute the tool."""
                try:
                    # Extract sandbox_id
                    # sandbox_id = kwargs.pop('sandbox_id', 'sandbox_for_debug')
                    sandbox_id = kwargs.get('sandbox_id', 'sandbox_for_debug')
                    
                    # Initialize sandbox if tool requires it
                    if tool.requires_sandbox:
                        try:
                            sandbox_manager.get_sandbox(sandbox_id)
                        except Exception as sandbox_error:
                            self.logger.error(f"Failed to initialize sandbox '{sandbox_id}': {sandbox_error}", exc_info=True)
                            return f"Error: Failed to initialize sandbox: {str(sandbox_error)}"
                    
                    # Execute tool with remaining kwargs
                    result = await tool(kwargs)
                    
                    # Format response
                    if result['success']:
                        data = result.get('data', "Operation completed successfully")
                        # Return string representation for FastMCP
                        if isinstance(data, (dict, list)):
                            return json.dumps(data, indent=2, ensure_ascii=False)
                        return str(data)
                    else:
                        error_msg = result.get('error', 'Unknown error')
                        self.logger.warning(f"Tool '{tool.name}' returned error: {error_msg}")
                        return f"Error: {error_msg}"
                        
                except Exception as e:
                    self.logger.error(f"CRITICAL: Tool '{tool.name}' execution failed!", exc_info=True)
                    self.logger.error("="*60)
                    self.logger.error(f"Tool name: {tool.name}")
                    self.logger.error(f"Error type: {type(e).__name__}")
                    self.logger.error(f"Error message: {str(e)}")
                    self.logger.error(f"Input kwargs: {kwargs}")
                    self.logger.error("="*60)
                    import traceback
                    error_traceback = traceback.format_exc()
                    self.logger.error(f"Full traceback:\n{error_traceback}")
                    return f"Error executing tool '{tool.name}': {type(e).__name__}: {str(e)}"
            
            # Set function metadata
            tool_wrapper.__name__ = schema.name
            tool_wrapper.__doc__ = schema.description
            
            # Build signature and annotations directly from JSON schema
            params = []
            annotations = {}
            
            for prop_name, prop_schema in properties.items():
                # Map JSON schema type to Python type
                python_type = self._get_python_type_from_schema(prop_schema)
                
                # Get default value (inspect.Parameter.empty means required)
                default_value = prop_schema.get('default', inspect.Parameter.empty)
                
                # Create parameter
                param = inspect.Parameter(
                    prop_name,
                    inspect.Parameter.KEYWORD_ONLY,
                    default=default_value,
                    annotation=python_type
                )
                params.append(param)
                annotations[prop_name] = python_type
                
                self.logger.debug(f"  Parameter '{prop_name}': type={python_type}, default={default_value}")
            

            # # Add sandbox_id parameter
            # params.append(inspect.Parameter(
            #     'sandbox_id',
            #     inspect.Parameter.KEYWORD_ONLY,
            #     default='sandbox_for_debug',
            #     annotation=str
            # ))
            # annotations['sandbox_id'] = str
            
            # Set signature and annotations
            tool_wrapper.__signature__ = inspect.Signature(params)
            tool_wrapper.__annotations__ = annotations
            
            # Register with FastMCP
            self.mcp.tool()(tool_wrapper)
            
        except Exception as e:
            self.logger.error(f"Error registering tool '{tool.name}': {e}", exc_info=True)
    
    def _get_python_type_from_schema(self, prop_schema: dict) -> type:
        """Convert JSON schema property to Python type annotation.
        
        Handles:
        - Basic types (string, integer, number, boolean)
        - Enums (converts to Literal)
        - Arrays with items schema (converts to List[T])
        - Objects (converts to Dict[str, Any])
        """
        prop_type = prop_schema.get('type', 'string')
        
        # Handle enum - must use Literal type
        if 'enum' in prop_schema:
            enum_values = tuple(prop_schema['enum'])
            if enum_values:
                return Literal[enum_values]
        
        # Handle array with items schema
        if prop_type == 'array':
            items_schema = prop_schema.get('items', {})
            if items_schema:
                items_type = items_schema.get('type', 'string')
                item_python_type = self._json_type_to_python(items_type)
                return List[item_python_type]
            return list
        
        # Handle object type
        if prop_type == 'object':
            return Dict
        
        # Handle basic types
        return self._json_type_to_python(prop_type)
    
    def _json_type_to_python(self, json_type: str) -> type:
        """Convert JSON schema type to Python type."""
        type_mapping = {
            'string': str,
            'integer': int,
            'number': float,
            'boolean': bool,
            'array': list,
            'object': dict,
        }
        return type_mapping.get(json_type, str)
    
    async def setup(self):
        """Setup the FastMCP server with all tools."""
        if self._setup_complete:
            return
        
        self.logger.info("Setting up FastMCP adapter...")
        
        # Load and register all tools
        await self._load_tools()
        
        self._setup_complete = True
        self.logger.info(f"FastMCP adapter setup complete with {len(self.tool_registry.get_all_tools())} tools")
    
    async def start(self):
        """Start the FastMCP server."""
        self.logger.info("Starting FastMCP Tools Server...")
        
        # Setup tools if not already done
        if not self._setup_complete:
            await self.setup()
        
        # Get host and port from config
        host = self.config.server.host
        port = self.config.server.port
        
        self.logger.info(f"FastMCP server starting on {host}:{port}")
        
        # FastMCP's run() is blocking and creates its own event loop
        # We need to call it synchronously, not in an async context
        # Instead, we return the mcp instance to be run by the caller
        return self.mcp
    
    def run_sync(self, host: str = None, port: int = None):
        """Run the FastMCP server synchronously (blocking).
        
        This method should be called from non-async context.
        """
        import asyncio
        import sys
        import traceback
        
        try:
            # Setup tools first
            self.logger.info("Setting up FastMCP tools...")
            asyncio.run(self.setup())
            self.logger.info("FastMCP tools setup completed successfully")
        except Exception as e:
            self.logger.critical(f"Failed to setup FastMCP tools: {e}", exc_info=True)
            self.logger.critical("="*60)
            self.logger.critical("FASTMCP SETUP FAILED!")
            self.logger.critical(f"Error type: {type(e).__name__}")
            self.logger.critical(f"Error message: {str(e)}")
            self.logger.critical("="*60)
            traceback.print_exc()
            sys.exit(1)
        
        # Get host and port
        host = host or self.config.server.host
        port = port or self.config.server.port
        
        self.logger.info(f"FastMCP server starting on {host}:{port}")
        
        try:
            # Run FastMCP server (this is blocking)
            self.logger.info("Starting FastMCP event loop...")
            self.mcp.run(transport="sse", host=host, port=port, log_level="warning")
        except KeyboardInterrupt:
            self.logger.info("FastMCP server stopped by user")
            sys.exit(0)
        except Exception as e:
            self.logger.critical(f"FastMCP server crashed: {e}", exc_info=True)
            self.logger.critical("="*60)
            self.logger.critical("FASTMCP SERVER RUNTIME ERROR!")
            self.logger.critical(f"Error type: {type(e).__name__}")
            self.logger.critical(f"Error message: {str(e)}")
            self.logger.critical(f"Host: {host}, Port: {port}")
            self.logger.critical("="*60)
            traceback.print_exc()
            sys.exit(1)
    
    def get_server_info(self) -> Dict[str, Any]:
        """Get server information."""
        return {
            'name': 'MCP Tools Server (FastMCP)',
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
