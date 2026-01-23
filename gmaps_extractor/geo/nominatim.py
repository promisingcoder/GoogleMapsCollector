"""
Nominatim API Integration

Fetches area boundaries from OpenStreetMap Nominatim API.
"""

import httpx
from typing import Tuple

from .grid import AreaBoundary
from ..config import get_proxy_url


def get_area_boundary(area_name: str, buffer_km: float = 5.0) -> Tuple[AreaBoundary, AreaBoundary]:
    """
    Fetch area boundaries from OpenStreetMap Nominatim API.

    Args:
        area_name: Name of the area to search (e.g., "New York, USA")
        buffer_km: Buffer in km to add around the area for filtering

    Returns:
        Tuple of (grid_boundary, filter_boundary):
        - grid_boundary: Exact area boundary for grid generation
        - filter_boundary: Expanded boundary with buffer for result filtering
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": area_name,
        "format": "json",
        "limit": 1,
    }
    headers = {"User-Agent": "GoogleMapsExtractor/1.0"}

    proxy_url = get_proxy_url()

    with httpx.Client(
        timeout=30.0,
        proxy=proxy_url,
    ) as client:
        response = client.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()

    if not data:
        raise ValueError(f"No results found for: {area_name}")

    result = data[0]
    bbox = result["boundingbox"]  # [south, north, west, east]

    south = float(bbox[0])
    north = float(bbox[1])
    west = float(bbox[2])
    east = float(bbox[3])

    # Grid boundary (exact area)
    # Use the input area_name to avoid encoding issues with non-ASCII names
    grid_boundary = AreaBoundary(
        name=area_name.split(",")[0],
        north=north,
        south=south,
        east=east,
        west=west,
    )

    # Calculate buffer in degrees (~111km per degree latitude)
    buffer_deg = buffer_km / 111.0

    # Filter boundary (with buffer)
    filter_boundary = AreaBoundary(
        name=f"{grid_boundary.name} Region",
        north=north + buffer_deg,
        south=south - buffer_deg,
        east=east + buffer_deg,
        west=west - buffer_deg,
    )

    return grid_boundary, filter_boundary
