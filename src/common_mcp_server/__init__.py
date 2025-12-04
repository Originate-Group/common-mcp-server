"""Common MCP Server - Reusable HTTP MCP Server Framework.

A production-ready framework for building MCP (Model Context Protocol) servers
with FastAPI, supporting both OAuth 2.1 and Personal Access Token authentication.

Copyright 2025 Originate Group
Licensed under the Apache License, Version 2.0
"""

__version__ = "1.0.0"

from .server import MCPServer
from .auth import OAuthConfig, PATConfig
from .protocol import MCPProtocolHandler
from .oauth import OAuthRouterConfig, create_oauth_router

__all__ = [
    "MCPServer",
    "OAuthConfig",
    "PATConfig",
    "MCPProtocolHandler",
    "OAuthRouterConfig",
    "create_oauth_router",
    "__version__",
]
