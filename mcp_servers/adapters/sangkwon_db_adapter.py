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


    def closure_stats(
        self,
        lat: float,
        lng: float,
        radius_m: float = 500,
        category_m: str = None,
    ) -> Dict:
        """
        Get business status breakdown (영업/폐업/휴업) within radius.

        Returns:
            {
                "total": int,
                "active": int, "closed": int, "suspended": int,
                "closure_rate_pct": float,
                "risk_grade": str,
                "by_status": [{"status", "count", "pct"}],
                "city_average_closure_pct": float,
            }
        """
        if not self.is_available:
            return {"error": True, "message": "DB not available"}

        south, west, north, east = bounding_box(lat, lng, radius_m)

        conn = self._get_conn()
        try:
            if self._has_rtree:
                sql = """
                    SELECT s.business_status_name, COUNT(*) as cnt
                    FROM stores s
                    INNER JOIN store_rtree r ON s.id = r.id
                    WHERE r.min_lat >= ? AND r.max_lat <= ?
                      AND r.min_lng >= ? AND r.max_lng <= ?
                """
                params = [south, north, west, east]
            else:
                sql = """
                    SELECT business_status_name, COUNT(*) as cnt
                    FROM stores
                    WHERE lat BETWEEN ? AND ? AND lng BETWEEN ? AND ?
                """
                params = [south, north, west, east]

            if category_m:
                sql += " AND s.category_m = ?" if self._has_rtree else " AND category_m = ?"
                params.append(category_m)
            sql += " GROUP BY business_status_name"

            rows = conn.execute(sql, params).fetchall()

            status_map = {}
            total = 0
            for row in rows:
                name = row[0] or "미분류"
                cnt = row[1]
                status_map[name] = cnt
                total += cnt

            active = status_map.get("영업/정상", 0)
            closed = status_map.get("폐업", 0)
            suspended = status_map.get("휴업", 0)

            denominator = active + closed
            closure_rate = round(closed / denominator * 100, 1) if denominator > 0 else 0

            # City average: get sido from nearest store
            city_avg = self._city_closure_average(conn, lat, lng, category_m)

            by_status = [
                {"status": name, "count": cnt, "pct": round(cnt / total * 100, 1) if total > 0 else 0}
                for name, cnt in sorted(status_map.items(), key=lambda x: -x[1])
            ]

            return {
                "total": total,
                "active": active,
                "closed": closed,
                "suspended": suspended,
                "closure_rate_pct": closure_rate,
                "risk_grade": _closure_grade(closure_rate),
                "by_status": by_status,
                "city_average_closure_pct": city_avg,
            }
        finally:
            conn.close()

    def _city_closure_average(self, conn, lat: float, lng: float, category_m: str = None) -> float:
        """Get closure rate average for the city (sido) this point belongs to."""
        try:
            # Find sido from nearest store
            sido_row = conn.execute("""
                SELECT sido FROM stores
                ORDER BY ABS(lat - ?) + ABS(lng - ?) LIMIT 1
            """, (lat, lng)).fetchone()
            if not sido_row:
                return 0
            sido = sido_row[0]

            sql = "SELECT business_status_name, COUNT(*) FROM stores WHERE sido = ?"
            params = [sido]
            if category_m:
                sql += " AND category_m = ?"
                params.append(category_m)
            sql += " GROUP BY business_status_name"

            rows = conn.execute(sql, params).fetchall()
            city_active = 0
            city_closed = 0
            for row in rows:
                if row[0] == "영업/정상":
                    city_active = row[1]
                elif row[0] == "폐업":
                    city_closed = row[1]

            denom = city_active + city_closed
            return round(city_closed / denom * 100, 1) if denom > 0 else 0
        except Exception:
            return 0

    def snapshot_compare(
        self,
        lat: float,
        lng: float,
        radius_m: float,
        category_m: str = None,
        quarter_current: str = None,
        quarter_previous: str = None,
    ) -> Dict:
        """Compare store counts between two quarters for trend analysis."""
        if not self.is_available:
            return {"error": True, "message": "DB not available"}

        conn = self._get_conn()
        try:
            # Get available quarters
            quarters = [r[0] for r in conn.execute(
                "SELECT DISTINCT quarter FROM store_snapshots ORDER BY quarter DESC"
            ).fetchall()]

            if not quarters:
                return {"available": False, "message": "스냅샷 데이터 없음", "quarters": []}

            if not quarter_current:
                quarter_current = quarters[0]
            if not quarter_previous and len(quarters) >= 2:
                quarter_previous = quarters[1]

            south, west, north, east = bounding_box(lat, lng, radius_m)

            def count_quarter(q):
                sql = """
                    SELECT COUNT(*) FROM store_snapshots
                    WHERE quarter = ? AND lat BETWEEN ? AND ? AND lng BETWEEN ? AND ?
                      AND business_status = '01'
                """
                params = [q, south, north, west, east]
                if category_m:
                    sql += " AND category_m = ?"
                    params.append(category_m)
                return conn.execute(sql, params).fetchone()[0]

            current_count = count_quarter(quarter_current)

            if quarter_previous:
                previous_count = count_quarter(quarter_previous)
                delta = current_count - previous_count
                growth_rate = round(delta / previous_count * 100, 1) if previous_count > 0 else 0
                if delta > 0:
                    trend = "증가"
                elif delta < 0:
                    trend = "감소"
                else:
                    trend = "유지"
            else:
                previous_count = None
                delta = None
                growth_rate = None
                trend = None

            return {
                "available": True,
                "quarter_current": quarter_current,
                "quarter_previous": quarter_previous,
                "current_count": current_count,
                "previous_count": previous_count,
                "delta": delta,
                "growth_rate_pct": growth_rate,
                "trend_direction": trend,
                "all_quarters": quarters,
                "message": "다음 분기 데이터 축적 후 트렌드 비교 가능" if not quarter_previous else None,
            }
        finally:
            conn.close()

    def area_aggregate(
        self,
        locations: List[Tuple[str, float, float]],
        category_m: str = None,
        radius_m: float = 500,
    ) -> List[Dict]:
        """Batch analysis for multiple locations (for hot_areas)."""
        results = []
        for name, lat, lng in locations:
            analysis = self.analyze(lat, lng, radius_m, category_m)
            closure = self.closure_stats(lat, lng, radius_m, category_m)
            results.append({
                "name": name,
                "lat": lat,
                "lng": lng,
                "total_stores": analysis.get("total_stores", 0),
                "filtered_stores": analysis.get("filtered_stores", 0),
                "competition_score": analysis.get("competition_score", 0),
                "competition_grade": analysis.get("competition_grade", ""),
                "closure_rate_pct": closure.get("closure_rate_pct", 0),
                "risk_grade": closure.get("risk_grade", ""),
            })
        return results


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


def _closure_grade(rate: float) -> str:
    """Convert closure rate to risk grade."""
    if rate < 10:
        return "안정"
    elif rate < 20:
        return "보통"
    elif rate < 30:
        return "주의"
    else:
        return "위험"
