"""Load integration config (calendar, vector DB, shopping pipeline MCP servers)."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from src.mcp.client import McpServerConfig

INTEGRATIONS_PATH = Path(os.getenv("INTEGRATIONS_CONFIG", "config/integrations.yaml"))


@lru_cache
def load_integrations() -> dict:
    if not INTEGRATIONS_PATH.exists():
        return {}
    return yaml.safe_load(INTEGRATIONS_PATH.read_text()) or {}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, default)
    return str(raw).lower() in ("1", "true", "yes", "on")


def _merge_env_headers(cfg: dict[str, Any], header_env_map: dict[str, str]) -> dict[str, str]:
    headers = dict(cfg.get("headers") or {})
    for header_name, env_var in header_env_map.items():
        if os.getenv(env_var):
            headers.setdefault(header_name, os.environ[env_var])
    return headers


def _parse_mcp_server(name: str, cfg: dict[str, Any]) -> McpServerConfig | None:
    if not cfg:
        return None

    env_toggle = {
        "exa": "EXA_ENABLED",
        "google_shopping": "GOOGLE_SHOPPING_ENABLED",
        "amazon_rainforest": "AMAZON_RAINFOREST_ENABLED",
    }.get(name)
    if env_toggle and os.getenv(env_toggle) is not None:
        if not _env_bool(env_toggle, False):
            return None
    elif not cfg.get("enabled", True):
        return None

    transport = os.getenv(f"MCP_{name.upper()}_TRANSPORT", cfg.get("transport", "stdio"))
    timeout = int(os.getenv(f"MCP_{name.upper()}_TIMEOUT", cfg.get("timeout_seconds", 30)))

    env = dict(cfg.get("env") or {})
    if name == "amazon_rainforest" and os.getenv("RAINFOREST_API_KEY"):
        env.setdefault("RAINFOREST_API_KEY", os.environ["RAINFOREST_API_KEY"])

    command = os.getenv(f"MCP_{name.upper()}_COMMAND", cfg.get("command", "python"))
    args_raw = os.getenv(f"MCP_{name.upper()}_ARGS")
    if args_raw:
        args = args_raw.split()
    else:
        args = list(cfg.get("args") or [])

    url = os.getenv(f"MCP_{name.upper()}_URL", cfg.get("url", ""))
    if name == "exa" and os.getenv("EXA_MCP_URL"):
        url = os.environ["EXA_MCP_URL"]
    tool_name = os.getenv(f"MCP_{name.upper()}_TOOL", cfg.get("tool_name", ""))
    arg_key = os.getenv(f"MCP_{name.upper()}_ARG_KEY", cfg.get("tool_argument_key", "query"))

    headers = _merge_env_headers(
        cfg,
        {
            "x-api-key": "EXA_API_KEY",
            "Authorization": "SERPAPI_KEY",
        },
    )

    return McpServerConfig(
        transport=transport,
        command=command,
        args=args,
        url=url,
        headers=headers,
        env=env or None,
        timeout_seconds=timeout,
        tool_name=tool_name,
        arguments=cfg.get("arguments"),
        tool_argument_key=arg_key,
    )


def get_shopping_pipeline_settings() -> dict[str, Any]:
    """Two-phase shopping pipeline: Exa discovery + retail verification MCP servers."""
    cfg = load_integrations().get("product_search", {})
    pipeline_cfg = dict(cfg.get("pipeline") or {})
    servers_cfg = dict(cfg.get("servers") or {})

    enabled = _env_bool("PRODUCT_SEARCH_ENABLED", cfg.get("enabled", False))
    discovery_enabled = enabled and _env_bool(
        "DISCOVERY_ENABLED",
        pipeline_cfg.get("discovery_enabled", True),
    )
    verification_enabled = enabled and _env_bool(
        "VERIFICATION_ENABLED",
        pipeline_cfg.get("verification_enabled", True),
    )

    discovery = _parse_mcp_server("exa", servers_cfg.get("exa") or {})
    google_shopping = _parse_mcp_server(
        "google_shopping", servers_cfg.get("google_shopping") or {}
    )
    amazon_rainforest = _parse_mcp_server(
        "amazon_rainforest", servers_cfg.get("amazon_rainforest") or {}
    )

    verify_top_n = int(
        os.getenv("VERIFY_TOP_N", pipeline_cfg.get("verify_top_n", 3))
    )

    return {
        "enabled": enabled,
        "discovery_enabled": discovery_enabled and discovery is not None,
        "verification_enabled": verification_enabled
        and (google_shopping is not None or amazon_rainforest is not None),
        "verify_top_n": verify_top_n,
        "discovery": discovery,
        "google_shopping": google_shopping,
        "amazon_rainforest": amazon_rainforest,
    }


def is_discovery_enabled() -> bool:
    return get_shopping_pipeline_settings()["discovery_enabled"]


def is_verification_enabled() -> bool:
    return get_shopping_pipeline_settings()["verification_enabled"]


def is_product_search_enabled() -> bool:
    """True when discovery or verification MCP is configured and enabled."""
    settings = get_shopping_pipeline_settings()
    return settings["discovery_enabled"] or settings["verification_enabled"]
