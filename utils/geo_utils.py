"""
Geospatial utility functions.

Pure Python, no external dependencies.
"""
import math
from typing import Tuple, List, Dict

# Earth radius in meters
EARTH_RADIUS_M = 6_371_000


def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance between two points in meters using Haversine formula."""
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlng / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_M * c


def bounding_box(lat: float, lng: float, radius_m: float) -> Tuple[float, float, float, float]:
    """
    Compute bounding box for R-tree pre-filtering.

    Returns: (south, west, north, east) as (min_lat, min_lng, max_lat, max_lng)
    """
    # Angular distance in radians
    angular = radius_m / EARTH_RADIUS_M

    lat_r = math.radians(lat)
    dlat = math.degrees(angular)
    # Longitude spread widens at lower latitudes
    dlng = math.degrees(angular / math.cos(lat_r)) if math.cos(lat_r) > 1e-10 else 180.0

    return (lat - dlat, lng - dlng, lat + dlat, lng + dlng)


def grid_cells(
    lat: float,
    lng: float,
    radius_m: float,
    cell_size_m: float = 100,
) -> List[Dict]:
    """
    Generate grid cells within a circular area for density mapping.

    Returns list of {"lat": float, "lng": float, "row": int, "col": int}
    """
    cells = []
    # Number of cells in each direction from center
    n = int(radius_m / cell_size_m)

    lat_r = math.radians(lat)
    # Meters per degree
    lat_deg_per_m = 1.0 / (EARTH_RADIUS_M * math.pi / 180)
    lng_deg_per_m = lat_deg_per_m / math.cos(lat_r) if math.cos(lat_r) > 1e-10 else lat_deg_per_m

    for row in range(-n, n + 1):
        for col in range(-n, n + 1):
            cell_lat = lat + row * cell_size_m * lat_deg_per_m
            cell_lng = lng + col * cell_size_m * lng_deg_per_m

            # Only include cells within the circle
            dist = haversine(lat, lng, cell_lat, cell_lng)
            if dist <= radius_m:
                cells.append({
                    "lat": round(cell_lat, 6),
                    "lng": round(cell_lng, 6),
                    "row": row,
                    "col": col,
                })

    return cells
