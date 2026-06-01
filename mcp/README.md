# MCP Tools Framework

A comprehensive Model Context Protocol (MCP) server framework with advanced sandbox support for secure tool execution.

## 📚 Documentation

- **[Transport Guide](TRANSPORT_GUIDE.md)**: Detailed guide on using stdio and FastMCP modes
- **[Migration Guide](MIGRATION_GUIDE.md)**: Upgrading from previous versions
- **[Config Example](config.example.yaml)**: Complete configuration reference

## Features

- **Dual Transport Support**: Works with both stdio (for Claude Desktop, etc.) and FastMCP (HTTP/SSE API)
- **Sandbox Isolation**: Each tool call receives a unique sandbox ID, creating isolated environments for file operations and command execution
- **Persistent Storage**: Sandboxes are stored locally and persist between sessions without occupying memory when inactive
- **Extensible Architecture**: Easy-to-extend framework supporting various tool types
- **Configuration Management**: YAML-based configuration with environment variable overrides
- **Multiple Tool Types**: Built-in support for file operations, command execution, and AI model integration
- **Security**: Command filtering and sandbox containment for safe execution

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/moolean/mcp_tools.git
cd mcp_tools

# Install dependencies
pip install -r requirements.txt

# Or install as a package
pip install -e .

# Or use uv
uv sync
```

### Configuration

Generate an example configuration file:

```bash
python -m mcp_tools.server --generate-config
```

This creates `config.example.yaml` with all available options. Copy it to `config.yaml` and modify as needed:

```yaml
server:
  # Transport type: "stdio" or "fastmcp"
  transport: stdio
  host: localhost
  port: 8001
  debug: false

sandbox:
  base_path: ./sandboxes
  max_file_size: 104857600  # 100MB
  max_command_timeout: 300  # 5 minutes
  allowed_commands:
    - ls
    - cat
    - echo
    - mkdir
    - touch
    - python3
    - node
    - npm
  blocked_commands:
    - sudo
    - rm -rf
    - chmod
    - kill

models:
  openai:
    api_key: your-openai-api-key-here
    model_name: gpt-3.5-turbo
    timeout: 30

tools:
  file_operations:
    enabled: true
  command_execution:
    enabled: true
  model_chat:
    enabled: true
    config:
      default_model: openai
```

### Running the Server

The server supports two transport modes. For detailed usage guide, see [TRANSPORT_GUIDE.md](TRANSPORT_GUIDE.md).

#### Quick Start

```bash
# Linux/macOS
chmod +x quickstart.sh
./quickstart.sh stdio              # stdio mode
./quickstart.sh fastmcp            # FastMCP mode
./quickstart.sh fastmcp --port 8002 --debug  # with options

# Windows
quickstart.bat stdio               # stdio mode
quickstart.bat fastmcp             # FastMCP mode
quickstart.bat fastmcp --port 8002 --debug   # with options
```

The server supports two transport modes:

#### 1. stdio Mode (Default)

Best for integration with Claude Desktop and other MCP clients that use standard I/O:

```bash
# Using command line argument
python -m mcp_tools.server --transport stdio --config config.yaml

# Or set in config.yaml
# server:
#   transport: stdio
python -m mcp_tools.server --config config.yaml

# With debug logging
python -m mcp_tools.server --transport stdio --debug
```

Configure in your Claude Desktop config:
```json
{
  "mcpServers": {
    "mcp-tools": {
      "command": "python",
      "args": ["-m", "mcp_tools.server", "--config", "/path/to/config.yaml"]
    }
  }
}
```

#### 2. FastMCP Mode (HTTP/SSE API)

Best for HTTP-based integrations and when you need a REST API:

```bash
# Using command line argument
python -m mcp_tools.server --transport fastmcp --host 0.0.0.0 --port 8001

# Or set in config.yaml
# server:
#   transport: fastmcp
#   host: 0.0.0.0
#   port: 8001
python -m mcp_tools.server --config config.yaml

# Custom host and port
python -m mcp_tools.server --transport fastmcp --host localhost --port 9000
```

The FastMCP server will start an HTTP/SSE API server that you can access at:
- Base URL: `http://localhost:8001` (or your configured host/port)
- SSE endpoint for real-time streaming

#### Backward Compatibility

The framework defaults to stdio mode for backward compatibility. Existing installations will continue to work without any changes.

## Architecture

### Core Components

