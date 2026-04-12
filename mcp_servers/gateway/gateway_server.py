"""
Gateway Server — FastMCP mount 패턴으로 모든 서버를 하나로 통합.
"""
import importlib
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastmcp import FastMCP

logger = logging.getLogger(__name__)

# (key, module_path, class_name)
SERVERS = [
    ("sangkwon", "mcp_servers.servers.sangkwon_server", "SangkwonServer"),
    ("maps", "mcp_servers.servers.maps_server", "MapsServer"),
    ("density", "mcp_servers.servers.density_server", "DensityServer"),
    ("status", "mcp_servers.servers.status_server", "StatusServer"),
]


class GatewayServer:
    """Unified gateway aggregating all sub-servers."""

    def __init__(self):
        self.mcp = FastMCP("luxon-sangkwon-mcp")
        self._loaded = []
        self._failed = []

        for key, module_path, class_name in SERVERS:
            self._load_server(key, module_path, class_name)

        logger.info(
            f"Gateway initialized: {len(self._loaded)} loaded, {len(self._failed)} failed"
        )

    def _load_server(self, key: str, module_path: str, class_name: str):
        """Dynamically load and mount a sub-server."""
        try:
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name)
            instance = cls()
            sub = instance.mcp
            self.mcp.mount(sub)
            self._loaded.append(key)
            logger.info(f"  + {key} (mounted)")
        except Exception as e:
            self._failed.append(key)
            logger.error(f"  x {key} failed: {e}")
