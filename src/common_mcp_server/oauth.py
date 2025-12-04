"""OAuth 2.1 endpoints for MCP authentication.

Provides OAuth discovery endpoints (RFC 8414, RFC 9728) and proxies
authorization/token requests to Keycloak.

This module is designed for Originate Group applications that share:
- A common Keycloak instance (auth.originate.group)
- A shared realm (originate)
- A shared public client (originate-api)

Each application only needs to provide its own resource_url (base URL).

Environment Variables (from GitHub organization/repo variables):
- KEYCLOAK_URL: Keycloak base URL (org-level, e.g., https://auth.originate.group)
- KEYCLOAK_REALM: Keycloak realm name (org-level, e.g., originate)
- KEYCLOAK_CLIENT_ID: Shared client ID (org-level, e.g., originate-api)
- <APP>_BASE_URL: Application base URL (repo-level, e.g., https://eng.tarkaflow.ai)

Copyright 2025 Originate Group
Licensed under the Apache License, Version 2.0
"""

import logging
from dataclasses import dataclass
from typing import Optional

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

logger = logging.getLogger("common-mcp-server.oauth")


@dataclass
class OAuthRouterConfig:
    """Configuration for OAuth router.

    Attributes:
        resource_url: Base URL of this application (e.g., https://eng.tarkaflow.ai)
        keycloak_url: Keycloak base URL (e.g., https://auth.originate.group)
        keycloak_realm: Keycloak realm name (e.g., originate)
        keycloak_client_id: Keycloak client ID (e.g., originate-api)
        service_name: Human-readable service name for registration response
    """

    resource_url: str
    keycloak_url: str
    keycloak_realm: str
    keycloak_client_id: str
    service_name: str = "Originate Service"

    @property
    def keycloak_base(self) -> str:
        """Get the Keycloak realm base URL."""
        return f"{self.keycloak_url}/realms/{self.keycloak_realm}"

    @property
    def keycloak_auth_url(self) -> str:
        """Get the Keycloak authorization endpoint."""
        return f"{self.keycloak_base}/protocol/openid-connect/auth"

    @property
    def keycloak_token_url(self) -> str:
        """Get the Keycloak token endpoint."""
        return f"{self.keycloak_base}/protocol/openid-connect/token"

    @property
    def keycloak_userinfo_url(self) -> str:
        """Get the Keycloak userinfo endpoint."""
        return f"{self.keycloak_base}/protocol/openid-connect/userinfo"

    @property
    def keycloak_jwks_url(self) -> str:
        """Get the Keycloak JWKS endpoint."""
        return f"{self.keycloak_base}/protocol/openid-connect/certs"