1. **MCPToolsServer**: Main server handling MCP protocol communication
2. **SandboxManager**: Manages isolated sandbox environments
3. **ToolRegistry**: Registry for available tools
4. **ConfigLoader**: Configuration management with YAML and environment variables

### Sandbox System

The framework provides isolated sandbox environments for secure tool execution. The `sandbox_id` is provided at the request level (not as a tool argument) and is automatically injected by the framework:

1. **Initialization**: If the sandbox doesn't exist, it's created with an isolated directory
2. **Persistence**: Sandbox state is stored locally and persists between sessions
3. **Isolation**: Each sandbox has its own file system space and process environment
4. **Security**: Commands are filtered and file access is contained within sandbox bounds

### Tool Development

Create custom tools by extending the `BaseTool` class:

```python
from mcp_tools.core.base_tool import BaseTool, ToolInput, ToolOutput, ToolSchema

class MyCustomTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="my_custom_tool",
            description="Description of what this tool does",
            requires_sandbox=True  # Set to True if tool needs sandbox
        )
    
    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            input_schema={
                "type": "object",
                "properties": {
                    "param1": {"type": "string", "description": "Parameter description"}
                },
                "required": ["param1"]
            },
            requires_sandbox=self.requires_sandbox
        )
    
    async def execute(self, input_data: ToolInput) -> ToolOutput:
        # Implementation here
        # sandbox_id is automatically available in input_data if requires_sandbox=True
        return ToolOutput(
            success=True,
            data={"result": "success"}
        )
```

## Built-in Tools

### File Operations Tool

Performs file system operations within sandboxes:

- **read**: Read file content
- **write**: Write content to file (with append option)
- **list**: List files and directories
- **delete**: Delete files or directories

Example usage (HTTP mode):
```json
{
  "name": "file_operations",
  "sandbox_id": "my-project-123",
  "arguments": {
    "operation": "write",
    "file_path": "hello.txt",
    "content": "Hello, World!"
  }
}
```

Example usage (MCP stdio mode):
```json
{
  "name": "file_operations",
  "arguments": {
    "sandbox_id": "my-project-123",
    "operation": "write",
    "file_path": "hello.txt",
    "content": "Hello, World!"
  }
}
```

### Command Execution Tool

Execute shell commands within sandboxes:

Example usage (HTTP mode):
```json
{
  "name": "command_execution",
  "sandbox_id": "my-project-123",
  "arguments": {
    "command": "python3 hello.py",
    "working_directory": ".",
    "timeout": 30
  }
}
```

Example usage (MCP stdio mode):
```json
{
  "name": "command_execution",
  "arguments": {
    "sandbox_id": "my-project-123",
    "command": "python3 hello.py",
    "working_directory": ".",
    "timeout": 30
  }
}
```

### Model Chat Tool

Integrate with AI models (OpenAI, Anthropic, etc.):

Example usage (HTTP mode):
```json
{
  "name": "model_chat",
  "sandbox_id": "my-project-123",
  "arguments": {
    "message": "Explain this code",
    "model": "openai",
    "temperature": 0.7,
    "max_tokens": 1000
  }
}
```

Example usage (MCP stdio mode):
```json
{
  "name": "model_chat",
  "arguments": {
    "sandbox_id": "my-project-123",
    "message": "Explain this code",
    "model": "openai",
    "temperature": 0.7,
    "max_tokens": 1000
  }
}
```

## Testing

Run the included test script to verify functionality:

```bash
python test_server.py
```

This will test:
- File operations in sandboxes
- Sandbox isolation
- Tool registry functionality
- Configuration loading

## Environment Variables

Override configuration with environment variables:

- `MCP_HOST`: Server host
- `MCP_PORT`: Server port
- `MCP_DEBUG`: Enable debug mode (true/false)
- `MCP_SANDBOX_PATH`: Base path for sandboxes
- `OPENAI_API_KEY`: OpenAI API key
- `ANTHROPIC_API_KEY`: Anthropic API key

## Security Considerations

- **Command Filtering**: Only whitelisted commands are allowed
- **Sandbox Isolation**: Each sandbox is contained within its directory
- **File Size Limits**: Configurable limits on file sizes
- **Timeout Protection**: Commands have configurable timeouts
- **Path Traversal Protection**: Paths are validated to stay within sandbox bounds

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add your tool or enhancement
4. Ensure tests pass
5. Submit a pull request

## License

MIT License - see LICENSE file for details.
