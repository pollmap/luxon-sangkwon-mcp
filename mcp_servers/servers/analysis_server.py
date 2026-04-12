"""
Analysis MCP Server — Phase 2 분석 도구.

Tools:
  - sangkwon_closure_risk: 폐업 리스크 분석
  - sangkwon_startup_score: AI 창업 적합도
  - sangkwon_trend: 상권 트렌드 (분기 비교)
  - sangkwon_hot_areas: 뜨는 상권 랭킹
  - sangkwon_report: 종합 리포트 (마크다운)
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
from mcp_servers.adapters.seoul_golmok_adapter import SeoulGolmokAdapter
from mcp_servers.adapters.nexus_bridge_adapter import NexusBridgeAdapter
from mcp_servers.servers.sangkwon_server import _resolve_location
from utils.category_codes import resolve_category
from utils.scoring import normalize_score, weighted_composite, score_to_grade, STARTUP_GRADES
from utils.hot_area_candidates import get_candidates_by_city

logger = logging.getLogger(__name__)


class AnalysisServer(BaseMCPServer):
    """Phase 2 분석 도구 MCP 서버."""

    @property
    def name(self) -> str:
        return "analysis"

    def __init__(self, **kwargs):
        self._db = SangkwonDBAdapter()
        self._kakao = KakaoGeocodeAdapter()
        self._seoul = SeoulGolmokAdapter()
        self._nexus = NexusBridgeAdapter()
        super().__init__(**kwargs)

    def _register_tools(self):
        db = self._db
        kakao = self._kakao
        seoul = self._seoul
        nexus = self._nexus

        @self.mcp.tool()
        def sangkwon_closure_risk(
            location: str,
            category: str = None,
            radius_m: int = 500,
        ) -> dict:
            """상권 폐업 리스크 분석. 반경 내 영업/폐업/휴업 비율과 위험 등급을 반환한다.

            Args:
                location: 기준 위치 (예: '강남역')
                category: 업종 (예: '카페'). 생략하면 전체
                radius_m: 분석 반경(미터). 기본 500m
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

            result = db.closure_stats(loc["lat"], loc["lng"], radius_m, cat_code)
            result["location_query"] = location
            result["resolved_location"] = loc["resolved_from"]
            result["radius_m"] = radius_m

            return success_response(
                data=result,
                source="소상공인시장진흥공단 상가정보",
                location=location,
            )

        @self.mcp.tool()
        def sangkwon_startup_score(
            location: str,
            category: str,
            budget: int = None,
        ) -> dict:
            """AI 창업 적합도 점수. 경쟁밀도, 폐업리스크, 유동인구, 경제지표를 종합 평가한다.

            Args:
                location: 창업 희망 위치 (예: '합정역')
                category: 창업 업종 (예: '카페', '치킨')
                budget: 예산(만원, 선택). 미입력 시 예산 무관 평가
            """
            if not db.is_available:
                return error_response("상권 DB가 준비되지 않았습니다.", code="DB_NOT_FOUND")

            loc = _resolve_location(kakao, location)
            if not loc:
                return error_response(f"'{location}' 위치를 찾을 수 없습니다.", code="LOCATION_NOT_FOUND")

            cat_info = resolve_category(category)
            if not cat_info:
                return error_response(f"'{category}' 업종을 인식할 수 없습니다.", code="CATEGORY_NOT_FOUND")
            cat_code = cat_info["code"]

            # Factor 1: Competition density (30%) — lower = better
            analysis = db.analyze(loc["lat"], loc["lng"], 500, cat_code)
            comp_score = normalize_score(
                analysis.get("competition_score", 50), 0, 100, invert=True
            )

            # Factor 2: Category saturation (20%) — lower = better
            total = analysis.get("total_stores", 1)
            filtered = analysis.get("filtered_stores", 0)
            saturation_pct = filtered / total * 100 if total > 0 else 0
            saturation_score = normalize_score(saturation_pct, 0, 30, invert=True)

            # Factor 3: Closure risk (20%) — lower closure = better
            closure = db.closure_stats(loc["lat"], loc["lng"], 500, cat_code)
            closure_rate = closure.get("closure_rate_pct", 15)
            closure_score = normalize_score(closure_rate, 0, 40, invert=True)

            # Factor 4: Foot traffic (15%, Seoul only)
            foot_score = seoul.get_foot_traffic_score() if seoul.is_available else None

            # Factor 5: Macro conditions (15%)
            macro_score = nexus.get_macro_score() if nexus.is_available else None

            # Weighted composite
            scores = {
                "competition": comp_score,
                "saturation": saturation_score,
                "closure_risk": closure_score,
                "foot_traffic": foot_score,
                "macro": macro_score,
            }
            weights = {
                "competition": 0.30,
                "saturation": 0.20,
                "closure_risk": 0.20,
                "foot_traffic": 0.15,
                "macro": 0.15,
            }

            overall = weighted_composite(scores, weights)
            grade = score_to_grade(overall, STARTUP_GRADES)

            # Build recommendation text
            if overall >= 80:
                verdict = "창업 적합 지역입니다. 경쟁이 적고 조건이 유리합니다."
            elif overall >= 60:
                verdict = "적합한 편이나 일부 리스크 요인이 있습니다. 차별화 전략을 준비하세요."
            elif overall >= 40:
                verdict = "보통 수준입니다. 경쟁이 있으나 진입 불가능하지는 않습니다."
            elif overall >= 20:
                verdict = "부적합한 편입니다. 높은 경쟁 또는 폐업 리스크가 있습니다."
            else:
                verdict = "매우 부적합합니다. 다른 위치나 업종을 검토하세요."

            result = {
                "overall_score": overall,
                "grade": grade,
                "verdict": verdict,
                "breakdown": {
                    k: {"score": round(v, 1) if v is not None else None, "weight": weights[k]}
                    for k, v in scores.items()
                },
                "factors_available": sum(1 for v in scores.values() if v is not None),
                "factors_total": len(scores),
                "location_query": location,
                "resolved_location": loc["resolved_from"],
                "category": cat_info,
                "budget": budget,
            }

            return success_response(data=result, source="Luxon AI Startup Score")

        @self.mcp.tool()
        def sangkwon_trend(
            location: str,
            category: str = None,
            radius_m: int = 500,
        ) -> dict:
            """상권 트렌드 분석. 분기별 점포 수 변화를 반환한다.

            Args:
                location: 기준 위치 (예: '성수동')
                category: 업종 (예: '카페'). 생략하면 전체
                radius_m: 분석 반경(미터). 기본 500m
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

            result = db.snapshot_compare(loc["lat"], loc["lng"], radius_m, cat_code)
            result["location_query"] = location
            result["resolved_location"] = loc["resolved_from"]

            return success_response(data=result, source="소상공인시장진흥공단 상가정보")

        @self.mcp.tool()
        def sangkwon_hot_areas(
            category: str,
            city: str = None,
            top_n: int = 10,
        ) -> dict:
            """뜨는 상권 랭킹. 경쟁이 낮고 조건이 좋은 상권을 찾아 순위를 매긴다.

            Args:
                category: 분석 업종 (예: '카페', '치킨')
                city: 도시 필터 (예: '서울특별시', '부산광역시'). 생략하면 전국
                top_n: 반환할 상위 결과 수. 기본 10
            """
            if not db.is_available:
                return error_response("상권 DB가 준비되지 않았습니다.", code="DB_NOT_FOUND")

            cat_info = resolve_category(category)
            if not cat_info:
                return error_response(f"'{category}' 업종을 인식할 수 없습니다.", code="CATEGORY_NOT_FOUND")
            cat_code = cat_info["code"]

            candidates = get_candidates_by_city(city)
            locations = [(name, lat, lng) for name, lat, lng, _ in candidates]

            # Batch analyze
            results = db.area_aggregate(locations, cat_code, radius_m=500)

            # Sort by: lowest competition score (best for new entry)
            results.sort(key=lambda x: x["competition_score"])

            top = results[:max(1, min(top_n, 50))]

            # Add rank
            for i, r in enumerate(top):
                r["rank"] = i + 1

            return success_response(
                data={
                    "rankings": top,
                    "category": cat_info,
                    "city_filter": city,
                    "total_candidates": len(candidates),
                },
                source="Luxon AI Hot Area Ranking",
            )

        @self.mcp.tool()
        def sangkwon_report(
            location: str,
            category: str,
            radius_m: int = 500,
        ) -> dict:
            """종합 상권 분석 리포트. 상권현황, 경쟁분석, 폐업리스크, 창업적합도를 마크다운으로 반환한다.

            Args:
                location: 분석 위치 (예: '강남역')
                category: 분석 업종 (예: '카페')
                radius_m: 분석 반경(미터). 기본 500m
            """
            if not db.is_available:
                return error_response("상권 DB가 준비되지 않았습니다.", code="DB_NOT_FOUND")

            loc = _resolve_location(kakao, location)
            if not loc:
                return error_response(f"'{location}' 위치를 찾을 수 없습니다.", code="LOCATION_NOT_FOUND")

            cat_info = resolve_category(category)
            cat_code = cat_info["code"] if cat_info else None
            cat_name = cat_info["name"] if cat_info else category

            # Gather all data
            analysis = db.analyze(loc["lat"], loc["lng"], radius_m, cat_code)
            closure = db.closure_stats(loc["lat"], loc["lng"], radius_m, cat_code)
            nearby = db.nearby_similar(loc["lat"], loc["lng"], cat_code, radius_m, limit=10) if cat_code else []

            # Startup score (inline calculation)
            comp_score = normalize_score(analysis.get("competition_score", 50), 0, 100, invert=True)
            total = analysis.get("total_stores", 1)
            filtered = analysis.get("filtered_stores", 0)
            sat_pct = filtered / total * 100 if total > 0 else 0
            sat_score = normalize_score(sat_pct, 0, 30, invert=True)
            cl_score = normalize_score(closure.get("closure_rate_pct", 15), 0, 40, invert=True)
            startup = weighted_composite(
                {"competition": comp_score, "saturation": sat_score, "closure_risk": cl_score},
                {"competition": 0.30, "saturation": 0.20, "closure_risk": 0.20},
            )
            startup_grade = score_to_grade(startup, STARTUP_GRADES)

            # Build markdown
            resolved = loc["resolved_from"]
            md = f"""# 상권 분석 리포트: {resolved}

