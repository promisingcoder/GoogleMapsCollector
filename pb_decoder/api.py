"""
FastAPI Backend for Google Maps PB Decoder

Provides endpoints for:
- Decoding curl commands
- Modifying parameters
- Executing requests
"""

import json
import re
import asyncio
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
from urllib.parse import urlencode, quote, unquote

from .main_decoder import decode_google_maps_curl, DecodedRequest
from .pb_decoder import PbDecoder

app = FastAPI(title="Google Maps PB Decoder API")

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CurlInput(BaseModel):
    curl_command: str


class ModifiedRequest(BaseModel):
    original_curl: str
    url_params: Dict[str, str]
    pb_params: List[Dict[str, Any]]
    headers: Dict[str, str]


class PbParam(BaseModel):
    path: str
    field: int
    type: str
    value: Any
    original_value: Any


class PlaceDetailsRequest(BaseModel):
    place_id: str  # ChIJ... format or hex format 0x...:0x...
    name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    ftid: Optional[str] = None  # Feature ID like /g/11b5wlq0vc
    hex_id: Optional[str] = None  # Hex format place ID 0x...:0x...


class ReviewsRequest(BaseModel):
    place_id: str  # ChIJ... format or hex format 0x...:0x...
    name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    ftid: Optional[str] = None  # Feature ID like /g/11b5wlq0vc
    hex_id: Optional[str] = None  # Hex format place ID
    sort_by: Optional[str] = "newest"  # newest, highest, lowest
    offset: Optional[int] = 0
    limit: Optional[int] = 10


def rebuild_pb_string(pb_params: List[Dict[str, Any]]) -> str:
    """
    Rebuild pb string from flat parameters.
    This reconstructs the pb parameter from the modified flat list.
    """
    # Group params by their message hierarchy
    # Build a tree structure first, then serialize

    root_fields = []
    message_children = {}  # path -> list of children

    for param in pb_params:
        path = param['path']
        field = param['field']
        ptype = param['type']
        value = param['value']

        # Parse the path to find parent
        parts = path.split('!')
        parts = [p for p in parts if p]  # Remove empty strings

        if len(parts) == 1:
            # Root level field
            root_fields.append((field, ptype, value, path))
        else:
            # Nested field - find parent path
            parent_parts = parts[:-1]
            parent_path = '!' + '!'.join(parent_parts)
            if parent_path not in message_children:
                message_children[parent_path] = []
            message_children[parent_path].append((field, ptype, value, path))

    def serialize_field(field: int, ptype: str, value: Any, path: str) -> str:
        if ptype == 'm':
            # Message field - need to count children and serialize them
            children = message_children.get(path, [])
            child_count = count_all_fields(children, message_children)
            child_str = ''.join(serialize_field(f, t, v, p) for f, t, v, p in children)
            return f"!{field}m{child_count}{child_str}"
        else:
            # Regular field
            if ptype == 's':
                return f"!{field}s{value}"
            elif ptype == 'i':
                return f"!{field}i{int(value)}"
            elif ptype == 'd':
                return f"!{field}d{value}"
            elif ptype == 'f':
                return f"!{field}f{value}"
            elif ptype == 'b':
                return f"!{field}b{'1' if value else '0'}"
            elif ptype == 'e':
                return f"!{field}e{int(value)}"
            else:
                return f"!{field}{ptype}{value}"

    def count_all_fields(fields: List, children_map: Dict) -> int:
        """Count total fields including nested ones"""
        count = 0
        for f, t, v, p in fields:
            count += 1
            if t == 'm':
                nested = children_map.get(p, [])
                count += count_all_fields(nested, children_map)
        return count

    # Serialize root fields
    result = ''.join(serialize_field(f, t, v, p) for f, t, v, p in root_fields)
    return result


