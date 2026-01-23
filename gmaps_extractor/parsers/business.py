"""
Business Data Extractor

Extracts business information from Google Maps search responses.

Google Maps response structure varies by query type:
- Organic results: data[0][1][i][14] or deeper nested
- Ads: data[2][11][0][i]

Business data at [14] contains:
    [11] = name
    [18] = full address
    [78] = place_id
    [4][7] = rating
    [4][8] = review count
    [9][2] = latitude
    [9][3] = longitude
    [178][0] = phone number
    [7] = contains website URL (needs parsing)
    [13] = categories array
"""

from typing import Dict, List, Any
from urllib.parse import parse_qs, urlparse


def safe_get(obj: Any, *indices, default=None) -> Any:
    """Safely traverse nested structures"""
    try:
        current = obj
        for idx in indices:
            if current is None:
                return default
            if isinstance(current, list) and isinstance(idx, int):
                if idx < len(current):
                    current = current[idx]
                else:
                    return default
            elif isinstance(current, dict):
                current = current.get(idx, default)
            else:
                return default
        return current
    except (IndexError, KeyError, TypeError):
        return default


def extract_website(biz_data: List) -> str:
    """Extract website URL from biz[7] array"""
    contact = safe_get(biz_data, 7)
    if not isinstance(contact, list):
        return None

    for item in contact[:5]:
        if isinstance(item, str) and '/url?q=' in item:
            try:
                parsed = parse_qs(urlparse(item).query)
                if 'q' in parsed:
                    return parsed['q'][0]
            except:
                pass
    return None


def extract_phone(biz_data: List) -> str:
    """Extract phone number from biz[178][0][0]"""
    phone_data = safe_get(biz_data, 178)
    if isinstance(phone_data, list) and len(phone_data) > 0:
        inner = phone_data[0]
        if isinstance(inner, list) and len(inner) > 0:
            phone = inner[0]
            if isinstance(phone, str) and (phone.startswith('+') or phone.startswith('(')):
                return phone
        elif isinstance(inner, str) and (inner.startswith('+') or inner.startswith('(')):
            return inner
    return None


def extract_single_business(biz_data: List) -> Dict:
    """Extract business info from the business data array"""
    if not isinstance(biz_data, list) or len(biz_data) < 12:
        return None

    name = safe_get(biz_data, 11)
    if not name or not isinstance(name, str):
        return None

    # Skip entries that look like encoded/garbage data
    if len(name) < 2 or name.endswith('='):
        return None
    if all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=' for c in name):
        return None

    business = {
        "name": name,
        "address": safe_get(biz_data, 18),
        "place_id": safe_get(biz_data, 78),
        "hex_id": safe_get(biz_data, 10),  # Hex ID for place-details endpoint
        "ftid": safe_get(biz_data, 89),  # Feature ID like /g/11b5wlq0vc
        "rating": safe_get(biz_data, 4, 7),
        "review_count": safe_get(biz_data, 4, 8),
        "latitude": safe_get(biz_data, 9, 2),
        "longitude": safe_get(biz_data, 9, 3),
        "phone": extract_phone(biz_data),
        "website": extract_website(biz_data),
    }

    # Category at [13][0]
    categories = safe_get(biz_data, 13)
    if isinstance(categories, list) and len(categories) > 0:
        business["category"] = categories[0] if isinstance(categories[0], str) else None

    return business


def find_business_arrays(obj: Any, depth: int = 0, max_depth: int = 10) -> List:
    """Recursively search for arrays that look like business entries"""
    found = []
    if depth > max_depth:
        return found

    if isinstance(obj, list):
        for i, item in enumerate(obj):
            if isinstance(item, list) and len(item) > 14:
                biz_data = safe_get(item, 14)
                if isinstance(biz_data, list) and len(biz_data) > 11:
                    name = safe_get(biz_data, 11)
                    if isinstance(name, str) and len(name) > 2:
                        found.append(item)

        for item in obj:
            if isinstance(item, list):
                found.extend(find_business_arrays(item, depth + 1, max_depth))

    return found


def search_all_indices(data: List) -> List:
    """Search through all top-level indices for business data"""
    found = []
    if not isinstance(data, list):
        return found

    for i, element in enumerate(data):
        if isinstance(element, list):
            entries = find_business_arrays(element, depth=0, max_depth=8)
            found.extend(entries)

    return found


def extract_businesses(data: Any) -> List[Dict]:
    """
    Extract business information from Google Maps response.

    Args:
        data: Parsed JSON response from Google Maps

    Returns:
        List of business dictionaries
    """
    businesses = []

    try:
        # Method 1: Search ALL indices for business entries
        business_entries = search_all_indices(data)

        for entry in business_entries:
            biz_data = safe_get(entry, 14)
            if biz_data and isinstance(biz_data, list):
                business = extract_single_business(biz_data)
                if business and business.get('name'):
                    businesses.append(business)

        # Method 2: Organic results at data[64][i][1]
        if isinstance(data, list) and len(data) > 64:
            organic_section = data[64]
            if isinstance(organic_section, list):
                for i, entry in enumerate(organic_section):
                    if isinstance(entry, list) and len(entry) > 1:
                        biz_data = entry[1] if isinstance(entry[1], list) else None
                        if biz_data and len(biz_data) > 11:
                            business = extract_single_business(biz_data)
                            if business and business.get('name'):
                                businesses.append(business)

        # Method 3: Ads/sponsored results at data[2][11][0][i]
        ads_entries = safe_get(data, 2, 11, 0, default=[])
        if isinstance(ads_entries, list):
            for ad in ads_entries:
                if not isinstance(ad, list) or len(ad) < 3:
                    continue

                name = safe_get(ad, 1)
                if not name or not isinstance(name, str):
                    continue

                business = {
                    "name": name,
                    "place_id": safe_get(ad, 0),
                    "latitude": safe_get(ad, 2, 0, 2),
                    "longitude": safe_get(ad, 2, 0, 3),
                    "rating": safe_get(ad, 2, 6),
                    "is_ad": True,
                }

                website_url = safe_get(ad, 3, 1)
                if website_url and isinstance(website_url, str) and not website_url.startswith('https://www.google.com'):
                    business["website"] = website_url

                if business.get('name'):
                    businesses.append(business)

        # Dedupe by place_id or name
        seen = set()
        unique = []
        for biz in businesses:
            key = biz.get('place_id') or biz.get('name')
            if key and key not in seen:
                seen.add(key)
                unique.append(biz)

        return unique

    except Exception as e:
        return []