**분석 일시**: {analysis.get('data_date', 'N/A')}
**분석 반경**: {radius_m}m | **업종**: {cat_name}

---

## 1. 요약

| 항목 | 값 |
|------|-----|
| 총 점포 수 | {analysis.get('total_stores', 0):,}개 |
| {cat_name} 점포 수 | {filtered:,}개 |
| 경쟁 점수 | {analysis.get('competition_score', 0)}/100 ({analysis.get('competition_grade', '')}) |
| 폐업률 | {closure.get('closure_rate_pct', 0)}% ({closure.get('risk_grade', '')}) |
| 창업 적합도 | {startup:.0f}/100 ({startup_grade}) |

---

## 2. 업종 분포

| 순위 | 업종 | 점포 수 | 비율 |
|------|------|---------|------|
"""
            for i, cat in enumerate(analysis.get("category_distribution", [])[:10], 1):
                md += f"| {i} | {cat['name']} | {cat['count']}개 | {cat['pct']}% |\n"

            md += f"""
---

## 3. 경쟁 분석

- **경쟁 점수**: {analysis.get('competition_score', 0)}/100
- **경쟁 등급**: {analysis.get('competition_grade', '')}
- **km당 밀도**: {analysis.get('density_per_km2', 0)}개/km²
"""

            md += f"""
