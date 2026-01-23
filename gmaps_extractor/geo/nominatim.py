"""
Nominatim API Integration

Fetches area boundaries from OpenStreetMap Nominatim API.
"""

import httpx
import time
from typing import Tuple, List, Dict, Optional
from dataclasses import dataclass

from .grid import AreaBoundary
from ..config import get_proxy_url


@dataclass
class SubArea:
    """Represents a sub-area with its name and boundary."""
    name: str
    full_name: str  # e.g., "Midtown, Manhattan, New York"
    boundary: AreaBoundary
    osm_id: Optional[str] = None
    area_type: Optional[str] = None  # e.g., "borough", "neighbourhood"


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


def get_sub_areas(
    area_name: str,
    parent_boundary: AreaBoundary = None,
    area_types: List[str] = None,
    delay: float = 1.0,
    verbose: bool = False,
) -> List[SubArea]:
    """
    Get sub-areas of a given area from Nominatim.

    Args:
        area_name: Name of the parent area (e.g., "New York, USA")
        parent_boundary: Optional boundary to filter sub-areas within
        area_types: Types of sub-areas to search for (default: borough, suburb, neighbourhood)
        delay: Delay between API calls to respect rate limits
        verbose: Print progress

    Returns:
        List of SubArea objects
    """
    if area_types is None:
        # Default types to search for, in order of priority
        area_types = ["borough", "suburb", "neighbourhood", "quarter", "city_district"]

    url = "https://nominatim.openstreetmap.org/search"
    headers = {"User-Agent": "GoogleMapsExtractor/1.0"}
    proxy_url = get_proxy_url()

    # Minimum bounding box span to accept (0.05 degrees ≈ 5km)
    # POIs typically get a default ~0.04 degree box, so this filters them out
    MIN_SPAN = 0.05

    sub_areas = []
    seen_names = set()

    with httpx.Client(timeout=30.0, proxy=proxy_url) as client:
        for area_type in area_types:
            # Search for sub-areas of this type within the parent area
            # Try different query formats
            queries = [
                f"{area_type} in {area_name}",
                f"{area_name} {area_type}",
            ]

            for query in queries:
                params = {
                    "q": query,
                    "format": "json",
                    "limit": 50,
                    "addressdetails": 1,
                }

                # If we have a parent boundary, use viewbox to limit results
                if parent_boundary:
                    params["viewbox"] = f"{parent_boundary.west},{parent_boundary.north},{parent_boundary.east},{parent_boundary.south}"
                    params["bounded"] = 1

                try:
                    response = client.get(url, params=params, headers=headers)
                    response.raise_for_status()
                    data = response.json()

                    for result in data:
                        name = result.get("name", "")
                        display_name = result.get("display_name", "")
                        osm_type = result.get("type", "")
                        osm_class = result.get("class", "")
                        osm_id = result.get("osm_id", "")

                        # Only accept place/boundary classes (actual geographic areas)
                        valid_classes = ["place", "boundary", "landuse", "natural"]
                        if osm_class not in valid_classes:
                            continue

                        # Skip if we've already seen this area
                        if name.lower() in seen_names or not name:
                            continue

                        # Get bounding box
                        bbox = result.get("boundingbox")
                        if not bbox:
                            continue

                        south = float(bbox[0])
                        north = float(bbox[1])
                        west = float(bbox[2])
                        east = float(bbox[3])

                        # Skip small results (POIs get a default ~0.04 degree box)
                        # Require at least 0.05 degrees (~5km) to be a real area
                        MIN_SPAN = 0.05
                        if (north - south) < MIN_SPAN or (east - west) < MIN_SPAN:
                            continue

                        # If parent boundary provided, check if this sub-area is within it
                        if parent_boundary:
                            center_lat = (north + south) / 2
                            center_lng = (east + west) / 2
                            if not (parent_boundary.south <= center_lat <= parent_boundary.north and
                                    parent_boundary.west <= center_lng <= parent_boundary.east):
                                continue

                        boundary = AreaBoundary(
                            name=name,
                            north=north,
                            south=south,
                            east=east,
                            west=west,
                        )

                        sub_area = SubArea(
                            name=name,
                            full_name=display_name,
                            boundary=boundary,
                            osm_id=str(osm_id),
                            area_type=osm_type or area_type,
                        )

                        sub_areas.append(sub_area)
                        seen_names.add(name.lower())

                        if verbose:
                            print(f"    Found: {name} ({osm_type})")

                except Exception as e:
                    if verbose:
                        print(f"    Error searching '{query}': {e}")

                time.sleep(delay)  # Respect rate limits

        # If no sub-areas found with type searches, try known sub-area names for major cities
        if not sub_areas:
            known_sub_areas = {
                "new york": ["Manhattan, New York", "Brooklyn, New York", "Queens, New York",
                             "The Bronx, New York", "Staten Island, New York"],
                "london": ["Westminster, London", "Camden, London", "Hackney, London",
                          "Tower Hamlets, London", "Islington, London", "Southwark, London"],
                "paris": ["1er arrondissement, Paris", "Le Marais, Paris", "Montmartre, Paris",
                         "Saint-Germain-des-Prés, Paris", "Belleville, Paris"],
                "los angeles": ["Downtown Los Angeles", "Hollywood, Los Angeles", "Santa Monica",
                               "Venice, Los Angeles", "Beverly Hills"],
            }

            area_lower = area_name.lower()
            for key, names in known_sub_areas.items():
                if key in area_lower:
                    if verbose:
                        print(f"    Using known sub-areas for {key}...")

                    for sub_name in names:
                        params = {
                            "q": sub_name,
                            "format": "json",
                            "limit": 1,
                        }

                        try:
                            response = client.get(url, params=params, headers=headers)
                            response.raise_for_status()
                            data = response.json()

                            if data:
                                result = data[0]
                                bbox = result.get("boundingbox")
                                if bbox:
                                    south = float(bbox[0])
                                    north = float(bbox[1])
                                    west = float(bbox[2])
                                    east = float(bbox[3])

                                    # Must have real area
                                    if (north - south) < MIN_SPAN or (east - west) < MIN_SPAN:
                                        continue

                                    name = result.get("name", sub_name.split(",")[0])

                                    boundary = AreaBoundary(
                                        name=name,
                                        north=north,
                                        south=south,
                                        east=east,
                                        west=west,
                                    )

                                    sub_area = SubArea(
                                        name=name,
                                        full_name=result.get("display_name", sub_name),
                                        boundary=boundary,
                                        osm_id=str(result.get("osm_id", "")),
                                        area_type=result.get("type", ""),
                                    )

                                    sub_areas.append(sub_area)
                                    if verbose:
                                        print(f"    Found: {name} ({result.get('type', '')})")

                        except Exception as e:
                            if verbose:
                                print(f"    Error searching '{sub_name}': {e}")

                        time.sleep(delay)
                    break

    return sub_areas