def create_oauth_router(config: OAuthRouterConfig) -> APIRouter:
    """Create an OAuth router with the given configuration.

    This router provides all OAuth endpoints required for MCP authentication
    via Claude Desktop Custom Connectors:

    - /.well-known/oauth-authorization-server (RFC 8414)
    - /.well-known/oauth-protected-resource (RFC 9728)
    - /oauth/authorize (proxy to Keycloak)
    - /oauth/token (proxy to Keycloak)
    - /oauth/register (RFC 7591 Dynamic Client Registration)
    - /oauth/userinfo (proxy to Keycloak)

    Args:
        config: OAuth router configuration

    Returns:
        FastAPI APIRouter with OAuth endpoints
    """
    router = APIRouter(tags=["OAuth"])

    @router.get("/.well-known/oauth-authorization-server")
    async def authorization_server_metadata(request: Request) -> JSONResponse:
        """OAuth 2.0 Authorization Server Metadata (RFC 8414).

        Returns metadata about the OAuth authorization server capabilities,
        as required by the MCP specification.
        """
        logger.debug(f"OAuth discovery request from {request.client.host if request.client else 'unknown'}")

        metadata = {
            "issuer": config.keycloak_base,
            "authorization_endpoint": f"{config.resource_url}/oauth/authorize",
            "token_endpoint": f"{config.resource_url}/oauth/token",
            "registration_endpoint": f"{config.resource_url}/oauth/register",
            "jwks_uri": config.keycloak_jwks_url,
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"],
            "scopes_supported": ["openid", "profile", "email", "offline_access"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": ["RS256"],
            "claims_supported": [
                "sub",
                "iss",
                "aud",
                "exp",
                "iat",
                "email",
                "email_verified",
                "name",
                "preferred_username",
            ],
            "resource_parameter_supported": True,
            "service_documentation": f"{config.resource_url}/docs",
        }

        return JSONResponse(content=metadata)

    @router.get("/.well-known/oauth-protected-resource")
    async def protected_resource_metadata(request: Request) -> JSONResponse:
        """OAuth 2.0 Protected Resource Metadata (RFC 9728).

        Returns metadata about the protected resource (MCP server)
        and its authorization requirements.
        """
        metadata = {
            "resource": f"{config.resource_url}/mcp",
            "authorization_servers": [config.resource_url],
            "bearer_methods_supported": ["header"],
            "resource_signing_alg_values_supported": ["RS256"],
            "scopes_supported": ["openid", "profile", "email"],
            "resource_documentation": f"{config.resource_url}/docs",
            "mcp_endpoints": [f"{config.resource_url}/mcp"],
        }

        return JSONResponse(content=metadata)

    @router.get("/oauth/authorize")
    async def authorize(request: Request) -> RedirectResponse:
        """OAuth authorization endpoint (proxy to Keycloak).

        Proxies authorization requests to Keycloak, preserving all query
        parameters required for the OAuth authorization code flow with PKCE.
        """
        query_params = dict(request.query_params)

        logger.debug(f"Authorization request: client_id={query_params.get('client_id')}")

        # Build Keycloak authorization URL with all parameters
        params_str = "&".join(f"{k}={v}" for k, v in query_params.items())
        keycloak_url = f"{config.keycloak_auth_url}?{params_str}"

        return RedirectResponse(url=keycloak_url, status_code=302)

    @router.post("/oauth/token")
    async def token(request: Request) -> Response:
        """OAuth token endpoint (proxy to Keycloak).

        Proxies token requests to Keycloak for:
        - Authorization code exchange
        - Refresh token exchange
        """
        form_data = await request.form()
        form_dict = dict(form_data)

        logger.debug(f"Token request: grant_type={form_dict.get('grant_type')}")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    config.keycloak_token_url,
                    data=form_dict,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=30.0,
                )

                if response.status_code != 200:
                    logger.warning(f"Keycloak token error: {response.status_code}")

                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    media_type="application/json",
                )
            except httpx.RequestError as e:
                logger.error(f"Token request failed: {e}")
                return JSONResponse(
                    status_code=502,
                    content={"error": "server_error", "error_description": str(e)},
                )

    @router.post("/oauth/register")
    async def register(request: Request) -> JSONResponse:
        """OAuth 2.0 Dynamic Client Registration (RFC 7591).

        Returns the pre-configured Keycloak client for all Custom Connector
        requests. All Custom Connector instances share the same OAuth client.

        The Keycloak client must be configured to allow:
        - redirect_uri: https://claude.ai/api/mcp/auth_callback
        - Public client (no client secret)
        - Authorization Code Flow with PKCE
        """
        try:
            body = await request.json()
            client_name = body.get("client_name", "MCP Client")
            redirect_uris = body.get("redirect_uris", [])

            logger.debug(f"Client registration: {client_name}, uris={redirect_uris}")

            response_data = {
                "client_id": config.keycloak_client_id,
                "client_secret": "",
                "client_name": client_name,
                "redirect_uris": redirect_uris,
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "token_endpoint_auth_method": "none",
                "application_type": "web",
            }

            return JSONResponse(
                status_code=201,
                content=response_data,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Cache-Control": "no-store",
                },
            )

        except Exception as e:
            logger.error(f"Client registration failed: {e}")
            return JSONResponse(
                status_code=400,
                content={
                    "error": "invalid_client_metadata",
                    "error_description": str(e),
                },
                headers={"Access-Control-Allow-Origin": "*"},
            )

    @router.get("/oauth/userinfo")
    async def userinfo(request: Request) -> Response:
        """OAuth UserInfo endpoint (proxy to Keycloak).

        Returns user information for the authenticated user based on
        the provided access token.
        """
        auth_header = request.headers.get("Authorization")

        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"error": "invalid_token"},
            )

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    config.keycloak_userinfo_url,
                    headers={"Authorization": auth_header},
                    timeout=30.0,
                )

                return Response(
                    content=response.content,
                    status_code=response.status_code,
                    media_type="application/json",
                )
            except httpx.RequestError as e:
                logger.error(f"UserInfo request failed: {e}")
                return JSONResponse(
                    status_code=502,
                    content={"error": "server_error"},
                )

    @router.options("/oauth/register")
    @router.options("/oauth/token")
    @router.options("/oauth/authorize")
    async def oauth_options() -> Response:
        """Handle CORS preflight requests for OAuth endpoints."""
        return Response(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization",
            },
        )

    return router