---

## 4. 폐업 리스크

- **폐업률**: {closure.get('closure_rate_pct', 0)}%
- **위험 등급**: {closure.get('risk_grade', '')}
- **영업 중**: {closure.get('active', 0)}개
- **폐업**: {closure.get('closed', 0)}개
- **휴업**: {closure.get('suspended', 0)}개
- **시 평균 폐업률**: {closure.get('city_average_closure_pct', 0)}%
"""

            md += f"""
---

## 5. 창업 적합도

- **종합 점수**: {startup:.0f}/100
- **등급**: {startup_grade}
- 경쟁밀도 점수: {comp_score:.0f}/100
- 카테고리 포화 점수: {sat_score:.0f}/100
- 폐업 리스크 점수: {cl_score:.0f}/100
"""

            if nearby:
                md += """
---

## 6. 주변 동종 업체

| 이름 | 거리 | 주소 |
|------|------|------|
"""
                for s in nearby[:10]:
                    md += f"| {s['name']} | {s['distance_m']}m | {s['address']} |\n"

            md += f"""
---

*Luxon Sangkwon MCP | 소상공인시장진흥공단 상가정보 기반*
"""

            return success_response(
                data={
                    "markdown": md,
                    "summary": {
                        "location": resolved,
                        "category": cat_name,
                        "total_stores": analysis.get("total_stores", 0),
                        "competition_score": analysis.get("competition_score", 0),
                        "closure_rate_pct": closure.get("closure_rate_pct", 0),
                        "startup_score": round(startup, 1),
                    },
                },
                source="Luxon AI Sangkwon Report",
            )