def get_subdivision_areas(
    area_name: str,
    verbose: bool = False,
) -> Tuple[AreaBoundary, List[SubArea]]:
    """
    Get an area's boundary and its sub-areas for subdivision search.

    This performs a two-level subdivision:
    1. Get sub-areas of the main area (e.g., boroughs of New York)
    2. Get sub-sub-areas of each sub-area (e.g., neighborhoods of Manhattan)

    Args:
        area_name: Name of the area (e.g., "New York, USA")
        verbose: Print progress

    Returns:
        Tuple of (main_boundary, list of all sub-areas for searching)
    """
    if verbose:
        print(f"\nGetting subdivision areas for '{area_name}'...")

    # Get main area boundary
    grid_boundary, filter_boundary = get_area_boundary(area_name)

    if verbose:
        print(f"  Main area: {grid_boundary.name}")
        print(f"  Boundary: N={grid_boundary.north:.4f}, S={grid_boundary.south:.4f}, "
              f"E={grid_boundary.east:.4f}, W={grid_boundary.west:.4f}")

    # Level 1: Get sub-areas of main area
    if verbose:
        print(f"\n  Level 1: Getting sub-areas of {grid_boundary.name}...")

    level1_areas = get_sub_areas(
        area_name,
        parent_boundary=grid_boundary,
        area_types=["borough", "city_district", "suburb"],
        verbose=verbose,
    )

    if verbose:
        print(f"  Found {len(level1_areas)} level-1 sub-areas")

    # Use level-1 areas directly (boroughs/districts have good boundaries)
    # Level-2 neighborhood search is unreliable with Nominatim
    all_search_areas = level1_areas

    if verbose and level1_areas:
        print(f"\n  Using {len(level1_areas)} sub-areas for search")
    else:
        # No sub-areas found at all, return empty list
        # Caller should fall back to grid approach
        if verbose:
            print(f"  No sub-areas found, will use grid approach")

    return filter_boundary, all_search_areas
