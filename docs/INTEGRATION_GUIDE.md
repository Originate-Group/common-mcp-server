# Integration Guide

This guide shows how to integrate `common-mcp-server` into your existing FastAPI application.

## Step-by-Step Integration

### 1. Add as Dependency

**Option A: Git Submodule (Recommended for internal projects)**

```bash
# Add as submodule
git submodule add https://github.com/Originate-Group/common-mcp-server.git

# Install in development mode
pip install -e common-mcp-server/
```

**Option B: PyPI (When published)**

```bash
pip install common-mcp-server
```

**Option C: Direct from Git**

```bash
pip install git+https://github.com/Originate-Group/common-mcp-server.git
```

### 2. Configure Authentication

#### For OAuth with Keycloak

```python
from common_mcp_server import OAuthConfig

oauth_config = OAuthConfig(
    jwks_url=f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/certs",
    issuer=f"{KEYCLOAK_URL}/realms/{REALM}",
    algorithms=["RS256"],
)
```

#### For Personal Access Tokens

```python
from common_mcp_server import PATConfig
from fastapi import Request
from sqlalchemy.orm import Session

async def verify_pat(token: str, request: Request) -> dict | None:
    """Verify PAT against your database."""
    # Access database via dependency injection
    db: Session = request.state.db

    # Query your PAT table
    pat_record = db.query(PersonalAccessToken).filter(
        PersonalAccessToken.token == token,
        PersonalAccessToken.is_active == True,
    ).first()

    if not pat_record:
        return None

    # Return user information
    return {
        "user_id": pat_record.user.external_id,
        "email": pat_record.user.email,
        "username": pat_record.user.email.split('@')[0],
        "name": pat_record.user.full_name,
    }

pat_config = PATConfig(
    header_name="X-API-Key",
    prefix="your_app_pat_",
    verify_function=verify_pat,
)
```

### 3. Create MCP Server Instance

```python
from common_mcp_server import MCPServer

mcp_server = MCPServer(
    name="your-app-mcp",
    version="1.0.0",
    oauth_config=oauth_config,  # Optional
    pat_config=pat_config,       # Optional
    resource_url="https://your-app.com",  # For OAuth WWW-Authenticate header
)
```

### 4. Define Your Tools

Create a module for your MCP tools (e.g., `mcp_tools.py`):

```python
from mcp.types import Tool

def get_tools() -> list[Tool]:
    """Return list of available MCP tools."""
    return [
        Tool(
            name="list_items",
            description="List all items with optional filtering",
            inputSchema={
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "string",
                        "description": "Optional filter"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max items to return"
                    }
                }
            }
        ),
        Tool(
            name="get_item",
            description="Get a specific item by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "string",
                        "description": "Item UUID"
                    }
                },
                "required": ["item_id"]
            }
        ),
        # Add more tools...
    ]

# Register tools provider
mcp_server.set_tools_provider(get_tools)
```

### 5. Implement Tool Handler

Create a tool handler module (e.g., `mcp_handlers.py`):

```python
from typing import Optional
import httpx
from mcp.types import TextContent

# Your API base URL (can be localhost for internal calls)
API_BASE_URL = "http://localhost:8000/api/v1"

@mcp_server.tool_handler()
async def handle_tool(
    name: str,
    arguments: dict,
    auth_token: Optional[str],
    user_id: Optional[str],
    is_pat: bool
) -> list[TextContent]:
    """Handle MCP tool calls by forwarding to your API endpoints."""

    # Prepare authentication headers
    headers = {}
    if auth_token:
        if is_pat:
            headers["X-API-Key"] = auth_token
        else:
            headers["Authorization"] = auth_token

    # Make API calls using httpx
    async with httpx.AsyncClient(base_url=API_BASE_URL, timeout=30.0, headers=headers) as client:
        try:
            if name == "list_items":
                # Forward to your API endpoint
                params = {k: v for k, v in arguments.items() if v is not None}
                response = await client.get("/items/", params=params)
                response.raise_for_status()
                result = response.json()

                # Format response for MCP client
                items_text = "\n".join([f"- {item['name']}" for item in result['items']])
                return [TextContent(
                    type="text",
                    text=f"Found {result['total']} items:\n{items_text}"
                )]

            elif name == "get_item":
                item_id = arguments["item_id"]
                response = await client.get(f"/items/{item_id}")
                response.raise_for_status()
                result = response.json()

                return [TextContent(
                    type="text",
                    text=f"Item: {result['name']}\nStatus: {result['status']}\nID: {result['id']}"
                )]

            else:
                return [TextContent(type="text", text=f"Unknown tool: {name}")]

        except httpx.HTTPStatusError as e:
            # Handle API errors
            try:
                error_detail = e.response.json().get("detail", str(e))
            except Exception:
                error_detail = e.response.text or str(e)
            return [TextContent(type="text", text=f"Error: {error_detail}")]

        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]
```

### 6. Mount in FastAPI App

In your `main.py` or `server.py`:

