"""Configuration models for MCP Tools Framework."""

from typing import Dict, Any, Optional, List, Literal
from pydantic import BaseModel, Field


TransportType = Literal["stdio", "http", "sse", "streamable-http"]


class ModelConfig(BaseModel):
    """Configuration for AI model integration."""
    api_key: str
    base_url: Optional[str] = None
    model_name: str = "gpt-3.5-turbo"
    timeout: int = 30

    class Config:
        extra = "allow"


class SandboxConfig(BaseModel):
    """Configuration for sandbox management."""
    base_path: str = "./sandboxes"
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    max_command_timeout: int = 300  # 5 minutes
    tool_execution_timeouts : int = 30
    max_memory: int = 512 #MB
    memory_data_path: str = "/mnt/afs/yuannang/agent/RL/rl_data/mcp_tools/data/memory_data/"
    # TODO
    allowed_commands: List[str] = Field(default_factory=lambda: [
        "ls", "cat", "echo", "mkdir", "touch", "cp", "mv", "rm", "grep",
        "find", "head", "tail", "wc", "sort", "uniq", "python3", "node", "npm","python", "which"
    ])
    blocked_commands: List[str] = Field(default_factory=lambda: [
        "sudo", "su", "chmod", "chown", "systemctl", "service", "kill", "killall"
    ])

    class Config:
        extra = "allow"


class WebSearchConfig(BaseModel):
    """Configuration for web search."""
    api_key: Optional[str] = None
    db_url: str = "sqlite:///./search_cache.db"

    class Config:
        extra = "allow"


class HttpSearchConfig(BaseModel):
    """Configuration for HTTP search."""
    url: str = "http://127.0.0.1"
    port: int = 8080
    api_key: Optional[str] = None
    class Config:
        extra = "allow"


class ToolConfig(BaseModel):
    """Configuration for individual tools."""
    enabled: bool = True
    config: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        extra = "allow"


class ServerConfig(BaseModel):
    """Main server configuration."""
    host: str = "localhost"
    port: int = 8000
    debug: bool = False
    cors_origins: List[str] = Field(default_factory=lambda: ["*"])
    transport: TransportType = "stdio"  # Default to stdio for backward compatibility

    class Config:
        extra = "allow"

class FetchUrlConfig(BaseModel):
    """Configuration for Fetch URL tool."""
    api_key: str
    base_url: str
    model_name: str = "qwen-plus"

    class Config:
        extra = "allow"

class RerankConfig(BaseModel):
    """Configuration for Rerank service."""
    api_url: str | List[str] = "http://10.119.29.248:8000/rerank"
    top_k: int = 2
    max_retries: int = 3

    class Config:
        extra = "allow"

class MCPToolsConfig(BaseModel):
    """Main configuration for MCP Tools Framework."""
    server: ServerConfig = Field(default_factory=ServerConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    models: Dict[str, ModelConfig] = Field(default_factory=dict)
    tools: Dict[str, ToolConfig] = Field(default_factory=dict)
    web_search: WebSearchConfig = Field(default_factory=WebSearchConfig)
    http_search: HttpSearchConfig = Field(default_factory=HttpSearchConfig)
    fetch_url: FetchUrlConfig = Field(default_factory=FetchUrlConfig)
    rerank: RerankConfig = Field(default_factory=RerankConfig)
    
    class Config:
        extra = "allow"