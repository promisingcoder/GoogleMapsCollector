"""
Grid Generation

Generates grid cells covering a geographic area for systematic querying.
"""

import math
from dataclasses import dataclass
from typing import List

from ..config import (
    METERS_PER_LAT_DEGREE,
    CELL_SIZE_SMALL,
    CELL_SIZE_MEDIUM,
    CELL_SIZE_LARGE,
    CELL_SIZE_XLARGE,
    CELL_SIZE_XXLARGE,
)


@dataclass
class GridCell:
    """Represents a single grid cell for querying"""
    cell_id: int
    center_lat: float
    center_lng: float
    radius_meters: int


@dataclass
class AreaBoundary:
    """Represents the boundary of a geographic area"""
    name: str
    north: float
    south: float
    east: float
    west: float


def meters_to_lng_degrees(meters: float, latitude: float) -> float:
    """Convert meters to longitude degrees at a given latitude"""
    return meters / (METERS_PER_LAT_DEGREE * math.cos(math.radians(latitude)))


def meters_to_lat_degrees(meters: float) -> float:
    """Convert meters to latitude degrees"""
    return meters / METERS_PER_LAT_DEGREE


def calculate_cell_size(boundary: AreaBoundary) -> int:
    """
    Calculate appropriate cell size based on area dimensions.

    Args:
        boundary: The area boundary

    Returns:
        Cell size in meters
    """
    area_height_km = (boundary.north - boundary.south) * 111
    area_width_km = (boundary.east - boundary.west) * 111 * math.cos(math.radians(boundary.south))

    if area_height_km < 10 or area_width_km < 10:
        return CELL_SIZE_SMALL  # 1km for small areas (cities)
    elif area_height_km < 30 or area_width_km < 30:
        return CELL_SIZE_MEDIUM  # 2km for medium areas
    elif area_height_km < 100 or area_width_km < 100:
        return CELL_SIZE_LARGE  # 5km for large areas (regions)
    elif area_height_km < 500 or area_width_km < 500:
        return CELL_SIZE_XLARGE  # 50km for very large areas (states)
    else:
        return CELL_SIZE_XXLARGE  # 100km for countries


def generate_grid(boundary: AreaBoundary, cell_size_meters: int = None) -> List[GridCell]:
    """
    Generate a grid of cells covering the area.

    Args:
        boundary: The area boundary to cover
        cell_size_meters: Size of each cell in meters (auto-calculated if None)

    Returns:
        List of GridCell objects covering the area
    """
    if cell_size_meters is None:
        cell_size_meters = calculate_cell_size(boundary)

    lat_step = meters_to_lat_degrees(cell_size_meters)
    cells = []
    cell_id = 0

    current_lat = boundary.south + (lat_step / 2)

    while current_lat <= boundary.north:
        lng_step = meters_to_lng_degrees(cell_size_meters, current_lat)
        current_lng = boundary.west + (lng_step / 2)

        while current_lng <= boundary.east:
            cell = GridCell(
                cell_id=cell_id,
                center_lat=round(current_lat, 6),
                center_lng=round(current_lng, 6),
                radius_meters=cell_size_meters // 2,
            )
            cells.append(cell)
            cell_id += 1
            current_lng += lng_step

        current_lat += lat_step

    return cells


def is_in_boundary(lat: float, lng: float, boundary: AreaBoundary) -> bool:
    """
    Check if a point is within the boundary.

    Args:
        lat: Latitude
        lng: Longitude
        boundary: The boundary to check against

    Returns:
        True if the point is within the boundary
    """
    return (boundary.south <= lat <= boundary.north and
            boundary.west <= lng <= boundary.east)