```python
from fastapi import FastAPI
from .routers import mcp_server  # Import your configured MCP server

app = FastAPI(title="Your Application")

# Mount your existing routers
app.include_router(api_router, prefix="/api/v1")

# Mount MCP router
app.include_router(
    mcp_server.get_router(),
    prefix="/mcp",
    tags=["MCP"]
)
```

## Project Structure Example

```
your-app/
├── src/
│   ├── api/
│   │   ├── main.py              # FastAPI app
│   │   ├── config.py            # Configuration
│   │   ├── routers/
│   │   │   ├── api.py           # Your API routes
│   │   │   └── mcp.py           # MCP configuration ⭐ NEW
│   │   └── mcp/
│   │       ├── tools.py         # MCP tool definitions ⭐ NEW
│   │       └── handlers.py      # MCP tool handlers ⭐ NEW
│   └── models/
│       └── database.py
├── common-mcp-server/           # Git submodule ⭐ NEW
└── requirements.txt
```

## Complete Example File

**src/api/routers/mcp.py:**

```python
"""MCP Server configuration for Your App."""

import logging
from typing import Optional
from fastapi import Request
from sqlalchemy.orm import Session

from common_mcp_server import MCPServer, OAuthConfig, PATConfig
from ..config import get_settings
from ..auth.dependencies import verify_personal_access_token
from ..mcp.tools import get_tools
from ..mcp.handlers import handle_tool

logger = logging.getLogger("your-app.mcp")
settings = get_settings()

# Configure authentication
oauth_config = OAuthConfig(
    jwks_url=f"{settings.keycloak_url}/realms/{settings.keycloak_realm}/protocol/openid-connect/certs",
    issuer=f"{settings.keycloak_url}/realms/{settings.keycloak_realm}",
)

async def verify_pat_wrapper(token: str, request: Request) -> Optional[dict]:
    """Wrapper for PAT verification with database access."""
    # Access database through FastAPI dependency
    from ..database import get_db
    db = next(get_db())
    try:
        user = await verify_personal_access_token(token, db)
        if not user:
            return None
        return {
            "user_id": user.external_id,
            "email": user.email,
            "username": user.email.split('@')[0],
            "name": user.full_name or user.email,
        }
    finally:
        db.close()

pat_config = PATConfig(
    header_name="X-API-Key",
    prefix="your_app_pat_",
    verify_function=verify_pat_wrapper,
)

# Create MCP server
mcp_server = MCPServer(
    name="your-app-mcp",
    version="1.0.0",
    oauth_config=oauth_config,
    pat_config=pat_config,
    resource_url=settings.base_url,
)

# Register tools
mcp_server.set_tools_provider(get_tools)

# Register handler
mcp_server.tool_handler()(handle_tool)

# Export router
__all__ = ["mcp_server"]
```

## Testing Your Integration

### 1. Test Authentication

```bash
# Test with PAT
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_app_pat_test123" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {}
  }'
```

### 2. Test Tool Listing

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_app_pat_test123" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list",
    "params": {}
  }'
```

### 3. Test Tool Execution

```bash
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_app_pat_test123" \
  -d '{
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {
      "name": "list_items",
      "arguments": {"limit": 10}
    }
  }'
```

### 4. Test with Claude Code

Add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "your-app": {
      "type": "http",
      "url": "http://localhost:8000/mcp",
      "headers": {
        "X-API-Key": "your_app_pat_test123"
      }
    }
  }
}
```

Then in Claude Code:
```
List my items using the your-app MCP tools
```

## Troubleshooting

### MCP Tools Not Available

1. Check tool handler is registered:
   ```python
   # Must use decorator BEFORE calling get_router()
   @mcp_server.tool_handler()
   async def handle_tool(...):
       pass
   ```

2. Verify tools provider is set:
   ```python
   mcp_server.set_tools_provider(get_tools)
   ```

3. Check logs for errors:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

### Authentication Failures

1. Check PAT prefix matches configuration
2. Verify OAuth JWKS URL is accessible
3. Enable debug logging:
   ```python
   logging.getLogger("common-mcp-server.auth").setLevel(logging.DEBUG)
   ```

### Tool Execution Errors

1. Check API endpoints are accessible from MCP handler
2. Verify authentication tokens are passed correctly
3. Test API endpoints directly with curl first

## Best Practices

1. **Keep tools simple** - Each tool should do one thing well
2. **Use descriptive names** - Tool names should clearly indicate their purpose
3. **Document schemas** - Provide clear descriptions in inputSchema
4. **Handle errors gracefully** - Return user-friendly error messages
5. **Log appropriately** - Use structured logging for debugging
6. **Test thoroughly** - Test with real MCP clients (Claude Code, Claude Desktop)
7. **Version your changes** - Update server version when changing tools

## Next Steps

- Add monitoring and metrics
- Implement rate limiting
- Add request validation
- Create automated tests
- Set up CI/CD pipeline
- Document your specific tools
