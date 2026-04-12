"""
Kakao Local API Adapter.

Provides geocoding, reverse geocoding, and POI search via Kakao REST API.
Docs: https://developers.kakao.com/docs/latest/ko/local/dev-guide
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

KAKAO_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
KAKAO_ADDRESS_URL = "https://dapi.kakao.com/v2/local/search/address.json"
KAKAO_COORD2ADDR_URL = "https://dapi.kakao.com/v2/local/geo/coord2address.json"
KAKAO_COORD2REGION_URL = "https://dapi.kakao.com/v2/local/geo/coord2regioncode.json"


class KakaoGeocodeAdapter:
    """Kakao Local API adapter for geocoding and POI search."""

    def __init__(self, api_key: str = None, cache=None, limiter=None):
        self.api_key = api_key or os.getenv("KAKAO_REST_API_KEY", "")
        self._cache = cache or get_cache()
        self._limiter = limiter or get_limiter()
        self.is_available = bool(self.api_key)

        if not self.is_available:
            logger.warning("KakaoGeocodeAdapter: KAKAO_REST_API_KEY not set")

    def _headers(self) -> dict:
        return {"Authorization": f"KakaoAK {self.api_key}"}

    def _request(self, url: str, params: dict) -> dict:
        """Make a rate-limited request to Kakao API."""
        self._limiter.acquire("kakao", wait=True)
        try:
            resp = requests.get(url, headers=self._headers(), params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"Kakao API error: {e}")
            return None

    def geocode(self, query: str) -> dict:
        """
        Convert address/keyword to coordinates.

        Args:
            query: 지역명 또는 주소 (e.g., "강남역", "서울 강남구 역삼동")

        Returns:
            {"lat": float, "lng": float, "address": str, "place_name": str}
            or None
        """
        if not self.is_available:
            return None

        cache_key = {"method": "geocode", "query": query}
        cached = self._cache.get("kakao", cache_key)
        if cached:
            return cached

        # Try keyword search first (handles place names like "강남역")
        data = self._request(KAKAO_KEYWORD_URL, {"query": query, "size": 1})
        if data and data.get("documents"):
            doc = data["documents"][0]
            try:
                result = {
                    "lat": float(doc["y"]),
                    "lng": float(doc["x"]),
                    "address": doc.get("road_address_name") or doc.get("address_name", ""),
                    "place_name": doc.get("place_name", ""),
                }
                self._cache.set("kakao", cache_key, result, "static_meta")
                return result
            except (ValueError, KeyError) as e:
                logger.warning(f"Kakao geocode parse error: {e}")

        # Fallback: address search
        data = self._request(KAKAO_ADDRESS_URL, {"query": query, "size": 1})
        if data and data.get("documents"):
            doc = data["documents"][0]
            try:
                result = {
                    "lat": float(doc["y"]),
                    "lng": float(doc["x"]),
                    "address": doc.get("address_name", ""),
                    "place_name": "",
                }
                self._cache.set("kakao", cache_key, result, "static_meta")
                return result
            except (ValueError, KeyError) as e:
                logger.warning(f"Kakao address parse error: {e}")

        return None

    def reverse_geocode(self, lat: float, lng: float) -> dict:
        """
        Convert coordinates to address.

        Returns:
            {"address": str, "road_address": str, "region": str, "dong": str}
            or None
        """
        if not self.is_available:
            return None

        cache_key = {"method": "reverse_geocode", "lat": round(lat, 5), "lng": round(lng, 5)}
        cached = self._cache.get("kakao", cache_key)
        if cached:
            return cached

        data = self._request(KAKAO_COORD2ADDR_URL, {"x": lng, "y": lat})
        region_data = self._request(KAKAO_COORD2REGION_URL, {"x": lng, "y": lat})

        result = {"address": "", "road_address": "", "region": "", "dong": ""}

        if data and data.get("documents"):
            doc = data["documents"][0]
            addr = doc.get("address") or {}
            road = doc.get("road_address") or {}
            result["address"] = addr.get("address_name", "")
            result["road_address"] = road.get("address_name", "")

        if region_data and region_data.get("documents"):
            for doc in region_data["documents"]:
                if doc.get("region_type") == "H":  # 행정동
                    result["region"] = doc.get("address_name", "")
                    result["dong"] = doc.get("region_3depth_name", "")

        if result["address"] or result["region"]:
            self._cache.set("kakao", cache_key, result, "static_meta")
            return result

        return None

    def search_poi(
        self,
        query: str,
        lat: float = None,
        lng: float = None,
        radius: int = None,
        size: int = 15,
        category_group_code: str = None,
    ) -> list:
        """
        Search for places of interest.

        Args:
            query: 검색 키워드
            lat, lng: 중심 좌표 (옵션)
            radius: 반경 미터 (옵션, 최대 20000)
            size: 결과 수 (최대 15)
            category_group_code: 카카오 카테고리 그룹 코드

        Returns:
            List of {"name": str, "address": str, "lat": float, "lng": float, "category": str, "phone": str, "url": str}
        """
        if not self.is_available:
            return []

        params = {"query": query, "size": min(size, 15)}
        if lat and lng:
            params["y"] = lat
            params["x"] = lng
            params["sort"] = "distance"
        if radius:
            params["radius"] = min(radius, 20000)
        if category_group_code:
            params["category_group_code"] = category_group_code

        cache_key = {"method": "search_poi", **params}
        cached = self._cache.get("kakao", cache_key)
        if cached:
            return cached

        data = self._request(KAKAO_KEYWORD_URL, params)
        if not data or not data.get("documents"):
            return []

        results = []
        for doc in data["documents"]:
            results.append({
                "name": doc.get("place_name", ""),
                "address": doc.get("road_address_name") or doc.get("address_name", ""),
                "lat": float(doc["y"]),
                "lng": float(doc["x"]),
                "category": doc.get("category_name", ""),
                "phone": doc.get("phone", ""),
                "url": doc.get("place_url", ""),
                "distance": int(doc["distance"]) if doc.get("distance") else None,
            })

        self._cache.set("kakao", cache_key, results, "daily_data")
        return results
