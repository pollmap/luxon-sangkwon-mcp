"""
Density MCP Server — 상권 밀도 분석.

Tools:
  - sangkwon_density_map: 격자 기반 밀도 분석
"""
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from mcp_servers.core.base_server import BaseMCPServer
from mcp_servers.core.responses import success_response, error_response
from mcp_servers.adapters.sangkwon_db_adapter import SangkwonDBAdapter
from mcp_servers.adapters.kakao_geocode_adapter import KakaoGeocodeAdapter
from mcp_servers.servers.sangkwon_server import _resolve_location
from utils.category_codes import resolve_category

logger = logging.getLogger(__name__)


class DensityServer(BaseMCPServer):
    """상권 밀도 분석 MCP 서버."""

    @property
    def name(self) -> str:
        return "density"

    def __init__(self, **kwargs):
        self._db = SangkwonDBAdapter()
        self._kakao = KakaoGeocodeAdapter()
        super().__init__(**kwargs)

    def _register_tools(self):
        db = self._db
        kakao = self._kakao

        @self.mcp.tool()
        def sangkwon_density_map(
            location: str,
            radius_m: int = 1000,
            category: str = None,
            cell_size_m: int = 100,
        ) -> dict:
            """상권 밀도 격자 분석. 지정 영역을 격자로 나누어 각 셀의 점포 밀도를 반환한다.

            Args:
                location: 중심 위치 (예: '강남역')
                radius_m: 분석 반경(미터). 기본 1000m
                category: 분석 업종 (예: '카페'). 생략하면 전체
                cell_size_m: 격자 셀 크기(미터). 기본 100m
            """
            if not db.is_available:
                return error_response("상권 DB가 준비되지 않았습니다.", code="DB_NOT_FOUND")

            loc = _resolve_location(kakao, location)
            if not loc:
                return error_response(f"'{location}' 위치를 찾을 수 없습니다.", code="LOCATION_NOT_FOUND")

            cat_code = None
            if category:
                cat_info = resolve_category(category)
                if cat_info:
                    cat_code = cat_info["code"]

            result = db.density_grid(
                loc["lat"], loc["lng"],
                radius_m=radius_m,
                category_m=cat_code,
                cell_size_m=cell_size_m,
            )
            result["location_query"] = location
            result["resolved_location"] = loc["resolved_from"]

            return success_response(
                data=result,
                source="소상공인시장진흥공단 상가정보",
            )
