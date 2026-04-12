"""
Nexus Finance MCP Bridge Adapter.

Calls nexus-finance-mcp (port 8100) via MCP JSON-RPC over HTTP
to get macroeconomic data for startup scoring.
"""
import json
import logging
import os
import sys
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from mcp_servers.core.cache_manager import get_cache
from mcp_servers.core.rate_limiter import get_limiter

logger = logging.getLogger(__name__)


class NexusBridgeAdapter:
    """Bridge to nexus-finance-mcp for macroeconomic data."""

    def __init__(self, base_url: str = None, cache=None, limiter=None):
        self.base_url = base_url or os.getenv(
            "NEXUS_FINANCE_URL", "http://127.0.0.1:8100/mcp"
        )
        self._cache = cache or get_cache()
        self._limiter = limiter or get_limiter()
        self._session_id = None
        self.is_available = self._check_available()

    def _check_available(self) -> bool:
        """Check if nexus-finance-mcp is reachable."""
        try:
            resp = requests.post(
                self.base_url,
                headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
                json={
                    "jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "sangkwon-bridge", "version": "1.0"},
                    },
                },
                timeout=5,
            )
            if resp.status_code == 200:
                self._session_id = resp.headers.get("mcp-session-id")
                return True
        except Exception:
            pass
        logger.info("NexusBridgeAdapter: nexus-finance-mcp not reachable (optional)")
        return False

    def _call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call a nexus-finance MCP tool via JSON-RPC."""
        if not self.is_available:
            return None

        self._limiter.acquire("nexus_finance", wait=True)

        cache_key = {"bridge": tool_name, **arguments}
        cached = self._cache.get("nexus_bridge", cache_key)
        if cached:
            return cached

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        try:
            resp = requests.post(
                self.base_url,
                headers=headers,
                json={
                    "jsonrpc": "2.0", "id": 2,
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": arguments},
                },
                timeout=10,
            )

            # Parse SSE response
            for line in resp.text.split("\n"):
                line = line.strip()
                if line.startswith("data:"):
                    data = json.loads(line[5:].strip())
                    if "result" in data:
                        content = data["result"].get("content", [])
                        if content:
                            result = json.loads(content[0].get("text", "{}"))
                            self._cache.set("nexus_bridge", cache_key, result, "daily_data")
                            return result
        except Exception as e:
            logger.warning(f"Nexus bridge call failed ({tool_name}): {e}")

        return None

    def get_base_rate(self) -> dict:
        """Get Korean base interest rate from BOK ECOS."""
        return self._call_tool("get_base_rate", {"year": 2026})

    def get_cpi(self) -> dict:
        """Get Consumer Price Index from KOSIS."""
        return self._call_tool("get_cpi", {})

    def get_macro_score(self) -> float:
        """
        Get normalized macroeconomic conditions score (0-100).
        Higher = more favorable for new business.

        Factors: low interest rate = good, low CPI growth = good.
        """
        # If nexus is down, return None (graceful degradation)
        if not self.is_available:
            return None

        # Try to get base rate
        rate_data = self.get_base_rate()
        if not rate_data or not rate_data.get("success"):
            return None

        # Simple heuristic: lower rate = better for startups
        # Korean base rate range: 0.5% ~ 5%
        try:
            rate_value = float(rate_data.get("data", {}).get("rate", 3.5))
            from utils.scoring import normalize_score
            return normalize_score(rate_value, 0.5, 5.0, invert=True)
        except (ValueError, TypeError):
            return None
