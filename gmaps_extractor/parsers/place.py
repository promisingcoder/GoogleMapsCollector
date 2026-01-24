"""
Place Details Extractor

Extracts detailed place information from Google Maps /maps/preview/place responses.

The place response structure contains:
- [6] = Place data array
- [6][11] = name
- [6][18] = address
- [6][4][7] = rating
- [6][4][8] = review count
- [6][9][2], [9][3] = lat, lng
- [6][13] = categories
- [6][34] = hours
- [6][36] = photos
- [6][52] = reviews array
- [6][178] = phone
"""

from typing import Dict, List, Any, Optional
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


def extract_business_hours(hours_data: List) -> Optional[Dict[str, str]]:
    """Extract business hours from the hours data array (old format at [34])."""
    days = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
    hours = {}

    try:
        schedule = hours_data[1] if len(hours_data) > 1 else hours_data

        if isinstance(schedule, list):
            for i, day_data in enumerate(schedule):
                if i >= 7:
                    break
                day_name = days[i]

                if isinstance(day_data, list) and len(day_data) > 0:
                    if day_data[0] == 'Closed' or (isinstance(day_data[0], list) and len(day_data[0]) == 0):
                        hours[day_name] = 'Closed'
                    else:
                        time_str = day_data[0] if isinstance(day_data[0], str) else str(day_data[0])
                        hours[day_name] = time_str
                else:
                    hours[day_name] = 'Unknown'

        return hours if hours else None
    except:
        return None


def extract_business_hours_new(hours_data: List) -> Optional[Dict[str, str]]:
    """Extract business hours from the new format at [203][0].

    New format structure:
    [
        ['Friday', 5, [2026, 1, 23], [['9 AM–5 PM', [[9], [17]]]], 0, 1],
        ['Saturday', 6, [2026, 1, 24], [['Closed']], 0, 2],
        ...
    ]

    Each entry: [day_name, day_num, [year, month, day], [[hours_string, ...]], flag1, flag2]
    """
    hours = {}

    try:
        if not isinstance(hours_data, list):
            return None

        for day_entry in hours_data:
            if not isinstance(day_entry, list) or len(day_entry) < 4:
                continue

            day_name = day_entry[0]  # e.g., 'Friday'
            hours_info = day_entry[3]  # e.g., [['9 AM–5 PM', [[9], [17]]]] or [['Closed']]

            if not isinstance(day_name, str):
                continue

            day_key = day_name.lower()

            if isinstance(hours_info, list) and len(hours_info) > 0:
                first_slot = hours_info[0]
                if isinstance(first_slot, list) and len(first_slot) > 0:
                    hours_str = first_slot[0]
                    if isinstance(hours_str, str):
                        # Clean up unicode characters (narrow no-break space, etc.)
                        hours_str = hours_str.replace('\u202f', ' ').replace('\u2013', '-')
                        hours[day_key] = hours_str
                    else:
                        hours[day_key] = 'Unknown'
                elif isinstance(first_slot, str):
                    hours[day_key] = first_slot.replace('\u202f', ' ').replace('\u2013', '-')
                else:
                    hours[day_key] = 'Unknown'
            else:
                hours[day_key] = 'Unknown'

        return hours if hours else None
    except Exception:
        return None


def extract_photos(photos_data: List) -> List[str]:
    """Extract photo URLs from the photos data array."""
    photos = []

    def find_photo_urls(obj, depth=0):
        if depth > 5:
            return
        if isinstance(obj, str):
            if 'googleusercontent.com' in obj or 'lh3.google' in obj or 'lh4.google' in obj or 'lh5.google' in obj:
                if obj not in photos:
                    photos.append(obj)
        elif isinstance(obj, list):
            for item in obj[:20]:
                find_photo_urls(item, depth + 1)

    find_photo_urls(photos_data)
    return photos


def extract_amenities(attributes_data: List) -> List[str]:
    """Extract amenities/attributes from the attributes data array."""
    amenities = []

    def find_amenities(obj, depth=0):
        if depth > 5:
            return
        if isinstance(obj, str) and len(obj) > 2 and len(obj) < 100:
            if not obj.startswith('http') and not obj.startswith('0x'):
                amenities.append(obj)
        elif isinstance(obj, list):
            for item in obj[:30]:
                find_amenities(item, depth + 1)

    find_amenities(attributes_data)
    return list(set(amenities))[:20]


