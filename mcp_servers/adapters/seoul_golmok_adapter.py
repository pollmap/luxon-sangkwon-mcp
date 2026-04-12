"""
Seoul 골목상권 API Adapter.

서울 열린데이터광장 골목상권 데이터:
  - OA-15572: 추정매출 (estimated sales)
  - OA-15568: 유동인구 (foot traffic)

Docs: https://data.seoul.go.kr
"""
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

SEOUL_API_BASE = "http://openapi.seoul.go.kr:8088"


class SeoulGolmokAdapter:
    """Seoul 골목상권 Open API adapter."""

    def __init__(self, api_key: str = None, cache=None, limiter=None):
        self.api_key = api_key or os.getenv("SEOUL_DATA_API_KEY", "")
        self._cache = cache or get_cache()
        self._limiter = limiter or get_limiter()
        self.is_available = bool(self.api_key)

        if not self.is_available:
            logger.info("SeoulGolmokAdapter: SEOUL_DATA_API_KEY not set (optional)")

    def _request(self, service: str, start: int = 1, end: int = 5, params: str = "") -> dict:
        """Make rate-limited request to Seoul Open API."""
        self._limiter.acquire("seoul_data", wait=True)
        url = f"{SEOUL_API_BASE}/{self.api_key}/json/{service}/{start}/{end}/{params}"
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            # Seoul API wraps results in service name key
            return data.get(service, data)
        except requests.RequestException as e:
            logger.error(f"Seoul API error: {e}")
            return None

    def get_estimated_sales(
        self,
        trdar_cd: str = None,
        quarter: str = None,
        category_l: str = None,
    ) -> dict:
        """
        Get estimated sales data for a commercial district.

        Args:
            trdar_cd: 상권코드 (optional, for specific district)
            quarter: 분기 코드 e.g. "20244" (2024년 4분기)
            category_l: 서비스업종코드 대분류

        Returns:
            {"monthly_sales_avg": int, "weekday_sales": int, "weekend_sales": int, ...}
            or None if unavailable
        """
        if not self.is_available:
            return None

        cache_key = {"method": "sales", "trdar_cd": trdar_cd, "quarter": quarter}
        cached = self._cache.get("seoul", cache_key)
        if cached:
            return cached

        # Build filter params
        params_parts = []
        if quarter:
            params_parts.append(quarter)
        if trdar_cd:
            params_parts.append(trdar_cd)
        params_str = "/".join(params_parts) if params_parts else ""

        data = self._request("VwsmTrdarSelng", 1, 5, params_str)
        if not data or "row" not in data:
            return None

        rows = data["row"]
        if not rows:
            return None

        # Aggregate first matching row
        row = rows[0]
        result = {
            "quarter": row.get("STDR_YR_CD", "") + "Q" + row.get("STDR_QU_CD", ""),
            "district_name": row.get("TRDAR_CD_NM", ""),
            "monthly_sales_avg": int(float(row.get("THSMON_SELNG_AMT", 0))),
            "monthly_sales_count": int(float(row.get("THSMON_SELNG_CO", 0))),
            "store_count": int(float(row.get("STOR_CO", 0))),
            "source": "서울 열린데이터 골목상권 추정매출",
        }

        self._cache.set("seoul", cache_key, result, "daily_data")
        return result

    def get_foot_traffic(
        self,
        trdar_cd: str = None,
        quarter: str = None,
    ) -> dict:
        """
        Get foot traffic data for a commercial district.

        Returns:
            {"total_foot_traffic": int, "weekday_avg": int, "weekend_avg": int, ...}
            or None if unavailable
        """
        if not self.is_available:
            return None

        cache_key = {"method": "traffic", "trdar_cd": trdar_cd, "quarter": quarter}
        cached = self._cache.get("seoul", cache_key)
        if cached:
            return cached

        params_parts = []
        if quarter:
            params_parts.append(quarter)
        if trdar_cd:
            params_parts.append(trdar_cd)
        params_str = "/".join(params_parts) if params_parts else ""

        data = self._request("VwsmTrdarFlpop", 1, 5, params_str)
        if not data or "row" not in data:
            return None

        rows = data["row"]
        if not rows:
            return None

        row = rows[0]
        result = {
            "quarter": row.get("STDR_YR_CD", "") + "Q" + row.get("STDR_QU_CD", ""),
            "district_name": row.get("TRDAR_CD_NM", ""),
            "total_foot_traffic": int(float(row.get("TOT_FLPOP_CO", 0))),
            "male_traffic": int(float(row.get("ML_FLPOP_CO", 0))),
            "female_traffic": int(float(row.get("FML_FLPOP_CO", 0))),
            "source": "서울 열린데이터 골목상권 유동인구",
        }

        self._cache.set("seoul", cache_key, result, "daily_data")
        return result

    def get_foot_traffic_score(self, trdar_cd: str = None, quarter: str = None) -> float:
        """
        Get normalized foot traffic score (0-100).
        Higher traffic = higher score.
        """
        data = self.get_foot_traffic(trdar_cd, quarter)
        if not data:
            return None

        total = data.get("total_foot_traffic", 0)
        # Normalize: 0 traffic = 0, 1M+ = 100 (rough Seoul scale)
        from utils.scoring import normalize_score
        return normalize_score(total, 0, 1_000_000)
