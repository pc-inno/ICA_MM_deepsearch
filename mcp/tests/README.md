# MCP Tools Framework - Testing Guide

This directory contains the test suite for the MCP Tools Framework, including unit tests and MCP integration tests.

## Installation

Install test dependencies:

```bash
pip install -r requirements-dev.txt
```

## Running Tests

### Run All Tests

```bash
pytest tests/
```

### Run Specific Test Files

```bash
# Run only DuckDuckGo tests
pytest tests/test_duckduckgo.py

# Run only MCP integration tests
pytest tests/test_tools_mcp.py
```

### Run Tests with Verbose Output

```bash
pytest tests/ -v
```

## Test Categories

### Unit Tests

Unit tests verify individual components in isolation and will skip gracefully if dependencies are not installed.

#### DuckDuckGo Search Tool Tests (`test_duckduckgo.py`)

Tests for the DuckDuckGo search functionality:

- `test_duckduckgo_search_basic`: Verifies basic search functionality
- `test_duckduckgo_search_empty_query`: Tests error handling for empty queries
- `test_duckduckgo_search_invalid_max_results`: Tests validation of max_results parameter
- `test_duckduckgo_missing_dependency`: Tests behavior when duckduckgo_search is not installed
- `test_duckduckgo_search_custom_max_results`: Tests custom result limits

**Requirements**: 
- `duckduckgo-search` package (tests skip if not installed)

**Running**:
```bash
# With dependency installed
pip install duckduckgo-search
pytest tests/test_duckduckgo.py -v

# Without dependency (tests will skip)
pytest tests/test_duckduckgo.py -v
```

### MCP Integration Tests (`test_tools_mcp.py`)

These tests verify tools can integrate with a live MCP server endpoint. They are marked with the `@pytest.mark.mcp` marker.

**Requirements**:
- MCP server running and accessible
- Environment variables set:
  - `MCP_HOST`: Hostname or IP address of MCP server (e.g., `localhost`)
  - `MCP_PORT`: Port number (default: `8000`)

**Running**:

```bash
# Tests skip automatically when MCP_HOST is not set
pytest tests/test_tools_mcp.py

# Run with MCP server
MCP_HOST=localhost MCP_PORT=8000 pytest tests/test_tools_mcp.py -v

# Run only MCP-marked tests
MCP_HOST=localhost MCP_PORT=8000 pytest tests/ -m mcp -v

# Skip MCP tests explicitly
pytest tests/ -m "not mcp" -v
```

**Test Behavior**:
- Automatically discovers all tool modules in `mcp_tools/tools/`
- Creates a parametrized test for each discovered tool
- Tests skip gracefully when:
  - `MCP_HOST` environment variable is not set
  - MCP server is not reachable
  - Connection to MCP server fails

**Extending MCP Tests**:

The MCP tests provide a scaffold for maintainers to implement full protocol interactions. To extend:

1. Implement the protocol helper functions in `conftest.py`:
   - `send_mcp_message()`: Send MCP protocol messages
   - `receive_mcp_message()`: Receive and parse MCP responses
   - `perform_mcp_handshake()`: Complete initialization sequence

2. Extend `test_tool_mcp_integration()` in `test_tools_mcp.py` with real protocol interactions (see comments in the test)

Example:
```python
# In conftest.py
def send_mcp_message(connection, message_data):
    import json
    message = json.dumps(message_data).encode('utf-8')
    connection.sendall(message)

# In test_tools_mcp.py
def test_tool_mcp_integration(tool_name, mcp_connection):
    # ... existing code ...
    
    # Perform handshake
    assert perform_mcp_handshake(mcp_connection)
    
    # List tools
    send_mcp_message(mcp_connection, {'type': 'list_tools'})
    response = receive_mcp_message(mcp_connection)
    assert tool_name in [t['name'] for t in response['tools']]
```

## Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `MCP_HOST` | MCP server hostname/IP | - | For MCP tests |
| `MCP_PORT` | MCP server port | 8000 | For MCP tests |

## Test Markers

Tests are marked with pytest markers to enable selective test execution:

- `@pytest.mark.mcp`: Tests requiring MCP server connection

## Continuous Integration

When running in CI environments without an MCP server:

```bash
# All MCP tests will skip automatically
pytest tests/

# Or explicitly skip MCP tests
pytest tests/ -m "not mcp"
```

## Tool Discovery

The test suite automatically discovers tools by scanning the `mcp_tools/tools/` directory for Python modules (excluding `__init__.py`). When you add a new tool:

1. Create your tool module in `mcp_tools/tools/your_tool.py`
2. The test suite will automatically discover it
3. Run tests to verify: `pytest tests/test_tools_mcp.py -v`

## Writing New Tests

### Adding a Unit Test for a New Tool

1. Create `tests/test_your_tool.py`
2. Follow the pattern from `test_duckduckgo.py`:
   - Use `pytest.skip()` or `pytest.importorskip()` for optional dependencies
   - Test both success and error cases
   - Verify data structures and types

Example:
```python
import pytest

def test_your_tool_basic():
    pytest.importorskip("your_dependency")
    from mcp_tools.tools.your_tool import your_function
    
    result = your_function("test")
    assert result is not None
```

### Adding MCP Integration Tests

MCP integration tests are automatically generated for all discovered tools. To add tool-specific MCP behavior:

1. Implement protocol helpers in `conftest.py`
2. Extend `test_tool_mcp_integration()` with tool-specific assertions
3. Or create a new test file with `@pytest.mark.mcp` decorator

## Troubleshooting

### Tests Skip Due to Missing Dependencies

If you see skip messages like "duckduckgo_search package not installed":

```bash
pip install -r requirements-dev.txt
```

### MCP Tests Always Skip

Ensure environment variables are set:

```bash
export MCP_HOST=localhost
export MCP_PORT=8000
pytest tests/test_tools_mcp.py -v
```

### Connection Refused Errors

Verify MCP server is running:

```bash
# Check if port is listening
nc -zv localhost 8000

# Or using telnet
telnet localhost 8000
```

## Coverage Reports

Generate test coverage reports:

```bash
# Install coverage tool
pip install pytest-cov

# Run with coverage
pytest tests/ --cov=mcp_tools --cov-report=html

# View report
open htmlcov/index.html  # or xdg-open on Linux
```

## Additional Resources

- [pytest documentation](https://docs.pytest.org/)
- [Main README](../README.md) for framework documentation
- MCP Protocol specification (when available)
