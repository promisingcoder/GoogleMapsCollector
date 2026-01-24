"""
FastAPI Server for Google Maps Business Extractor

Provides API endpoints for:
- Executing search requests
- Fetching place details
- Fetching reviews
"""

import json
import re
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
from urllib.parse import urlencode, quote, unquote

from .decoder import decode_google_maps_curl
from .decoder.pb import PbDecoder
from .parsers import (
    extract_businesses,
    extract_place_details_from_place_response,
    extract_reviews_from_place_response,
)
from .config import get_proxy_url, get_google_cookies


# FastAPI app
app = FastAPI(title="Google Maps Business Extractor API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request Models
class CurlInput(BaseModel):
    curl_command: str


class ModifiedRequest(BaseModel):
    original_curl: str
    url_params: Dict[str, str]
    pb_params: List[Dict[str, Any]]
    headers: Dict[str, str]


class PlaceDetailsRequest(BaseModel):
    place_id: str
    name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    ftid: Optional[str] = None
    hex_id: Optional[str] = None
    cookies: Optional[Dict[str, str]] = None  # Optional Google cookies for full reviews
    include_raw: Optional[bool] = False  # Include raw response for debugging


class ReviewsRequest(BaseModel):
    place_id: str
    name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    ftid: Optional[str] = None
    hex_id: Optional[str] = None
    sort_by: Optional[str] = "newest"
    offset: Optional[int] = 0
    limit: Optional[int] = 10
    pagination_token: Optional[str] = None  # Token for fetching next page of reviews
    cookies: Optional[Dict[str, str]] = None  # Optional Google cookies for full reviews


# Helper Functions
def rebuild_pb_string(pb_params: List[Dict[str, Any]]) -> str:
    """Rebuild pb string from flat parameters."""
    root_fields = []
    message_children = {}

    for param in pb_params:
        path = param['path']
        field = param['field']
        ptype = param['type']
        value = param['value']

        parts = path.split('!')
        parts = [p for p in parts if p]

        if len(parts) == 1:
            root_fields.append((field, ptype, value, path))
        else:
            parent_parts = parts[:-1]
            parent_path = '!' + '!'.join(parent_parts)
            if parent_path not in message_children:
                message_children[parent_path] = []
            message_children[parent_path].append((field, ptype, value, path))

    def serialize_field(field: int, ptype: str, value: Any, path: str) -> str:
        if ptype == 'm':
            children = message_children.get(path, [])
            child_count = count_all_fields(children, message_children)
            child_str = ''.join(serialize_field(f, t, v, p) for f, t, v, p in children)
            return f"!{field}m{child_count}{child_str}"
        else:
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
        count = 0
        for f, t, v, p in fields:
            count += 1
            if t == 'm':
                nested = children_map.get(p, [])
                count += count_all_fields(nested, children_map)
        return count

    result = ''.join(serialize_field(f, t, v, p) for f, t, v, p in root_fields)
    return result


def build_url_with_params(base_url: str, url_params: Dict[str, str], pb_string: str) -> str:
    """Build the full URL with modified parameters."""
    match = re.match(r'(https?://[^/]+)([^?]*)', base_url)
    if match:
        base = match.group(1) + match.group(2)
    else:
        base = base_url.split('?')[0]

    all_params = dict(url_params)
    all_params['pb'] = pb_string

    query = urlencode(all_params, safe='!@#$%^&*()_+-=[]{}|;:,.<>?')
    return f"{base}?{query}"


def build_reviews_pb_string(hex_id: str, limit: int = 10, pagination_token: str = None) -> str:
    """Build pb parameter for reviews endpoint (/maps/rpc/listugcposts).

    Uses exact format from working curl example.

    Args:
        hex_id: Hex format ID (0x...:0x...) for the place - NOT URL-encoded
        limit: Number of reviews to fetch (default 10)
        pagination_token: Token for fetching next page (from previous response)

    Returns:
        pb parameter string (will be URL-encoded when placed in URL)
    """
    # hex_id should be raw, not URL-encoded
    hex_id_raw = hex_id if hex_id else ""
    token = pagination_token or ""

    # Exact format from working curl
    return (
        f"!1m6!1s{hex_id_raw}"
        f"!6m4!4m1!1e1!4m1!1e3"
        f"!2m2!1i{limit}!2s{token}"
        f"!5m2!1s!7e81"
        f"!8m9!2b1!3b1!5b1!7b1!12m4!1b1!2b1!4m1!1e1"
        f"!11m4!1e3!2e1!6m1!1i2"
        f"!13m1!1e1"
    )


def build_place_pb_string(hex_id: str, name: str, lat: float, lng: float, ftid: str = None) -> str:
    """Build pb parameter for place details request.

    Uses the exact working pb format from browser inspection.
    The hex_id (format 0x...:0x...) is required for this endpoint to work.

    IMPORTANT: hex_id and ftid should NOT be URL-encoded within the pb string.
    Name should use + for spaces (not %20).
    """
    # hex_id should be raw (e.g., 0x89c259a8669c0f0d:0x25d4109319b4f5a0)
    hex_id_raw = hex_id if hex_id else ""

    # Name: replace spaces with + (not %20)
    name_plus = name.replace(' ', '+') if name else ""

    # ftid should be raw (e.g., /g/1vs5xm_3)
    ftid_raw = ftid if ftid else ""
    ftid_part = f"!15m2!1m1!4s{ftid_raw}" if ftid_raw else ""

    # Exact working pb format from curl example
    return (
        f"!1m17"
        f"!1s{hex_id_raw}"
        f"!2s{name_plus}"
        f"!3m8!1m3!1d3022.7!2d{lng}!3d{lat}!3m2!1i1024!2i768!4f13.1"
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


async def fetch_and_parse_json(url: str, headers: dict, cookies: dict = None) -> Any:
    """Fetch URL and parse the JSON response. Uses proxy if configured."""
    proxy_url = get_proxy_url()

    async with httpx.AsyncClient(
        timeout=30.0,
        follow_redirects=True,
        proxy=proxy_url,
    ) as client:
        response = await client.get(url, headers=headers, cookies=cookies)
        response_text = response.text

        if not response_text:
            return []

        if response_text.startswith(")]}'"):
            response_text = response_text[4:].strip()

        if not response_text:
            return []

        # Find and parse JSON array
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
                        return json.loads(response_text[start:i+1])
                    except json.JSONDecodeError:
                        continue

        # Try parsing the whole text if array extraction failed
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            return []


# API Endpoints
@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/api/decode")
async def decode_curl(input: CurlInput):
    """Decode a curl command and return structured parameters."""
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
    """Execute a search request and return businesses."""
    try:
        original = decode_google_maps_curl(request.original_curl)

        # Check if params were modified
        def values_equal(v1, v2):
            if v1 is None and v2 is None:
                return True
            if v1 is None or v2 is None:
                return False
            if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
                return abs(float(v1) - float(v2)) < 1e-9
            return str(v1) == str(v2)

        params_modified = False
        if request.pb_params:
            for param in request.pb_params:
                if not values_equal(param.get('value'), param.get('original_value')):
                    params_modified = True
                    break

        if params_modified:
            pb_string = rebuild_pb_string(request.pb_params)
            if not pb_string:
                pb_string = original.pb_raw
        else:
            pb_string = original.pb_raw

        # Merge URL params
        merged_url_params = dict(original.url_params)
        if request.url_params:
            merged_url_params.update(request.url_params)

        new_url = build_url_with_params(original.url, merged_url_params, pb_string)

        # Merge headers
        headers = dict(original.headers)
        if request.headers:
            headers.update(request.headers)
        if 'user-agent' not in {k.lower() for k in headers}:
            headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

        # Execute request
        data = await fetch_and_parse_json(new_url, headers)
        businesses = extract_businesses(data)

        return {
            "success": True,
            "request": {"url": new_url, "pb_string": pb_string},
            "response": {
                "status_code": 200,
                "business_count": len(businesses),
                "businesses": businesses,
            }
        }

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Request timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/place-details")
async def get_place_details(request: PlaceDetailsRequest):
    """Fetch detailed information about a place."""
    try:
        # hex_id (0x...:0x...) is required for this endpoint to work
        if not request.hex_id:
            return {
                "success": False,
                "place_id": request.place_id,
                "error": "hex_id required for place details",
                "details": {},
            }

        name = request.name or request.place_id
        lat = request.latitude or 40.7128
        lng = request.longitude or -74.0060

        pb_string = build_place_pb_string(request.hex_id, name, lat, lng, request.ftid)
        name_plus = name.replace(' ', '+')

        # URL-encode the pb string (! -> %21, : -> %3A, etc.)
        pb_encoded = quote(pb_string, safe='')

        url = f"https://www.google.com/maps/preview/place?authuser=0&hl=en&gl=us&q={name_plus}&pb={pb_encoded}"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': f'https://www.google.com/maps/place/{name_plus}/',
            'Origin': 'https://www.google.com',
        }

        # Auto-fetch cookies if not provided
        cookies = request.cookies or get_google_cookies(auto_fetch=True)

        data = await fetch_and_parse_json(url, headers, cookies)
        details = extract_place_details_from_place_response(data)

        # Note: Inline reviews extraction disabled - use /api/reviews endpoint instead
        # The place response structure doesn't contain proper reviews data

        result = {
            "success": True,
            "place_id": request.place_id,
            "details": details,
        }

        if request.include_raw:
            result["raw"] = data

        return result

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Request timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/reviews")
async def get_reviews(request: ReviewsRequest):
    """Fetch reviews for a place using dedicated reviews endpoint.

    Uses /maps/rpc/listugcposts which provides paginated reviews.
    """
    try:
        # hex_id (0x...:0x...) is required for this endpoint to work
        if not request.hex_id:
            return {
                "success": False,
                "place_id": request.place_id,
                "error": "hex_id required for reviews",
                "reviews": [],
            }

        pb_string = build_reviews_pb_string(
            request.hex_id,
            limit=request.limit or 10,
            pagination_token=request.pagination_token,
        )

        # URL-encode the pb string
        pb_encoded = quote(pb_string, safe='')

        url = f"https://www.google.com/maps/rpc/listugcposts?authuser=0&hl=en&gl=us&pb={pb_encoded}"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.google.com/',
            'x-maps-diversion-context-bin': 'CAE=',
        }

        # Auto-fetch cookies if not provided
        cookies = request.cookies or get_google_cookies(auto_fetch=True)

        data = await fetch_and_parse_json(url, headers, cookies)

        # DEBUG: Log what we got from Google
        print(f"DEBUG REVIEWS API: data type={type(data).__name__}, len={len(data) if isinstance(data, list) else 'N/A'}")
        if isinstance(data, list) and len(data) > 2:
            reviews_arr = data[2] if isinstance(data[2], list) else None
            print(f"DEBUG REVIEWS API: data[2] type={type(data[2]).__name__ if len(data) > 2 else 'N/A'}, len={len(reviews_arr) if reviews_arr else 0}")

        # Extract reviews from listugcposts response
        # Structure: data[2] = reviews array, data[1] = pagination token
        reviews = []
        next_page_token = None

        if isinstance(data, list):
            # Get pagination token
            if len(data) > 1 and isinstance(data[1], str):
                next_page_token = data[1]

            # Get reviews array
            reviews_array = data[2] if len(data) > 2 and isinstance(data[2], list) else []

            for review_entry in reviews_array:
                if not isinstance(review_entry, list) or len(review_entry) < 1:
                    continue

                review_data = review_entry[0] if isinstance(review_entry[0], list) else review_entry

                # Extract fields from review structure
                # [0] = review ID
                # [1][4][5][0] = author name
                # [1][4][5][1] = author photo URL
                # [1][6] = date
                # [2][0][0] = rating
                # [2][14][0][0] = review text

                def safe_get(obj, *indices):
                    try:
                        current = obj
                        for idx in indices:
                            if current is None:
                                return None
                            current = current[idx]
                        return current
                    except (IndexError, KeyError, TypeError):
                        return None

                review_id = safe_get(review_data, 0)
                author = safe_get(review_data, 1, 4, 5, 0)
                author_photo = safe_get(review_data, 1, 4, 5, 1)
                date = safe_get(review_data, 1, 6)
                rating = safe_get(review_data, 2, 0, 0)
                text = safe_get(review_data, 2, 15, 0, 0)

                if author or text:
                    reviews.append({
                        'review_id': review_id,
                        'author': author,
                        'author_photo': author_photo,
                        'rating': rating if isinstance(rating, int) and 1 <= rating <= 5 else None,
                        'date': date,
                        'text': text,
                    })

        return {
            "success": True,
            "place_id": request.place_id,
            "review_count": len(reviews),
            "reviews": reviews,
            "next_page_token": next_page_token,
        }

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Request timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the API server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
