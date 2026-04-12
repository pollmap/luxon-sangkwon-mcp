"""
Status MCP Server — 서버 상태 조회.

Tools:
  - maps_status: 전체 서버 상태 (DB 통계, API 가용성, 캐시)
"""
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from mcp_servers.core.base_server import BaseMCPServer
from mcp_servers.core.responses import success_response
from mcp_servers.adapters.sangkwon_db_adapter import SangkwonDBAdapter
from mcp_servers.adapters.kakao_geocode_adapter import KakaoGeocodeAdapter

logger = logging.getLogger(__name__)


class StatusServer(BaseMCPServer):
    """서버 상태 MCP 서버."""

    @property
    def name(self) -> str:
        return "status"

    def __init__(self, **kwargs):
        self._db = SangkwonDBAdapter()
        self._kakao = KakaoGeocodeAdapter()
        super().__init__(**kwargs)

    def _register_tools(self):
        db = self._db
        kakao = self._kakao

        @self.mcp.tool()
        def maps_status() -> dict:
            """Luxon Sangkwon MCP 서버의 전체 상태를 반환한다. DB 통계, API 가용성, 캐시 히트율 등."""
            db_stats = db.get_stats()

            return success_response(
                data={
                    "server": "luxon-sangkwon-mcp",
                    "version": "1.0.0",
                    "database": db_stats,
                    "apis": {
                        "kakao_geocode": {"available": kakao.is_available},
                    },
                    "cache": self.get_cache_stats(),
                    "rate_limits": self.get_rate_limit_stats(),
                },
                source="luxon-sangkwon-mcp",
            )
