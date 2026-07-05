"""MCP client — call tools on configured MCP servers (stdio or HTTP)."""

from __future__ import annotations

import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("gift_assistant.mcp")

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="mcp-client")

_ENV_PLACEHOLDER = re.compile(r"\{([A-Z0-9_]+)\}")


@dataclass
class McpServerConfig:
    """Connection settings for one MCP server."""

    transport: str = "stdio"  # stdio | http
    command: str = "npx"
    args: list[str] = field(default_factory=list)
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    env: dict[str, str] | None = None
    timeout_seconds: int = 30
    tool_name: str = ""
    arguments: dict[str, Any] | None = None
    tool_argument_key: str = "query"


def resolve_env_placeholders(value: str) -> str:
    """Replace {ENV_VAR} tokens from os.environ."""

    import os

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        return os.environ.get(key, match.group(0))

    return _ENV_PLACEHOLDER.sub(repl, value)


def resolve_env_in_mapping(data: Any) -> Any:
    """Recursively resolve {ENV_VAR} placeholders in strings."""

    if isinstance(data, str):
        return resolve_env_placeholders(data)
    if isinstance(data, list):
        return [resolve_env_in_mapping(item) for item in data]
    if isinstance(data, dict):
        return {key: resolve_env_in_mapping(val) for key, val in data.items()}
    return data


def build_tool_arguments(config: McpServerConfig, query: str) -> dict[str, Any]:
    """Build MCP tool arguments from config template or simple query key."""

    if config.arguments:
        args = resolve_env_in_mapping(config.arguments)
        return _substitute_query_token(args, query)

    key = config.tool_argument_key or "query"
    return {key: query}


def _substitute_query_token(data: Any, query: str) -> Any:
    if isinstance(data, str):
        return data.replace("{query}", query)
    if isinstance(data, list):
        return [_substitute_query_token(item, query) for item in data]
    if isinstance(data, dict):
        return {key: _substitute_query_token(val, query) for key, val in data.items()}
    return data


def extract_tool_text(result: Any) -> str:
    """Flatten MCP CallToolResult content blocks to plain text."""
    if result is None:
        return ""
    if getattr(result, "isError", False):
        parts = []
        for block in getattr(result, "content", []) or []:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        raise RuntimeError("; ".join(parts) or "MCP tool returned an error")

    parts: list[str] = []
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
        elif isinstance(block, dict) and block.get("text"):
            parts.append(str(block["text"]))

    structured = getattr(result, "structuredContent", None)
    if structured and not parts:
        parts.append(str(structured))

    return "\n".join(parts).strip()


def extract_tool_text_safe(result: Any) -> str:
    """Like extract_tool_text but returns empty string instead of raising."""
    try:
        return extract_tool_text(result)
    except RuntimeError as exc:
        logger.warning("MCP tool returned error: %s", exc)
        return ""


async def _session_call_many(
    read,
    write,
    calls: list[tuple[str, dict[str, Any]]],
) -> list[str]:
    from mcp import ClientSession

    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        available = [t.name for t in tools.tools]
        logger.info("MCP server tools available: %s", available)

        outputs: list[str] = []
        quota_hit = False
        for tool_name, arguments in calls:
            if quota_hit:
                outputs.append("")
                continue

            name = tool_name
            if name not in available:
                if len(available) == 1:
                    name = available[0]
                else:
                    logger.warning(
                        "MCP tool %r not found; skipping. Available: %s",
                        tool_name,
                        available,
                    )
                    outputs.append("")
                    continue

            result = await session.call_tool(name, arguments=arguments)
            text = extract_tool_text_safe(result)
            if "quota_exceeded" in text or "402 Payment Required" in text:
                quota_hit = True
            if "api_error" in text or "400 Bad Request" in text:
                quota_hit = True
            outputs.append(text)
        return outputs


async def _call_tool_async(
    config: McpServerConfig,
    tool_name: str,
    arguments: dict[str, Any],
) -> str:
    results = await _call_tools_async(config, [(tool_name, arguments)])
    return results[0] if results else ""


async def _call_tools_async(
    config: McpServerConfig,
    calls: list[tuple[str, dict[str, Any]]],
) -> list[str]:
    async def _run() -> list[str]:
        if config.transport == "http":
            import httpx
            from mcp.client.streamable_http import streamable_http_client

            url = resolve_env_placeholders(config.url)
            if not url:
                raise RuntimeError("HTTP MCP server requires a url")

            headers = resolve_env_in_mapping(config.headers)
            timeout = httpx.Timeout(config.timeout_seconds, read=config.timeout_seconds * 2)
            async with httpx.AsyncClient(headers=headers, timeout=timeout) as http_client:
                async with streamable_http_client(url, http_client=http_client) as (
                    read,
                    write,
                ):
                    return await _session_call_many(read, write, calls)

        from mcp import StdioServerParameters
        from mcp.client.stdio import stdio_client

        server_params = StdioServerParameters(
            command=config.command,
            args=config.args,
            env=config.env,
        )
        async with stdio_client(server_params) as (read, write):
            return await _session_call_many(read, write, calls)

    return await asyncio.wait_for(_run(), timeout=config.timeout_seconds * max(len(calls), 1))


def call_mcp_tools(
    config: McpServerConfig,
    calls: list[tuple[str, dict[str, Any]]],
) -> list[str]:
    """Run multiple tool calls on one MCP server session (one stdio process)."""
    if not calls:
        return []

    coro = _call_tools_async(config, calls)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    future = _executor.submit(asyncio.run, coro)
    return future.result(timeout=(config.timeout_seconds + 5) * max(len(calls), 1))


def call_mcp_tool(
    config: McpServerConfig,
    tool_name: str,
    arguments: dict[str, Any],
) -> str:
    """Sync wrapper for Slack / LangGraph (runs async MCP client in a thread)."""
    coro = _call_tool_async(config, tool_name, arguments)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    future = _executor.submit(asyncio.run, coro)
    return future.result(timeout=config.timeout_seconds + 5)


def call_mcp_server(config: McpServerConfig, query: str) -> str:
    """Call the configured tool on an MCP server using its argument template."""
    tool_name = config.tool_name
    if not tool_name:
        raise RuntimeError("MCP server config missing tool_name")
    arguments = build_tool_arguments(config, query)
    logger.info(
        "MCP call transport=%s tool=%s query=%r",
        config.transport,
        tool_name,
        query[:200],
    )
    return call_mcp_tool(config, tool_name, arguments)
