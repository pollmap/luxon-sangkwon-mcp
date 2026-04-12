"""
Sangkwon DB Adapter — SQLite + R-tree 기반 상권 분석 엔진.

Core analytical engine for commercial district analysis.
"""
import logging
import math
import os
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from mcp_servers.core.cache_manager import get_cache
from mcp_servers.core.rate_limiter import get_limiter
from utils.geo_utils import haversine, bounding_box, grid_cells
from utils.category_codes import resolve_category, get_category_weight, CATEGORY_L

logger = logging.getLogger(__name__)


class SangkwonDBAdapter:
    """SQLite + R-tree based commercial district analyzer."""

    def __init__(self, db_path: str = None, cache=None, limiter=None):
        self.db_path = db_path or os.getenv(
            "SANGKWON_DB_PATH",
            str(PROJECT_ROOT / "data" / "sangkwon.db"),
        )
        self._cache = cache or get_cache()
        self._limiter = limiter or get_limiter()

        self._has_rtree = False
        self.is_available = self._validate_db()

        if self.is_available:
            self._check_rtree()

    def _validate_db(self) -> bool:
        """Check if DB file exists and is a valid SQLite database."""
        db_file = Path(self.db_path)
        if not db_file.exists():
            return False
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("SELECT 1 FROM stores LIMIT 1")
            conn.close()
            return True
        except Exception as e:
            logger.warning(f"DB validation failed: {e}")
            return False

    def _get_conn(self) -> sqlite3.Connection:
        """Get a new SQLite connection with WAL mode."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA cache_size=-50000;")  # 50MB
        return conn

    def _check_rtree(self):
        """Check if R-tree is available."""
        try:
            conn = self._get_conn()
            # Check if rtree table exists
            cur = conn.execute("SELECT COUNT(*) FROM store_rtree LIMIT 1")
            cur.fetchone()
            self._has_rtree = True
            conn.close()
        except Exception:
            self._has_rtree = False
            logger.warning("R-tree not available, using fallback spatial query")

    def query_radius(
        self,
        lat: float,
        lng: float,
        radius_m: float,
        category_m: str = None,
        limit: int = 5000,
    ) -> List[Dict]:
        """
        Query stores within a radius using R-tree + haversine.

        Returns list of store dicts with 'distance_m' field added.
        """
        if not self.is_available:
            return []

        south, west, north, east = bounding_box(lat, lng, radius_m)

        conn = self._get_conn()
        try:
            if self._has_rtree:
                sql = """
                    SELECT s.* FROM stores s
                    INNER JOIN store_rtree r ON s.id = r.id
                    WHERE r.min_lat >= ? AND r.max_lat <= ?
                      AND r.min_lng >= ? AND r.max_lng <= ?
                """
                params = [south, north, west, east]
            else:
                sql = """
                    SELECT * FROM stores
                    WHERE lat BETWEEN ? AND ?
                      AND lng BETWEEN ? AND ?
                """
                params = [south, north, west, east]

            if category_m:
                sql += " AND s.category_m = ?" if self._has_rtree else " AND category_m = ?"
                params.append(category_m)

            # Sanitize limit (prevent injection)
            limit = max(1, min(int(limit), 10000))
            sql += f" LIMIT {limit}"

            cur = conn.execute(sql, params)
            rows = cur.fetchall()

            # Post-filter with exact haversine distance
            results = []
            for row in rows:
                row_dict = dict(row)
                dist = haversine(lat, lng, row_dict["lat"], row_dict["lng"])
                if dist <= radius_m:
                    row_dict["distance_m"] = round(dist, 1)
                    results.append(row_dict)

            results.sort(key=lambda x: x["distance_m"])
            return results
        finally:
            conn.close()

    def analyze(
        self,
        lat: float,
        lng: float,
        radius_m: float = 500,
        category_m: str = None,
    ) -> Dict:
        """
        Comprehensive commercial district analysis.

        Returns:
            {
                "center": {"lat", "lng"},
                "radius_m": int,
                "total_stores": int,
                "filtered_stores": int,
                "category_filter": str or None,
                "category_distribution": [{"name", "count", "pct"}],
                "competition_score": float (0-100),
                "competition_grade": str,
                "density_per_km2": float,
                "top_subcategories": [{"code", "name", "count"}],
                "data_date": str,
                "source": str,
            }
        """
        if not self.is_available:
            return {"error": True, "message": "Database not available"}

        cache_key = {
            "method": "analyze",
            "lat": round(lat, 4),
            "lng": round(lng, 4),
            "radius_m": radius_m,
            "category_m": category_m,
        }
        cached = self._cache.get("sangkwon", cache_key)
        if cached:
            return cached

        # Get all stores in radius
        all_stores = self.query_radius(lat, lng, radius_m)
        total = len(all_stores)

        # Get filtered stores if category specified
        if category_m:
            filtered = [s for s in all_stores if s.get("category_m") == category_m]
        else:
            filtered = all_stores
        filtered_count = len(filtered)

        # Category distribution (from all stores)
        cat_counter = Counter()
        for s in all_stores:
            cat_name = s.get("category_m_name") or s.get("category_m") or "기타"
            cat_counter[cat_name] += 1

        cat_dist = []
        for name, count in cat_counter.most_common():
            cat_dist.append({
                "name": name,
                "count": count,
                "pct": round(count / total * 100, 1) if total > 0 else 0,
            })

        # Competition score
        area_km2 = math.pi * (radius_m / 1000) ** 2
        if category_m and area_km2 > 0:
            weight = get_category_weight(category_m)
            density = filtered_count / area_km2
            score = min(100, round(density * weight * 10))
        elif total > 0 and area_km2 > 0:
            density = total / area_km2
            score = min(100, round(density * 0.5))
        else:
            density = 0
            score = 0

        grade = _score_to_grade(score)

        # Top subcategories (소분류) within the filtered set
        sub_counter = Counter()
        for s in filtered:
            sub_name = s.get("category_s_name") or s.get("category_m_name") or "기타"
            sub_counter[sub_name] += 1

        top_subs = [
            {"name": name, "count": count}
            for name, count in sub_counter.most_common(10)
        ]

        # Data date from metadata
        data_date = self._get_meta("build_date") or "unknown"

        result = {
            "center": {"lat": round(lat, 6), "lng": round(lng, 6)},
            "radius_m": radius_m,
            "total_stores": total,
            "filtered_stores": filtered_count,
            "category_filter": category_m,
            "category_distribution": cat_dist[:15],  # Top 15
            "competition_score": score,
            "competition_grade": grade,
            "density_per_km2": round(density, 1) if area_km2 > 0 else 0,
            "top_subcategories": top_subs,
            "data_date": data_date,
            "source": "소상공인시장진흥공단 상가정보",
        }

        self._cache.set("sangkwon", cache_key, result, "daily_data")
        return result

    def compare(
        self,
        locations: List[Tuple[float, float]],
        radius_m: float = 500,
        category_m: str = None,
    ) -> Dict:
        """
        Compare multiple locations side by side.

        Args:
            locations: List of (lat, lng) tuples
            radius_m: Analysis radius
            category_m: Category filter

        Returns:
            {"locations": [analysis_dict, ...], "winner": {...}}
        """
        analyses = []
        for lat, lng in locations:
            result = self.analyze(lat, lng, radius_m, category_m)
            analyses.append(result)

        # Determine winner (lowest competition = best for new business)
        winner_idx = 0
        min_score = 999
        for i, a in enumerate(analyses):
            score = a.get("competition_score", 100)
            if score < min_score:
                min_score = score
                winner_idx = i

        return {
            "locations": analyses,
            "best_for_entry": {
                "index": winner_idx,
                "center": analyses[winner_idx]["center"] if analyses else None,
                "competition_score": min_score,
                "reason": "가장 낮은 경쟁 강도",
            },
            "category_filter": category_m,
            "radius_m": radius_m,
        }

    def nearby_similar(
        self,
        lat: float,
        lng: float,
        category_m: str,
        radius_m: float = 500,
        limit: int = 50,
    ) -> List[Dict]:
        """
        Find similar stores nearby, sorted by distance.

        Returns list of store dicts with distance_m.
        """
        stores = self.query_radius(lat, lng, radius_m, category_m=category_m, limit=limit)
        return [
            {
                "name": s.get("name", ""),
                "category": s.get("category_m_name", ""),
                "subcategory": s.get("category_s_name", ""),
                "address": s.get("road_address") or s.get("old_address", ""),
                "lat": s["lat"],
                "lng": s["lng"],
                "distance_m": s["distance_m"],
                "floor": s.get("floor_info", ""),
            }
            for s in stores
        ]

    def density_grid(
        self,
        lat: float,
        lng: float,
        radius_m: float = 1000,
        category_m: str = None,
        cell_size_m: float = 100,
    ) -> Dict:
        """
        Compute store density on a grid.

        Returns grid cells with store counts.
        """
        cells = grid_cells(lat, lng, radius_m, cell_size_m)

        # Get all stores in the area once
        all_stores = self.query_radius(lat, lng, radius_m, category_m=category_m)

        # For each cell, count stores within cell_size_m/2
        cell_radius = cell_size_m / 2
        for cell in cells:
            count = 0
            for s in all_stores:
                dist = haversine(cell["lat"], cell["lng"], s["lat"], s["lng"])
                if dist <= cell_radius:
                    count += 1
            cell["store_count"] = count

        max_count = max((c["store_count"] for c in cells), default=0)

        return {
            "center": {"lat": round(lat, 6), "lng": round(lng, 6)},
            "radius_m": radius_m,
            "cell_size_m": cell_size_m,
            "total_cells": len(cells),
            "total_stores": len(all_stores),
            "max_density": max_count,
            "cells": cells,
            "category_filter": category_m,
        }

    def get_stats(self) -> Dict:
        """Get database statistics."""
        if not self.is_available:
            return {
                "available": False,
                "db_path": self.db_path,
                "message": "Database file not found",
            }

        conn = self._get_conn()
        try:
            total = conn.execute("SELECT COUNT(*) FROM stores").fetchone()[0]
            categories = conn.execute("SELECT COUNT(DISTINCT category_m) FROM stores").fetchone()[0]
            sidos = conn.execute("SELECT COUNT(DISTINCT sido) FROM stores").fetchone()[0]

            # Top categories
            top = conn.execute("""
                SELECT category_m_name, COUNT(*) as cnt
                FROM stores
                GROUP BY category_m_name
                ORDER BY cnt DESC
                LIMIT 5
            """).fetchall()

            db_size_mb = Path(self.db_path).stat().st_size / 1_000_000

            return {
                "available": True,
                "db_path": self.db_path,
                "total_stores": total,
                "total_categories": categories,
                "total_sidos": sidos,
                "has_rtree": self._has_rtree,
                "db_size_mb": round(db_size_mb, 1),
                "build_date": self._get_meta("build_date"),
                "source": self._get_meta("source"),
                "top_categories": [{"name": r[0], "count": r[1]} for r in top],
            }
        finally:
            conn.close()

    def _get_meta(self, key: str) -> Optional[str]:
        """Get metadata value from DB."""
        try:
            conn = self._get_conn()
            cur = conn.execute("SELECT value FROM metadata WHERE key = ?", (key,))
            row = cur.fetchone()
            conn.close()
            return row[0] if row else None
        except Exception:
            return None


def _score_to_grade(score: int) -> str:
    """Convert competition score to Korean grade."""
    if score <= 20:
        return "거의 없음"
    elif score <= 40:
        return "낮음"
    elif score <= 60:
        return "보통"
    elif score <= 80:
        return "높음"
    else:
        return "과포화"
