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

__all__ = [
    "MCPServer",
    "OAuthConfig",
    "PATConfig",
    "MCPProtocolHandler",
    "__version__",
]
