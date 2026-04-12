"""
Sangkwon MCP Server — 상권 분석 핵심 도구.

Tools:
  - sangkwon_analyze: 상권 종합 분석
  - sangkwon_compare: 복수 지역 비교
  - sangkwon_nearby_similar: 주변 동종 업종 검색
"""
import logging
import re
import sys
from pathlib import Path
from typing import List, Optional

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from mcp_servers.core.base_server import BaseMCPServer
from mcp_servers.core.responses import success_response, error_response
from mcp_servers.adapters.sangkwon_db_adapter import SangkwonDBAdapter
from mcp_servers.adapters.kakao_geocode_adapter import KakaoGeocodeAdapter
from utils.category_codes import resolve_category

logger = logging.getLogger(__name__)

# Pattern for "lat,lng" format — require at least one digit before and after decimal
COORD_PATTERN = re.compile(r"^(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)$")


def _resolve_location(kakao: KakaoGeocodeAdapter, location: str) -> dict:
    """Resolve location string to lat/lng coordinates."""
    m = COORD_PATTERN.match(location.strip())
    if m:
        lat, lng = float(m.group(1)), float(m.group(2))
        # Validate Earth bounds
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            return None
        return {"lat": lat, "lng": lng, "resolved_from": "coordinates"}

    result = kakao.geocode(location)
    if result:
        return {
            "lat": result["lat"],
            "lng": result["lng"],
            "resolved_from": result.get("place_name") or result.get("address") or location,
        }

    return None


class SangkwonServer(BaseMCPServer):
    """상권 분석 MCP 서버."""

    @property
    def name(self) -> str:
        return "sangkwon"

    def __init__(self, **kwargs):
        self._db = SangkwonDBAdapter()
        self._kakao = KakaoGeocodeAdapter()
        super().__init__(**kwargs)

    def _register_tools(self):
        db = self._db
        kakao = self._kakao

        @self.mcp.tool()
        def sangkwon_analyze(
            location: str,
            radius_m: int = 500,
            category: str = None,
        ) -> dict:
            """상권 종합 분석. 반경 내 점포 수, 업종 분포, 경쟁 강도를 반환한다.

            Args:
                location: 지역명(예: '강남역', '홍대입구') 또는 좌표('37.498,127.028')
                radius_m: 분석 반경(미터). 기본 500m
                category: 분석할 업종(예: '카페', '치킨', 'Q12'). 생략하면 전체 업종
            """
            if not db.is_available:
                return error_response("상권 DB가 준비되지 않았습니다. build_db.py를 실행하세요.", code="DB_NOT_FOUND")

            loc = _resolve_location(kakao, location)
            if not loc:
                return error_response(f"'{location}' 위치를 찾을 수 없습니다.", code="LOCATION_NOT_FOUND")

            cat_code = None
            cat_info = None
            if category:
                cat_info = resolve_category(category)
                if cat_info:
                    cat_code = cat_info["code"]

            result = db.analyze(loc["lat"], loc["lng"], radius_m, cat_code)
            result["location_query"] = location
            result["resolved_location"] = loc["resolved_from"]
            if cat_info:
                result["category_info"] = cat_info

            return success_response(
                data=result,
                source="소상공인시장진흥공단 상가정보",
                location=location,
            )

        @self.mcp.tool()
        def sangkwon_compare(
            locations: str,
            radius_m: int = 500,
            category: str = None,
        ) -> dict:
            """복수 지역 상권 비교. 쉼표(;)로 구분된 지역들을 비교 분석한다.

            Args:
                locations: 비교할 지역들, 세미콜론(;)으로 구분. 예: '강남역;홍대입구;합정역'
                radius_m: 분석 반경(미터). 기본 500m
                category: 비교할 업종(예: '카페'). 생략하면 전체
            """
            if not db.is_available:
                return error_response("상권 DB가 준비되지 않았습니다.", code="DB_NOT_FOUND")

            loc_names = [l.strip() for l in locations.split(";") if l.strip()]
            if len(loc_names) < 2:
                return error_response("비교하려면 2개 이상의 지역이 필요합니다. 세미콜론(;)으로 구분하세요.", code="INVALID_INPUT")

            coords = []
            resolved = []
            for name in loc_names:
                loc = _resolve_location(kakao, name)
                if not loc:
                    return error_response(f"'{name}' 위치를 찾을 수 없습니다.", code="LOCATION_NOT_FOUND")
                coords.append((loc["lat"], loc["lng"]))
                resolved.append({"query": name, "resolved": loc["resolved_from"]})

            cat_code = None
            if category:
                cat_info = resolve_category(category)
                if cat_info:
                    cat_code = cat_info["code"]

            result = db.compare(coords, radius_m, cat_code)
            result["location_queries"] = resolved

            return success_response(
                data=result,
                source="소상공인시장진흥공단 상가정보",
            )

        @self.mcp.tool()
        def sangkwon_nearby_similar(
            location: str,
            category: str,
            radius_m: int = 500,
        ) -> dict:
            """주변 동종 업종 검색. 지정 위치 반경 내 같은 업종 점포를 거리순으로 반환한다.

            Args:
                location: 기준 위치(예: '강남역' 또는 '37.498,127.028')
                category: 검색할 업종(예: '카페', '치킨')
                radius_m: 검색 반경(미터). 기본 500m
            """
            if not db.is_available:
                return error_response("상권 DB가 준비되지 않았습니다.", code="DB_NOT_FOUND")

            loc = _resolve_location(kakao, location)
            if not loc:
                return error_response(f"'{location}' 위치를 찾을 수 없습니다.", code="LOCATION_NOT_FOUND")

            cat_info = resolve_category(category)
            if not cat_info:
                return error_response(f"'{category}' 업종을 인식할 수 없습니다.", code="CATEGORY_NOT_FOUND")

            stores = db.nearby_similar(loc["lat"], loc["lng"], cat_info["code"], radius_m)

            return success_response(
                data=stores,
                source="소상공인시장진흥공단 상가정보",
                location=location,
                category=cat_info,
                radius_m=radius_m,
            )
