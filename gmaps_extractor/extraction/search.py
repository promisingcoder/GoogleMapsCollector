"""
Search Execution

Executes search queries via the local API server.
"""

import httpx
from typing import List, Dict
from urllib.parse import quote

from ..config import (
    API_BASE_URL,
    SEARCH_CURL_TEMPLATE,
    DEFAULT_RESULTS_PER_PAGE,
    DEFAULT_MAX_RADIUS,
    DEFAULT_VIEWPORT_DIST,
)


def build_search_curl(
    search_query: str,
    lat: float,
    lng: float,
    results_count: int = DEFAULT_RESULTS_PER_PAGE,
    max_radius: int = DEFAULT_MAX_RADIUS,
    viewport_dist: float = DEFAULT_VIEWPORT_DIST,
    offset: int = 0,
) -> str:
    """
    Build a curl command for Google Maps search.

    Args:
        search_query: What to search for (e.g., "lawyers")
        lat: Center latitude
        lng: Center longitude
        results_count: Number of results per page
        max_radius: Maximum search radius in meters
        viewport_dist: Viewport distance in meters
        offset: Pagination offset

    Returns:
        Curl command string
    """
    query_encoded = quote(search_query)
    query_url = quote(search_query).replace('%20', '+')

    curl = SEARCH_CURL_TEMPLATE.format(
        query=query_url,
        query_encoded=query_encoded,
        lat=lat,
        lng=lng,
        viewport_dist=viewport_dist,
        results_count=results_count,
        max_radius=max_radius,
        offset=offset,
    )
    return curl


def execute_search(
    search_query: str,
    lat: float,
    lng: float,
    results_count: int = DEFAULT_RESULTS_PER_PAGE,
    max_radius: int = DEFAULT_MAX_RADIUS,
    viewport_dist: float = DEFAULT_VIEWPORT_DIST,
    offset: int = 0,
    timeout: float = 60.0,
) -> List[Dict]:
    """
    Execute a search query via the API server.

    Args:
        search_query: What to search for
        lat: Center latitude
        lng: Center longitude
        results_count: Number of results per page
        max_radius: Maximum search radius in meters
        viewport_dist: Viewport distance in meters
        offset: Pagination offset
        timeout: Request timeout in seconds

    Returns:
        List of business dictionaries

    Raises:
        Exception: If the API returns an error
    """
    curl_command = build_search_curl(
        search_query, lat, lng, results_count, max_radius, viewport_dist, offset
    )

    payload = {
        'original_curl': curl_command,
        'url_params': {},
        'pb_params': [],
        'headers': {},
    }

    with httpx.Client(timeout=timeout) as client:
        response = client.post(f"{API_BASE_URL}/api/execute", json=payload)

        if response.status_code != 200:
            raise Exception(f"API error: {response.status_code} - {response.text[:200]}")

        data = response.json()

        if not data.get('success'):
            raise Exception(f"API returned error: {data}")

        return data.get('response', {}).get('businesses', [])
