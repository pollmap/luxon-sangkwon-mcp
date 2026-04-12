"""
Maps MCP Server — 지오코딩 + POI 검색.

Tools:
  - geocode: 주소/지역명 → 좌표
  - reverse_geocode: 좌표 → 주소
  - poi_search: POI 검색
"""
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from mcp_servers.core.base_server import BaseMCPServer
from mcp_servers.core.responses import success_response, error_response
from mcp_servers.adapters.kakao_geocode_adapter import KakaoGeocodeAdapter

logger = logging.getLogger(__name__)


class MapsServer(BaseMCPServer):
    """지도/지오코딩 MCP 서버."""

    @property
    def name(self) -> str:
        return "maps"

    def __init__(self, **kwargs):
        self._kakao = KakaoGeocodeAdapter()
        super().__init__(**kwargs)

    def _register_tools(self):
        kakao = self._kakao

        @self.mcp.tool()
        def geocode(address: str) -> dict:
            """주소 또는 지역명을 좌표로 변환한다.

            Args:
                address: 주소 또는 지역명 (예: '강남역', '서울 강남구 역삼동 123')
            """
            if not kakao.is_available:
                return error_response("카카오 API 키가 설정되지 않았습니다.", code="API_UNAVAILABLE")

            result = kakao.geocode(address)
            if not result:
                return error_response(f"'{address}'에 대한 좌표를 찾을 수 없습니다.", code="NOT_FOUND")

            return success_response(data=result, source="Kakao Local API")

        @self.mcp.tool()
        def reverse_geocode(lat: float, lng: float) -> dict:
            """좌표를 주소로 변환한다.

            Args:
                lat: 위도 (예: 37.498)
                lng: 경도 (예: 127.028)
            """
            if not kakao.is_available:
                return error_response("카카오 API 키가 설정되지 않았습니다.", code="API_UNAVAILABLE")

            result = kakao.reverse_geocode(lat, lng)
            if not result:
                return error_response(f"좌표 ({lat}, {lng})에 대한 주소를 찾을 수 없습니다.", code="NOT_FOUND")

            return success_response(data=result, source="Kakao Local API")

        @self.mcp.tool()
        def poi_search(
            query: str,
            location: str = None,
            radius_m: int = None,
        ) -> dict:
            """장소(POI)를 검색한다. 키워드와 위치 기반으로 주변 장소를 찾는다.

            Args:
                query: 검색 키워드 (예: '스타벅스', '주차장')
                location: 기준 위치 (예: '강남역'). 생략하면 키워드만으로 검색
                radius_m: 검색 반경(미터, 최대 20000). location이 있을 때만 유효
            """
            if not kakao.is_available:
                return error_response("카카오 API 키가 설정되지 않았습니다.", code="API_UNAVAILABLE")

            lat, lng = None, None
            if location:
                loc = kakao.geocode(location)
                if loc:
                    lat, lng = loc["lat"], loc["lng"]

            results = kakao.search_poi(query, lat=lat, lng=lng, radius=radius_m)
            return success_response(data=results, source="Kakao Local API")
