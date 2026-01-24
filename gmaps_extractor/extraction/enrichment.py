"""
Business Enrichment

Fetches additional details and reviews for businesses.
"""

import time
import httpx
from typing import Dict

from ..config import (
    API_BASE_URL,
    DELAY_BETWEEN_DETAILS,
    DELAY_BETWEEN_REVIEWS,
    get_google_cookies,
)


def fetch_place_details(
    place_id: str,
    name: str = None,
    latitude: float = None,
    longitude: float = None,
    hex_id: str = None,
    ftid: str = None,
    timeout: float = 30.0,
) -> Dict:
    """
    Fetch detailed information about a place from the API.

    Args:
        place_id: Google Maps place ID
        name: Business name (helps with lookup)
        latitude: Business latitude
        longitude: Business longitude
        hex_id: Hex format ID (0x...:0x...) for place endpoint
        ftid: Feature ID (like /g/11b5wlq0vc) for reviews
        timeout: Request timeout in seconds

    Returns:
        Dictionary with place details, or empty dict on error
    """
    payload = {'place_id': place_id}
    if name:
        payload['name'] = name
    if latitude is not None:
        payload['latitude'] = latitude
    if longitude is not None:
        payload['longitude'] = longitude
    if hex_id:
        payload['hex_id'] = hex_id
    if ftid:
        payload['ftid'] = ftid

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(f"{API_BASE_URL}/api/place-details", json=payload)

            if response.status_code != 200:
                return {}

            data = response.json()
            if data.get('success'):
                return data.get('details', {})
            return {}
    except Exception as e:
        return {}


def fetch_reviews(
    place_id: str,
    name: str = None,
    latitude: float = None,
    longitude: float = None,
    hex_id: str = None,
    ftid: str = None,
    limit: int = 10,
    timeout: float = 30.0,
    cookies: Dict = None,
    max_retries: int = 3,
    page_size: int = 10,
    page_delay: float = 0.5,
) -> Dict:
    """
    Fetch review info for a place from the API with pagination support.

    Args:
        place_id: Google Maps place ID
        name: Business name
        latitude: Business latitude
        longitude: Business longitude
        hex_id: Hex format ID (0x...:0x...) for place endpoint
        ftid: Feature ID (like /g/11b5wlq0vc) for reviews
        limit: Maximum total number of reviews to fetch (uses pagination if > page_size)
        timeout: Request timeout in seconds
        cookies: Google cookies (required for reviews endpoint)
        max_retries: Number of retry attempts on failure
        page_size: Reviews per page (max 10-20, default 10)
        page_delay: Delay between pagination requests in seconds

    Returns:
        Dictionary with review_count, rating, and reviews list
    """
    all_reviews = []
    pagination_token = None
    total_fetched = 0

    # Limit page_size to max 20 (Google's limit)
    page_size = min(page_size, 20)

    while total_fetched < limit:
        # Calculate how many to request this page
        remaining = limit - total_fetched
        request_size = min(page_size, remaining)

        payload = {
            'place_id': place_id,
            'sort_by': 'newest',
            'limit': request_size,
        }
        if name:
            payload['name'] = name
        if latitude is not None:
            payload['latitude'] = latitude
        if longitude is not None:
            payload['longitude'] = longitude
        if hex_id:
            payload['hex_id'] = hex_id
        if ftid:
            payload['ftid'] = ftid
        if cookies:
            payload['cookies'] = cookies
        if pagination_token:
            payload['pagination_token'] = pagination_token

        success = False
        for attempt in range(max_retries):
            try:
                with httpx.Client(timeout=timeout) as client:
                    response = client.post(f"{API_BASE_URL}/api/reviews", json=payload)

                    if response.status_code != 200:
                        if attempt < max_retries - 1:
                            time.sleep(1.0 * (attempt + 1))
                            continue
                        break

                    data = response.json()
                    if data.get('success'):
                        page_reviews = data.get('reviews', [])
                        all_reviews.extend(page_reviews)
                        total_fetched += len(page_reviews)

                        # Get next page token
                        pagination_token = data.get('next_page_token')
                        success = True
                        break

                    # API returned error - retry
                    if attempt < max_retries - 1:
                        time.sleep(1.0 * (attempt + 1))
                        continue
                    break

            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                break

        # Stop if request failed, no more pages, or got no reviews
        if not success or not pagination_token or total_fetched == 0:
            break

        # Check if we got fewer reviews than requested (means no more available)
        if len(data.get('reviews', [])) < request_size:
            break

        # Delay before next page
        if total_fetched < limit:
            time.sleep(page_delay)

    return {
        'review_count': len(all_reviews),
        'rating': None,  # Rating not available from pagination endpoint
        'reviews': all_reviews,
    }


