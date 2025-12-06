# MCP Integration Tests

Integration tests for the Ryumem MCP server (TypeScript wrapper).

## Overview

These tests verify that:
1. The MCP server starts correctly and responds to protocol requests
2. Each MCP tool correctly proxies calls to the Ryumem API
3. End-to-end workflows function as expected
4. Multi-tenant isolation and session management work properly

## Prerequisites

### 1. Build the MCP Server

Before running tests, build the TypeScript MCP server:

```bash
cd mcp-server-ts/
npm install
npm run build
```

### 2. Start a Ryumem API Server

The tests require a running Ryumem API server. You can either:

**Option A: Use a local development server**
```bash
# Set environment variable to point to your local server
export RYUMEM_TEST_API_URL="http://localhost:8000"
export RYUMEM_API_KEY="your-test-api-key"
```

**Option B: Use the production API**
```bash
export RYUMEM_TEST_API_URL="https://api.ryumem.io"
export RYUMEM_API_KEY="your-production-api-key"
```

### 3. Install Test Dependencies

```bash
pip install pytest pytest-asyncio
```

## Running Tests

### Run all MCP tests
```bash
# With environment variables set
pytest tests/mcp/ -v

# Or inline
RYUMEM_API_URL="http://localhost:8000" RYUMEM_API_KEY="your-api-key" pytest tests/mcp/ -v
```

### Run specific test files
```bash
# Server protocol tests
pytest tests/mcp/test_mcp_server.py -v

# Individual tool tests
pytest tests/mcp/test_mcp_tools.py -v

# Integration workflow tests
pytest tests/mcp/test_mcp_integration.py -v
```

### Run with coverage
```bash
pytest tests/mcp/ --cov=ryumem --cov-report=html
```

## Test Structure

### `conftest.py`
- Fixtures for MCP server client
- Mock API server setup
- Test data generators
- API availability checks

### `test_mcp_server.py`
- Server startup and initialization
- MCP protocol compliance (JSON-RPC 2.0)
- Tool listing and schema validation
- Configuration via environment variables

### `test_mcp_tools.py`
- Individual tool invocation tests
- Parameter validation
- Error handling
- Response format verification

### `test_mcp_integration.py`
- End-to-end workflows
- Multi-tool interactions
- Session management
- Entity tracking
- Memory pruning
- Error recovery

## Environment Variables

- `RYUMEM_TEST_API_URL`: URL of the Ryumem API server (default: `http://localhost:8000`)
- `RYUMEM_API_KEY`: API key for authentication (default: `test-api-key`)

## Skipped Tests

Tests will be automatically skipped if:
- The MCP server is not built (`mcp-server-ts/build/index.js` doesn't exist)
- The Ryumem API server is not available
- Required environment variables are missing

## Troubleshooting

### MCP server fails to start
- Verify the server is built: `ls mcp-server-ts/build/index.js`
- Check Node.js is installed: `node --version`
- Ensure API key is set: `echo $RYUMEM_API_KEY`

### Tests timeout or hang
- Verify API server is running and accessible
- Check network connectivity
- Increase test timeouts if needed

### Import errors
- Ensure you're in the project root
- Install test dependencies: `pip install -e ".[dev]"`

## Contributing

When adding new MCP tools:
1. Add tool tests to `test_mcp_tools.py`
2. Add integration scenarios to `test_mcp_integration.py`
3. Update tool list in `test_mcp_server.py::test_list_tools`
4. Document new environment variables if needed