def extract_place_details(data: Any) -> Dict:
    """
    Extract detailed place information from Google Maps place response.

    Args:
        data: Parsed JSON response

    Returns:
        Dictionary with place details
    """
    details = {}

    place_data = safe_get(data, 6)
    if not place_data:
        place_data = data

    # Basic info
    details['name'] = safe_get(place_data, 11)
    details['address'] = safe_get(place_data, 18)
    details['place_id'] = safe_get(place_data, 78)

    # Rating and reviews
    details['rating'] = safe_get(place_data, 4, 7)
    details['review_count'] = safe_get(place_data, 4, 8)

    # Coordinates
    details['latitude'] = safe_get(place_data, 9, 2)
    details['longitude'] = safe_get(place_data, 9, 3)

    # Categories
    categories = safe_get(place_data, 13)
    if isinstance(categories, list):
        details['categories'] = [c for c in categories if isinstance(c, str)]

    # Price level
    details['price_level'] = safe_get(place_data, 4, 2)

    # Phone number
    phone_data = safe_get(place_data, 178)
    if isinstance(phone_data, list) and len(phone_data) > 0:
        inner = phone_data[0]
        if isinstance(inner, list) and len(inner) > 0:
            details['phone'] = inner[0] if isinstance(inner[0], str) else None
        elif isinstance(inner, str):
            details['phone'] = inner

    # Website
    contact = safe_get(place_data, 7)
    if isinstance(contact, list):
        for item in contact[:5]:
            if isinstance(item, str) and '/url?q=' in item:
                try:
                    parsed = parse_qs(urlparse(item).query)
                    if 'q' in parsed:
                        details['website'] = parsed['q'][0]
                        break
                except:
                    pass

    # Business hours - try new location [203][0] first, fallback to old [34]
    hours_data_new = safe_get(place_data, 203, 0)
    if isinstance(hours_data_new, list) and len(hours_data_new) > 0:
        hours = extract_business_hours_new(hours_data_new)
        if hours:
            details['hours'] = hours
    else:
        # Fallback to old location [34]
        hours_data = safe_get(place_data, 34)
        if isinstance(hours_data, list):
            hours = extract_business_hours(hours_data)
            if hours:
                details['hours'] = hours

    # Photos
    photos_data = safe_get(place_data, 36)
    if isinstance(photos_data, list):
        photos = extract_photos(photos_data)
        if photos:
            details['photos'] = photos[:10]

    # Description
    about = safe_get(place_data, 32)
    if isinstance(about, list):
        for item in about:
            if isinstance(item, list) and len(item) > 1:
                desc = item[1] if isinstance(item[1], str) else None
                if desc:
                    details['description'] = desc
                    break

    # Amenities
    attributes = safe_get(place_data, 100)
    if isinstance(attributes, list):
        amenities = extract_amenities(attributes)
        if amenities:
            details['amenities'] = amenities

    return details


def extract_place_details_from_place_response(data: Any) -> Dict:
    """
    Extract detailed place information from Google Maps /maps/preview/place response.

    This is the main extraction function for place preview API responses.

    Args:
        data: Parsed JSON response from /maps/preview/place endpoint

    Returns:
        Dictionary with place details
    """
    details = {}

    # Try to find the main place data - usually at [6]
    place_data = safe_get(data, 6)
    if not place_data or not isinstance(place_data, list):
        place_data = data

    # Basic info
    details['name'] = safe_get(place_data, 11)
    details['address'] = safe_get(place_data, 18)
    details['place_id'] = safe_get(place_data, 78)

    # Rating and review count
    details['rating'] = safe_get(place_data, 4, 7)
    details['review_count'] = safe_get(place_data, 4, 8)

    # Coordinates
    details['latitude'] = safe_get(place_data, 9, 2)
    details['longitude'] = safe_get(place_data, 9, 3)

    # Categories
    categories = safe_get(place_data, 13)
    if isinstance(categories, list):
        details['categories'] = [c for c in categories if isinstance(c, str)]

    # Price level
    details['price_level'] = safe_get(place_data, 4, 2)

    # Phone number - try multiple locations
    phone = None
    phone_data = safe_get(place_data, 178)
    if isinstance(phone_data, list) and len(phone_data) > 0:
        inner = phone_data[0]
        if isinstance(inner, list) and len(inner) > 0:
            phone = inner[0] if isinstance(inner[0], str) else None
        elif isinstance(inner, str):
            phone = inner
    if not phone:
        phone = safe_get(place_data, 178, 0, 0)
    details['phone'] = phone

    # Website
    contact = safe_get(place_data, 7)
    if isinstance(contact, list):
        for item in contact[:10]:
            if isinstance(item, str) and '/url?q=' in item:
                try:
                    parsed = parse_qs(urlparse(item).query)
                    if 'q' in parsed:
                        details['website'] = parsed['q'][0]
                        break
                except:
                    pass
            elif isinstance(item, str) and item.startswith('http') and 'google.com' not in item:
                details['website'] = item
                break

    # Business hours - try new location [203][0] first, fallback to old [34]
    hours_data_new = safe_get(place_data, 203, 0)
    if isinstance(hours_data_new, list) and len(hours_data_new) > 0:
        hours = extract_business_hours_new(hours_data_new)
        if hours:
            details['hours'] = hours
    else:
        # Fallback to old location [34]
        hours_data = safe_get(place_data, 34)
        if isinstance(hours_data, list):
            hours = extract_business_hours(hours_data)
            if hours:
                details['hours'] = hours

    # Photos
    photos_data = safe_get(place_data, 36)
    if isinstance(photos_data, list):
        photos = extract_photos(photos_data)
        if photos:
            details['photos'] = photos[:10]

    # Description
    about = safe_get(place_data, 32)
    if isinstance(about, list):
        for item in about:
            if isinstance(item, list) and len(item) > 1:
                desc = item[1] if isinstance(item[1], str) else None
                if desc:
                    details['description'] = desc
                    break
            elif isinstance(item, str) and len(item) > 20:
                details['description'] = item
                break

    return details
