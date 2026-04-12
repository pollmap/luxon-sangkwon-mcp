"""
Base MCP Server class using FastMCP.

Provides: caching, rate limiting, error handling, logging.
"""
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional
import sys
from functools import wraps

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastmcp import FastMCP

from mcp_servers.core.cache_manager import CacheManager, get_cache
from mcp_servers.core.rate_limiter import RateLimiter, get_limiter
from mcp_servers.core.responses import error_response

logger = logging.getLogger(__name__)


class BaseMCPServer(ABC):
    """Abstract base class for MCP servers."""

    def __init__(self, cache: CacheManager = None, limiter: RateLimiter = None, debug: bool = False):
        self._cache = cache or get_cache()
        self._limiter = limiter or get_limiter()
        if debug:
            logging.basicConfig(level=logging.DEBUG)
        self._mcp = FastMCP(self.name)
        self._register_tools()
        logger.info(f"Initialized MCP server: {self.name}")

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def _register_tools(self) -> None:
        pass

    @property
    def mcp(self) -> FastMCP:
        return self._mcp

    def _cached_request(self, key: Any, fetch_func: callable, data_type: str = "default", namespace: str = None) -> Any:
        ns = namespace or self.name
        result = self._cache.get(ns, key)
        if result is not None:
            return result
        result = fetch_func()
        if result is not None:
            self._cache.set(ns, key, result, data_type)
        return result

    def _rate_limited(self, service: str = None) -> bool:
        return self._limiter.acquire(service or self.name, wait=True)

    def get_cache_stats(self) -> Dict[str, Any]:
        return self._cache.get_stats()

    def get_rate_limit_stats(self) -> Dict[str, Any]:
        return self._limiter.get_stats()


class ToolError(Exception):
    def __init__(self, message: str, code: str = "TOOL_ERROR", details: Any = None):
        super().__init__(message)
        self.code = code
        self.details = details


def tool_handler(func):
    """Decorator for MCP tool handlers with standard error handling."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ToolError as e:
            return error_response(str(e), code=e.code)
        except Exception as e:
            logger.exception(f"Tool error in {func.__name__}")
            return error_response(str(e), code="INTERNAL_ERROR")
    return wrapper


def async_tool_handler(func):
    """Async version of tool_handler decorator."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except ToolError as e:
            return error_response(str(e), code=e.code)
        except Exception as e:
            logger.exception(f"Tool error in {func.__name__}")
            return error_response(str(e), code="INTERNAL_ERROR")
    return wrapper