def enrich_businesses(
    businesses: Dict[str, Dict],
    fetch_details: bool = True,
    fetch_reviews_flag: bool = True,
    reviews_limit: int = 5,
    details_delay: float = DELAY_BETWEEN_DETAILS,
    reviews_delay: float = DELAY_BETWEEN_REVIEWS,
    verbose: bool = True,
    cookies: Dict = None,
) -> Dict[str, Dict]:
    """
    Enrich all businesses with detailed information and reviews.

    Args:
        businesses: Dictionary of place_id -> business data
        fetch_details: Whether to fetch place details
        fetch_reviews_flag: Whether to fetch reviews
        reviews_limit: Number of reviews to fetch per business
        details_delay: Delay between detail requests
        reviews_delay: Delay between review requests
        verbose: Whether to print progress
        cookies: Google cookies (required for reviews endpoint)

    Returns:
        Enriched businesses dictionary
    """
    # Use default cookies if not provided
    if cookies is None:
        cookies = get_google_cookies()

    total = len(businesses)
    enriched = {}

    if verbose:
        print(f"\nEnriching {total} businesses...")

    for i, (place_id, business) in enumerate(businesses.items()):
        name = business.get('name', 'Unknown')

        if verbose:
            try:
                print(f"\n  [{i+1}/{total}] {name[:40]}...")
            except UnicodeEncodeError:
                print(f"\n  [{i+1}/{total}] [non-ASCII name]...")

        enriched_business = dict(business)

        # Fetch place details
        if fetch_details and place_id:
            details = fetch_place_details(
                place_id,
                name=business.get('name'),
                latitude=business.get('latitude'),
                longitude=business.get('longitude'),
                hex_id=business.get('hex_id'),
                ftid=business.get('ftid'),
            )
            if details:
                # Merge details into business, preserving existing values
                for key, value in details.items():
                    if value is not None and (key not in enriched_business or enriched_business[key] is None):
                        enriched_business[key] = value
                if verbose:
                    print(f"    [OK] Details fetched")
            else:
                if verbose:
                    print(f"    [!] No details available")

            time.sleep(details_delay)

        # Fetch reviews
        if fetch_reviews_flag and place_id:
            review_info = fetch_reviews(
                place_id,
                name=business.get('name'),
                latitude=business.get('latitude'),
                longitude=business.get('longitude'),
                hex_id=business.get('hex_id'),
                ftid=business.get('ftid'),
                limit=reviews_limit,
                cookies=cookies,
            )
            if review_info:
                if review_info.get('review_count') and not enriched_business.get('review_count'):
                    enriched_business['review_count'] = review_info['review_count']
                if review_info.get('rating') and not enriched_business.get('rating'):
                    enriched_business['rating'] = review_info['rating']
                if review_info.get('reviews'):
                    enriched_business['reviews_data'] = review_info['reviews']
                if verbose:
                    print(f"    [OK] Reviews: count={review_info.get('review_count', 0)}, rating={review_info.get('rating', 'N/A')}")
            else:
                if verbose:
                    print(f"    [!] No review info available")

            time.sleep(reviews_delay)

        enriched[place_id] = enriched_business

    return enriched