def build_url_with_params(base_url: str, url_params: Dict[str, str], pb_string: str) -> str:
    """Build the full URL with modified parameters"""
    # Parse base URL to get scheme, host, path
    match = re.match(r'(https?://[^/]+)([^?]*)', base_url)
    if match:
        base = match.group(1) + match.group(2)
    else:
        base = base_url.split('?')[0]

    # Add pb parameter
    all_params = dict(url_params)
    all_params['pb'] = pb_string

    # Build query string
    query = urlencode(all_params, safe='!@#$%^&*()_+-=[]{}|;:,.<>?')

    return f"{base}?{query}"


@app.post("/api/decode")
async def decode_curl(input: CurlInput):
    """Decode a curl command and return structured parameters"""
    try:
        result = decode_google_maps_curl(input.curl_command)

        return {
            "success": True,
            "data": {
                "url": result.url,
                "method": result.method,
                "url_params": result.url_params,
                "pb_raw": result.pb_raw,
                "pb_params": result.pb_flat,
                "headers": result.headers,
                "cookies": result.cookies,
                "extracted": {
                    "search_query": result.search_query,
                    "latitude": result.latitude,
                    "longitude": result.longitude,
                    "viewport_distance": result.viewport_distance,
                    "results_count": result.results_count,
                    "offset": result.offset,
                    "max_radius": result.max_radius,
                    "zoom_level": result.zoom_level,
                }
            }
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/execute")
async def execute_request(request: ModifiedRequest):
    """Execute the modified request and return results"""
    try:
        # First decode the original to get base URL and other info
        original = decode_google_maps_curl(request.original_curl)

        # Use original pb string unless values were actually modified
        # Check if any param values differ from their original values
        def values_equal(v1, v2):
            """Compare values with tolerance for floats"""
            if v1 is None and v2 is None:
                return True
            if v1 is None or v2 is None:
                return False
            # Handle numeric comparisons with tolerance
            if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                return abs(float(v1) - float(v2)) < 1e-9
            # String comparison
            return str(v1) == str(v2)

        params_modified = False
        if request.pb_params:
            for param in request.pb_params:
                if not values_equal(param.get('value'), param.get('original_value')):
                    params_modified = True
                    break

        if params_modified:
            # Rebuild only if user modified values
            pb_string = rebuild_pb_string(request.pb_params)
            if not pb_string:
                pb_string = original.pb_raw
        else:
            # Use original pb string (more reliable)
            pb_string = original.pb_raw

        # Merge URL params: start with original, override with user-provided
        merged_url_params = dict(original.url_params)
        if request.url_params:
            merged_url_params.update(request.url_params)

        # Build the new URL with merged params
        new_url = build_url_with_params(original.url, merged_url_params, pb_string)

        # Merge headers: start with original, override with user-provided
        headers = dict(original.headers)
        if request.headers:
            headers.update(request.headers)
        if 'user-agent' not in {k.lower() for k in headers}:
            headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

        # Execute the request
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(new_url, headers=headers)

            # Parse the response
            response_text = response.text

            # Google Maps returns data with )]}' prefix
            if response_text.startswith(")]}'"):
                response_text = response_text[4:].strip()

            # Try to parse as JSON
            try:
                # Find the first complete JSON array
                data = None
                depth = 0
                start = None

                for i, char in enumerate(response_text):
                    if char == '[':
                        if depth == 0:
                            start = i
                        depth += 1
                    elif char == ']':
                        depth -= 1
                        if depth == 0 and start is not None:
                            try:
                                data = json.loads(response_text[start:i+1])
                                break
                            except json.JSONDecodeError:
                                continue

                if data is None:
                    data = json.loads(response_text)

                # Extract businesses from the response
                businesses = extract_businesses(data)

                return {
                    "success": True,
                    "request": {
                        "url": new_url,
                        "pb_string": pb_string,
                    },
                    "response": {
                        "status_code": response.status_code,
                        "business_count": len(businesses),
                        "businesses": businesses,
                    }
                }

            except json.JSONDecodeError as e:
                return {
                    "success": True,
                    "request": {
                        "url": new_url,
                        "pb_string": pb_string,
                    },
                    "response": {
                        "status_code": response.status_code,
                        "raw_text": response_text[:5000],
                        "parse_error": str(e),
                    }
                }

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Request timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def extract_businesses(data: Any) -> List[Dict]:
    """
    Extract business information from Google Maps response.

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
    from urllib.parse import parse_qs, urlparse
    import logging

    logger = logging.getLogger(__name__)
    businesses = []

    def safe_get(obj, *indices, default=None):
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

    def extract_website(biz_data):
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

    def extract_phone(biz_data):
        """Extract phone number from biz[178][0][0]"""
        phone_data = safe_get(biz_data, 178)
        if isinstance(phone_data, list) and len(phone_data) > 0:
            # Phone is nested: [['+1 123-456-7890', ...]]
            inner = phone_data[0]
            if isinstance(inner, list) and len(inner) > 0:
                phone = inner[0]
                if isinstance(phone, str) and (phone.startswith('+') or phone.startswith('(')):
                    return phone
            # Fallback: direct string
            elif isinstance(inner, str) and (inner.startswith('+') or inner.startswith('(')):
                return inner
        return None

    def extract_single_business(biz_data):
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
        }

        # Rating at [4][7]
        business["rating"] = safe_get(biz_data, 4, 7)

        # Reviews at [4][8]
        business["reviews"] = safe_get(biz_data, 4, 8)

        # Coordinates at [9][2] (lat) and [9][3] (lng)
        business["latitude"] = safe_get(biz_data, 9, 2)
        business["longitude"] = safe_get(biz_data, 9, 3)

        # Phone at [178][0]
        business["phone"] = extract_phone(biz_data)

        # Website from [7]
        business["website"] = extract_website(biz_data)

        # Category at [13][0]
        categories = safe_get(biz_data, 13)
        if isinstance(categories, list) and len(categories) > 0:
            business["category"] = categories[0] if isinstance(categories[0], str) else None

        return business

    def find_business_arrays(obj, depth=0, max_depth=10):
        """Recursively search for arrays that look like business entries"""
        found = []
        if depth > max_depth:
            return found

        if isinstance(obj, list):
            # Check if this looks like a business entry array (has [14] with business data)
            for i, item in enumerate(obj):
                if isinstance(item, list) and len(item) > 14:
                    biz_data = safe_get(item, 14)
                    if isinstance(biz_data, list) and len(biz_data) > 11:
                        name = safe_get(biz_data, 11)
                        if isinstance(name, str) and len(name) > 2:
                            # This looks like a business entry
                            found.append(item)

            # Recurse into ALL sublists (not just first few)
            for item in obj:
                if isinstance(item, list):
                    found.extend(find_business_arrays(item, depth + 1, max_depth))

        return found

    def search_all_indices(data):
        """Search through all top-level indices for business data"""
        found = []
        if not isinstance(data, list):
            return found

        # Search each top-level element
        for i, element in enumerate(data):
            if isinstance(element, list):
                # Look for arrays that contain business entries
                entries = find_business_arrays(element, depth=0, max_depth=8)
                found.extend(entries)

        return found

    try:
        # Method 1: Search ALL indices for business entries
        business_entries = search_all_indices(data)

        for entry in business_entries:
            biz_data = safe_get(entry, 14)
            if biz_data and isinstance(biz_data, list):
                business = extract_single_business(biz_data)
                if business and business.get('name'):
                    businesses.append(business)

        # Method 2: Organic results at data[64][i][1] (alternative location)
        # The structure at [1] is the same as [14] in the original location
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


@app.post("/api/place-details")
async def get_place_details(request: PlaceDetailsRequest):
    """
    Fetch detailed information about a place using Google Maps place preview endpoint.

    Uses /maps/preview/place endpoint which returns full details including:
    - Business hours
    - Photos URLs
    - Full description
    - All categories
    - Price level
    - Attributes/amenities
    - Reviews

    Required: place_id (or hex_id) and name
    Recommended: latitude, longitude, ftid for best results
    """
    try:
        # Determine which place ID format to use
        # Prefer hex_id if provided, otherwise use place_id
        place_id_for_url = request.hex_id if request.hex_id else request.place_id

        # URL encode the name
        name_encoded = quote(request.name) if request.name else quote(request.place_id)
        name_plus = name_encoded.replace('%20', '+')

        # Use coordinates if provided
        lat = request.latitude if request.latitude else 40.7128
        lng = request.longitude if request.longitude else -74.0060

        # Build ftid part if provided
        ftid_part = ""
        if request.ftid:
            ftid_encoded = quote(request.ftid)
            ftid_part = f"!15m2!1m1!4s{ftid_encoded}"

        # Build the pb parameter for place details request
        # Format based on actual Google Maps place request
        pb_string = (
            f"!1m17"
            f"!1s{quote(place_id_for_url)}"
            f"!2s{name_encoded}"
            f"!3m8!1m3!1d3000!2d{lng}!3d{lat}!3m2!1i1024!2i768!4f13.1"
            f"!4m2!3d{lat}!4d{lng}"
            f"{ftid_part}"
            "!12m4!2m3!1i360!2i120!4i8"
            "!13m57!2m2!1i203!2i100!3m2!2i4!5b1"
            "!6m6!1m2!1i86!2i86!1m2!1i408!2i240"
            "!7m33!1m3!1e1!2b0!3e3!1m3!1e2!2b1!3e2!1m3!1e2!2b0!3e3!1m3!1e8!2b0!3e3!1m3!1e10!2b0!3e3!1m3!1e10!2b1!3e2!1m3!1e10!2b0!3e4!1m3!1e9!2b1!3e2!2b1!9b0"
            "!15m8!1m7!1m2!1m1!1e2!2m2!1i195!2i195!3i20"
            "!15m108!1m29!13m9!2b1!3b1!4b1!6i1!8b1!9b1!14b1!20b1!25b1"
            "!18m18!3b1!4b1!5b1!6b1!13b1!14b1!17b1!21b1!22b1!27m1!1b0!28b0!30b1!32b1!33m1!1b1!34b1!36e2"
            "!10m1!8e3!11m1!3e1!14m1!3b0!17b1!20m2!1e3!1e6!24b1!25b1!26b1!27b1!29b1!30m1!2b1!36b1!37b1"
            "!39m3!2m2!2i1!3i1!43b1!52b1!54m1!1b1!55b1!56m1!1b1!61m2!1m1!1e1!65m5!3m4!1m3!1m2!1i224!2i298"
            "!72m22!1m8!2b1!5b1!7b1!12m4!1b1!2b1!4m1!1e1!4b1!8m10!1m6!4m1!1e1!4m1!1e3!4m1!1e4!3sother_user_google_review_posts__and__hotel_and_vr_partner_review_posts!6m1!1e1!9b1"
            "!89b1!98m3!1b1!2b1!3b1!103b1!113b1!114m3!1b1!2m1!1b1!117b1!122m1!1b1!126b1!127b1"
            "!21m0!22m1!1e81"
            "!30m8!3b1!6m2!1b1!2b1!7m2!1e3!2b1!9b1"
            "!34m5!7b1!10b1!14b1!15m1!1b0"
            "!37i763"
        )

        url = f"https://www.google.com/maps/preview/place?authuser=0&hl=en&gl=us&q={name_plus}&pb={pb_string}"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': f'https://www.google.com/maps/place/{name_plus}/',
            'Origin': 'https://www.google.com',
        }

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response_text = response.text

            # Remove )]}' prefix if present
            if response_text.startswith(")]}'"):
                response_text = response_text[4:].strip()

            try:
                # Find and parse the JSON array
                data = None
                depth = 0
                start = None

                for i, char in enumerate(response_text):
                    if char == '[':
                        if depth == 0:
                            start = i
                        depth += 1
                    elif char == ']':
                        depth -= 1
                        if depth == 0 and start is not None:
                            try:
                                data = json.loads(response_text[start:i+1])
                                break
                            except json.JSONDecodeError:
                                continue

                if data is None:
                    data = json.loads(response_text)

                # Extract place details from the place response
                details = extract_place_details_from_place_response(data)

                # Also extract reviews from the place response
                reviews = extract_reviews_from_place_response(data)
                if reviews:
                    details['reviews'] = reviews

                return {
                    "success": True,
                    "place_id": request.place_id,
                    "details": details,
                }
            except json.JSONDecodeError as e:
                return {
                    "success": False,
                    "error": f"Failed to parse response: {str(e)}",
                    "raw_text": response_text[:2000],
                }

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Request timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def extract_place_details(data: Any) -> Dict:
    """
    Extract detailed place information from Google Maps place response.

    The response structure contains:
    - [6] = Place data array
    - [6][13] = Categories array
    - [6][34] = Hours data
    - [6][36] = Photos
    - [6][32] = Description/About
    - [6][4][2] = Price level
    """
    def safe_get(obj, *indices, default=None):
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

    details = {}

    # The main place data is typically at index [6]
    place_data = safe_get(data, 6)
    if not place_data:
        # Try alternative location
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

    # Price level (1-4, where 1 = cheap, 4 = expensive)
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
        from urllib.parse import parse_qs, urlparse
        for item in contact[:5]:
            if isinstance(item, str) and '/url?q=' in item:
                try:
                    parsed = parse_qs(urlparse(item).query)
                    if 'q' in parsed:
                        details['website'] = parsed['q'][0]
                        break
                except:
                    pass

    # Business hours
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
            details['photos'] = photos[:10]  # Limit to 10 photos

    # Description/About
    about = safe_get(place_data, 32)
    if isinstance(about, list):
        for item in about:
            if isinstance(item, list) and len(item) > 1:
                desc = item[1] if isinstance(item[1], str) else None
                if desc:
                    details['description'] = desc
                    break

    # Attributes/Amenities
    attributes = safe_get(place_data, 100)
    if isinstance(attributes, list):
        amenities = extract_amenities(attributes)
        if amenities:
            details['amenities'] = amenities

    return details


def extract_place_details_from_place_response(data: Any) -> Dict:
    """
    Extract detailed place information from Google Maps /maps/preview/place response.

    The place response structure is different from search response.
    Main data is typically at data[6] with nested arrays containing:
    - [11] = name
    - [18] = address
    - [4][7] = rating
    - [4][8] = review count
    - [9][2], [9][3] = lat, lng
    - [13] = categories
    - [34] = hours
    - [52] = reviews array
    - [178] = phone
    """
    def safe_get(obj, *indices, default=None):
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
        # Try alternative location
        phone = safe_get(place_data, 178, 0, 0)
    details['phone'] = phone

    # Website
    contact = safe_get(place_data, 7)
    if isinstance(contact, list):
        from urllib.parse import parse_qs, urlparse
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

    # Business hours
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


def extract_reviews_from_place_response(data: Any) -> List[Dict]:
    """
    Extract reviews from Google Maps /maps/preview/place response.

    Reviews are typically found at data[6][52] or nested within the response.
    Each review contains:
    - Author name
    - Rating (1-5)
    - Review text
    - Date/time
    - Profile photo URL
    """
    def safe_get(obj, *indices, default=None):
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

    reviews = []

    # Try to find reviews at data[6][52]
    place_data = safe_get(data, 6)
    if not place_data:
        place_data = data

    reviews_data = safe_get(place_data, 52)
    if not reviews_data:
        # Try alternative locations
        reviews_data = safe_get(place_data, 52, 0)

    if not isinstance(reviews_data, list):
        # Search recursively for review-like structures
        reviews_data = find_reviews_in_data(data)

    if isinstance(reviews_data, list):
        for review_entry in reviews_data:
            if not isinstance(review_entry, list):
                continue

            review = extract_single_review(review_entry)
            if review and review.get('author'):
                reviews.append(review)

    return reviews


def find_reviews_in_data(data: Any, depth: int = 0) -> List:
    """Recursively search for review arrays in the data structure."""
    if depth > 8:
        return []

    if isinstance(data, list):
        # Check if this looks like a reviews array
        # Reviews typically have author info, rating, and text
        if len(data) > 0:
            first = data[0] if len(data) > 0 else None
            if isinstance(first, list) and len(first) > 3:
                # Check if items look like reviews
                review_count = 0
                for item in data[:5]:
                    if isinstance(item, list):
                        # Look for review characteristics
                        has_text = any(isinstance(x, str) and len(x) > 20 for x in item[:10] if x)
                        has_rating = any(isinstance(x, int) and 1 <= x <= 5 for x in item[:10] if x)
                        if has_text or has_rating:
                            review_count += 1
                if review_count >= 2:
                    return data

        # Recurse into sublists
        for item in data:
            result = find_reviews_in_data(item, depth + 1)
            if result:
                return result

    return []


def extract_single_review(review_data: List) -> Optional[Dict]:
    """Extract a single review from a review data array."""
    def safe_get(obj, *indices, default=None):
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
                else:
                    return default
            return current
        except:
            return default

    if not isinstance(review_data, list) or len(review_data) < 3:
        return None

    review = {}

    # Try to find author name - usually in first few elements
    for i in range(min(5, len(review_data))):
        item = review_data[i]
        if isinstance(item, list) and len(item) > 0:
            # Author info is often nested
            author = safe_get(item, 0, 1) or safe_get(item, 1)
            if isinstance(author, str) and len(author) > 1 and len(author) < 100:
                review['author'] = author
                break
        elif isinstance(item, str) and len(item) > 1 and len(item) < 100:
            # Direct author name
            if not item.startswith('http') and not any(c.isdigit() for c in item[:3]):
                review['author'] = item
                break

    # Find rating (integer 1-5)
    for i in range(min(10, len(review_data))):
        item = review_data[i]
        if isinstance(item, int) and 1 <= item <= 5:
            review['rating'] = item
            break

    # Find review text (longer string)
    for i in range(min(15, len(review_data))):
        item = review_data[i]
        if isinstance(item, str) and len(item) > 30:
            review['text'] = item
            break
        elif isinstance(item, list):
            # Text might be nested
            for j in range(min(5, len(item))):
                if isinstance(item[j], str) and len(item[j]) > 30:
                    review['text'] = item[j]
                    break
            if review.get('text'):
                break

    # Find date string
    for i in range(min(20, len(review_data))):
        item = review_data[i]
        if isinstance(item, str):
            # Look for date patterns
            if 'ago' in item.lower() or 'week' in item.lower() or 'month' in item.lower() or 'year' in item.lower():
                review['date'] = item
                break
            if any(month in item.lower() for month in ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']):
                review['date'] = item
                break

    # Only return if we have at least author or text
    if review.get('author') or review.get('text'):
        return review
    return None


def extract_business_hours(hours_data: List) -> Optional[Dict[str, str]]:
    """Extract business hours from the hours data array."""
    days = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
    hours = {}

    try:
        # Hours are typically at [1] with each day's schedule
        schedule = hours_data[1] if len(hours_data) > 1 else hours_data

        if isinstance(schedule, list):
            for i, day_data in enumerate(schedule):
                if i >= 7:
                    break
                day_name = days[i]

                if isinstance(day_data, list) and len(day_data) > 0:
                    # Check for closed status
                    if day_data[0] == 'Closed' or (isinstance(day_data[0], list) and len(day_data[0]) == 0):
                        hours[day_name] = 'Closed'
                    else:
                        # Extract time ranges
                        time_str = day_data[0] if isinstance(day_data[0], str) else str(day_data[0])
                        hours[day_name] = time_str
                else:
                    hours[day_name] = 'Unknown'

        return hours if hours else None
    except:
        return None


def extract_photos(photos_data: List) -> List[str]:
    """Extract photo URLs from the photos data array."""
    photos = []

    def find_photo_urls(obj, depth=0):
        if depth > 5:
            return
        if isinstance(obj, str):
            # Look for Google Maps photo URLs
            if 'googleusercontent.com' in obj or 'lh3.google' in obj or 'lh4.google' in obj or 'lh5.google' in obj:
                if obj not in photos:
                    photos.append(obj)
        elif isinstance(obj, list):
            for item in obj[:20]:  # Limit recursion breadth
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
            # Filter out obvious non-amenity strings
            if not obj.startswith('http') and not obj.startswith('0x'):
                amenities.append(obj)
        elif isinstance(obj, list):
            for item in obj[:30]:
                find_amenities(item, depth + 1)

    find_amenities(attributes_data)
    return list(set(amenities))[:20]  # Dedupe and limit


@app.post("/api/reviews")
async def get_reviews(request: ReviewsRequest):
    """
    Fetch reviews for a place using Google Maps place endpoint.

    Uses /maps/preview/place to get actual reviews.

    Returns:
    - Review count
    - Average rating
    - List of reviews with author, rating, text, date
    """
    try:
        # Determine which place ID format to use (same logic as place-details)
        place_id_for_url = request.hex_id if request.hex_id else request.place_id

        # Use name if provided, otherwise use place_id
        name_encoded = quote(request.name) if request.name else quote(request.place_id)
        name_plus = name_encoded.replace('%20', '+')

        lat = request.latitude if request.latitude else 40.7128
        lng = request.longitude if request.longitude else -74.0060

        # Build ftid part if provided
        ftid_part = ""
        if request.ftid:
            ftid_encoded = quote(request.ftid)
            ftid_part = f"!15m2!1m1!4s{ftid_encoded}"

        # Build the pb parameter for place details request (includes reviews)
        # Exact same format as place-details endpoint
        pb_string = (
            f"!1m17"
            f"!1s{quote(place_id_for_url)}"
            f"!2s{name_encoded}"
            f"!3m8!1m3!1d3000!2d{lng}!3d{lat}!3m2!1i1024!2i768!4f13.1"
            f"!4m2!3d{lat}!4d{lng}"
            f"{ftid_part}"
            "!12m4!2m3!1i360!2i120!4i8"
            "!13m57!2m2!1i203!2i100!3m2!2i4!5b1"
            "!6m6!1m2!1i86!2i86!1m2!1i408!2i240"
            "!7m33!1m3!1e1!2b0!3e3!1m3!1e2!2b1!3e2!1m3!1e2!2b0!3e3!1m3!1e8!2b0!3e3!1m3!1e10!2b0!3e3!1m3!1e10!2b1!3e2!1m3!1e10!2b0!3e4!1m3!1e9!2b1!3e2!2b1!9b0"
            "!15m8!1m7!1m2!1m1!1e2!2m2!1i195!2i195!3i20"
            "!15m108!1m29!13m9!2b1!3b1!4b1!6i1!8b1!9b1!14b1!20b1!25b1"
            "!18m18!3b1!4b1!5b1!6b1!13b1!14b1!17b1!21b1!22b1!27m1!1b0!28b0!30b1!32b1!33m1!1b1!34b1!36e2"
            "!10m1!8e3!11m1!3e1!14m1!3b0!17b1!20m2!1e3!1e6!24b1!25b1!26b1!27b1!29b1!30m1!2b1!36b1!37b1"
            "!39m3!2m2!2i1!3i1!43b1!52b1!54m1!1b1!55b1!56m1!1b1!61m2!1m1!1e1!65m5!3m4!1m3!1m2!1i224!2i298"
            "!72m22!1m8!2b1!5b1!7b1!12m4!1b1!2b1!4m1!1e1!4b1!8m10!1m6!4m1!1e1!4m1!1e3!4m1!1e4!3sother_user_google_review_posts__and__hotel_and_vr_partner_review_posts!6m1!1e1!9b1"
            "!89b1!98m3!1b1!2b1!3b1!103b1!113b1!114m3!1b1!2m1!1b1!117b1!122m1!1b1!126b1!127b1"
            "!21m0!22m1!1e81"
            "!30m8!3b1!6m2!1b1!2b1!7m2!1e3!2b1!9b1"
            "!34m5!7b1!10b1!14b1!15m1!1b0"
            "!37i763"
        )

        url = f"https://www.google.com/maps/preview/place?authuser=0&hl=en&gl=us&q={name_plus}&pb={pb_string}"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': f'https://www.google.com/maps/place/{name_plus}/',
            'Origin': 'https://www.google.com',
        }

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response_text = response.text

            # Remove )]}' prefix if present
            if response_text.startswith(")]}'"):
                response_text = response_text[4:].strip()

            try:
                # Find and parse the JSON array
                data = None
                depth = 0
                start = None

                for i, char in enumerate(response_text):
                    if char == '[':
                        if depth == 0:
                            start = i
                        depth += 1
                    elif char == ']':
                        depth -= 1
                        if depth == 0 and start is not None:
                            try:
                                data = json.loads(response_text[start:i+1])
                                break
                            except json.JSONDecodeError:
                                continue

                if data is None:
                    data = json.loads(response_text)

                # Extract place details for review count/rating
                details = extract_place_details_from_place_response(data)

                # Extract reviews from place response
                reviews = extract_reviews_from_place_response(data)

                return {
                    "success": True,
                    "place_id": request.place_id,
                    "review_count": details.get('review_count', len(reviews)),
                    "rating": details.get('rating'),
                    "reviews": reviews,
                }

            except json.JSONDecodeError as e:
                return {
                    "success": False,
                    "error": f"Failed to parse response: {str(e)}",
                    "raw_text": response_text[:2000],
                }

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Request timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def extract_reviews(data: Any) -> List[Dict]:
    """
    Extract reviews from Google Maps review response.

    Review structure typically:
    - [2] = Reviews array
    - Each review: [0]=author, [1]=profile pic, [2]=review id, [3]=text, [4]=rating, [6]=date
    """
    def safe_get(obj, *indices, default=None):
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

    reviews = []

    # Reviews are typically in data[2]
    reviews_array = safe_get(data, 2)
    if not isinstance(reviews_array, list):
        # Try alternative location
        reviews_array = data if isinstance(data, list) else []

    def find_reviews(obj, depth=0):
        """Recursively search for review-like structures."""
        if depth > 6:
            return

        if isinstance(obj, list):
            # Check if this looks like a review entry
            # Reviews typically have: author name, rating (1-5), text
            if len(obj) > 4:
                author = safe_get(obj, 0, 1) or safe_get(obj, 0)
                rating = None
                text = None
                date = None

                # Look for rating (integer 1-5)
                for i in range(min(10, len(obj))):
                    val = obj[i]
                    if isinstance(val, int) and 1 <= val <= 5:
                        rating = val
                        break

                # Look for text (longer string)
                for i in range(min(10, len(obj))):
                    val = obj[i]
                    if isinstance(val, str) and len(val) > 20:
                        text = val
                        break
                    elif isinstance(val, list):
                        # Text might be nested
                        for j in range(min(5, len(val))):
                            if isinstance(val[j], str) and len(val[j]) > 20:
                                text = val[j]
                                break

                # Look for date string
                for i in range(min(15, len(obj))):
                    val = obj[i]
                    if isinstance(val, str) and ('ago' in val.lower() or '202' in val or '201' in val):
                        date = val
                        break

                if author and isinstance(author, str) and (rating or text):
                    review = {
                        'author': author,
                        'rating': rating,
                        'text': text,
                        'date': date,
                    }

                    # Look for helpful count
                    for i in range(min(20, len(obj))):
                        val = obj[i]
                        if isinstance(val, list) and len(val) > 0:
                            if isinstance(val[0], int) and val[0] > 0 and val[0] < 10000:
                                review['helpful_count'] = val[0]
                                break

                    reviews.append(review)
                    return

            # Recurse into sublists
            for item in obj:
                find_reviews(item, depth + 1)

    find_reviews(reviews_array)

    # Deduplicate by author + text
    seen = set()
    unique_reviews = []
    for review in reviews:
        key = (review.get('author', ''), review.get('text', '')[:50] if review.get('text') else '')
        if key not in seen:
            seen.add(key)
            unique_reviews.append(review)

    return unique_reviews


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
