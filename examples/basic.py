"""Basic example of using common-mcp-submodule.

This example demonstrates a minimal MCP server with PAT authentication only.

Run with:
    uvicorn basic:app --reload

Test with:
    curl -X POST http://localhost:8000/mcp \
      -H "Content-Type: application/json" \
      -H "X-API-Key: demo_pat_12345" \
      -d '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}'
"""

from fastapi import FastAPI, Request
from mcp.types import Tool, TextContent
from common_mcp_server import MCPServer, PATConfig

app = FastAPI(title="Basic MCP Server Example")


# Simple PAT verification (in production, check against database)
async def verify_pat(token: str, request: Request) -> dict | None:
    """Verify Personal Access Token."""
    # Demo: accept any token that starts with demo_pat_
    if token.startswith("demo_pat_"):
        return {
            "user_id": "demo-user-123",
            "email": "demo@example.com",
            "username": "demo",
            "name": "Demo User",
        }
    return None


# Create MCP server with PAT authentication only
mcp_server = MCPServer(
    name="basic-mcp-server",
    version="1.0.0",
    pat_config=PATConfig(
        header_name="X-API-Key",
        prefix="demo_pat_",
        verify_function=verify_pat,
    ),
)


# Define available tools
async def get_tools():
    return [
        Tool(
            name="echo",
            description="Echoes back the input message",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Message to echo back"
                    }
                },
                "required": ["message"]
            }
        ),
        Tool(
            name="greet",
            description="Greets a user by name",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name to greet"
                    }
                },
                "required": ["name"]
            }
        ),
    ]


mcp_server.set_tools_provider(get_tools)


# Implement tool execution
@mcp_server.tool_handler()
async def handle_tool(
    name: str,
    arguments: dict,
    auth_token: str,
    user_id: str,
    is_pat: bool
) -> list[TextContent]:
    """Execute MCP tool calls."""

    if name == "echo":
        message = arguments.get("message", "")
        return [TextContent(
            type="text",
            text=f"Echo: {message}"
        )]

    elif name == "greet":
        name_arg = arguments.get("name", "stranger")
        return [TextContent(
            type="text",
            text=f"Hello, {name_arg}! 👋"
        )]

    else:
        return [TextContent(
            type="text",
            text=f"Unknown tool: {name}"
        )]


# Mount MCP router
app.include_router(
    mcp_server.get_router(),
    prefix="/mcp",
    tags=["MCP"]
)


@app.get("/")
async def root():
    """Root endpoint with server info."""
    return {
        "name": "Basic MCP Server Example",
        "mcp_endpoint": "/mcp",
        "documentation": "/docs",
        "auth": "PAT (X-API-Key header with demo_pat_* prefix)",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
