"""
Default configuration for Google Maps Business Extractor.

This module provides safe default values for pip-installed users who
don't have a custom config.py. All credentials use placeholders.
Configure via environment variables or GMapsExtractor() constructor args.

For repo-clone users: copy config.example.py to config.py and edit it.
For library users: use GMapsExtractor(proxy="...") or set GMAPS_PROXY_* env vars.
"""

import os
import time
import httpx

# Proxy Configuration
# Use environment variables or GMapsExtractor(proxy="...") to configure
_DIRECT_PROXY_HOST = ""
_DIRECT_PROXY_USER = ""
_DIRECT_PROXY_PASS = ""

# Use environment variables if set, otherwise fall back to direct settings
PROXY_HOST = os.environ.get("GMAPS_PROXY_HOST", _DIRECT_PROXY_HOST)
PROXY_USER = os.environ.get("GMAPS_PROXY_USER", _DIRECT_PROXY_USER)
PROXY_PASS = os.environ.get("GMAPS_PROXY_PASS", _DIRECT_PROXY_PASS)

def get_proxy_url():
    """Get proxy URL. Returns single URL string for httpx."""
    if PROXY_HOST and PROXY_USER and PROXY_PASS:
        return f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}"
    return None

# API Server
API_HOST = "0.0.0.0"
API_PORT = 8000
API_BASE_URL = f"http://localhost:{API_PORT}"

# Google Cookies (required for reviews endpoint)
# The SOCS cookie below is a consent cookie - it rarely needs updating.
# NID, AEC, and __Secure-BUCKET are auto-fetched by the system.
_DEFAULT_COOKIES = {
    '__Secure-BUCKET': 'CGA',
    'SOCS': 'CAISNQgEEitib3FfaWRlbnRpdHlmcm9udGVuZHVpc2VydmVyXzIwMjYwMTE4LjA5X3AwGgJlbiACGgYIgIu7ywY',
    'AEC': '',  # Auto-fetched
    'NID': '',  # Auto-fetched
}

# Cache for fetched cookies
_CACHED_COOKIES = None
_COOKIES_FETCH_TIME = 0
_COOKIES_TTL = 3600  # Refresh cookies every hour

# Search Parameters
DEFAULT_RESULTS_PER_PAGE = 400
DEFAULT_MAX_RADIUS = 5000
DEFAULT_VIEWPORT_DIST = 10000

# Rate Limiting (seconds)
DELAY_BETWEEN_CELLS = 0.05
DELAY_BETWEEN_PAGES = 0.1
DELAY_BETWEEN_DETAILS = 0.2
DELAY_BETWEEN_REVIEWS = 0.2

# Parallel Processing
DEFAULT_PARALLEL_WORKERS = 20
MAX_PARALLEL_WORKERS = 50

# Grid Configuration
CELL_SIZE_SMALL = 1000
CELL_SIZE_MEDIUM = 2000
CELL_SIZE_LARGE = 5000
CELL_SIZE_XLARGE = 50000
CELL_SIZE_XXLARGE = 100000

# Geographic Constants
METERS_PER_LAT_DEGREE = 111320

# Curl Template for Search Requests
SEARCH_CURL_TEMPLATE = '''curl 'https://www.google.com/search?tbm=map&authuser=0&hl=en&gl=us&q={query}&pb=!1s{query_encoded}!4m8!1m3!1d{viewport_dist}!2d{lng}!3d{lat}!3m2!1i1024!2i768!4f13.1!7i{results_count}!8i{offset}!10b1!12m50!1m5!18b1!30b1!31m1!1b1!34e1!2m4!5m1!6e2!20e3!39b1!6m23!49b1!63m0!66b1!74i{max_radius}!85b1!91b1!114b1!149b1!206b1!209b1!212b1!213b1!223b1!232b1!233b1!234b1!244b1!246b1!250b1!253b1!258b1!260b1!263b1!10b1!12b1!13b1!14b1!16b1!17m1!3e1!20m3!5e2!6b1!14b1!46m1!1b0!96b1!99b1' -H 'User-Agent: Mozilla/5.0' '''

# Output Schema
OUTPUT_SCHEMA = {
    "name": "string",
    "address": "string",
    "place_id": "string",
    "rating": "float",
    "review_count": "integer",
    "latitude": "float",
    "longitude": "float",
    "phone": "string",
    "website": "string",
    "category": "string",
    "categories": "list[string]",
    "hours": "dict",
    "reviews_data": "list[dict]",
}

# CSV Output Columns
CSV_COLUMNS = [
    "name",
    "address",
    "place_id",
    "hex_id",
    "ftid",
    "rating",
    "review_count",
    "latitude",
    "longitude",
    "phone",
    "website",
    "category",
    "categories",
    "hours",
    "found_in",
    "reviews_data",
]


def _encode_varint(value: int) -> bytes:
    """Encode integer as protobuf varint."""
    result = b''
    while value > 127:
        result += bytes([(value & 0x7F) | 0x80])
        value >>= 7
    result += bytes([value])
    return result


def generate_socs_cookie(date_str: str = None, language: str = 'en') -> str:
    """Generate a SOCS consent cookie (experimental)."""
    import base64
    from datetime import datetime

    if date_str is None:
        date_str = datetime.now().strftime('%Y%m%d')

    server_version = f'boq_identityfrontenduiserver_{date_str}.09_p0'

    inner = bytearray()
    inner.extend(b'\x08\x04')
    inner.extend(b'\x12')
    inner.append(len(server_version))
    inner.extend(server_version.encode())
    inner.extend(b'\x1a')
    inner.append(len(language))
    inner.extend(language.encode())
    inner.extend(b'\x20\x02')

    outer = bytearray()
    outer.extend(b'\x08\x02')
    outer.extend(b'\x12')
    outer.append(len(inner))
    outer.extend(inner)

    ts = int(time.time())
    ts_inner = b'\x08' + _encode_varint(ts)
    outer.extend(b'\x1a')
    outer.append(len(ts_inner))
    outer.extend(ts_inner)

    return base64.b64encode(bytes(outer)).decode().rstrip('=')


def fetch_fresh_cookies(verbose: bool = False) -> dict:
    """Fetch fresh cookies from Google by building a proper session."""
    global _CACHED_COOKIES, _COOKIES_FETCH_TIME

    if _CACHED_COOKIES and (time.time() - _COOKIES_FETCH_TIME) < _COOKIES_TTL:
        return _CACHED_COOKIES

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Upgrade-Insecure-Requests': '1',
    }

    try:
        proxy_url = get_proxy_url()
        client_kwargs = {'timeout': 30.0, 'follow_redirects': True}
        if proxy_url:
            client_kwargs['proxy'] = proxy_url

        with httpx.Client(**client_kwargs) as client:
            if verbose:
                print("[Cookie] Step 1: Visiting google.com...")
            client.get('https://www.google.com/', headers=headers)

            if verbose:
                print("[Cookie] Step 2: Visiting consent.google.com...")
            client.get('https://consent.google.com/', headers=headers)

            if verbose:
                print("[Cookie] Step 3: Visiting maps.google.com...")
            client.get('https://www.google.com/maps', headers=headers)

            cookies = {}
            for cookie in client.cookies.jar:
                cookies[cookie.name] = cookie.value

            if cookies.get('NID'):
                if 'SOCS' not in cookies and _DEFAULT_COOKIES.get('SOCS'):
                    cookies['SOCS'] = _DEFAULT_COOKIES['SOCS']
                    if verbose:
                        print("[Cookie] Added SOCS from defaults")

                if verbose:
                    print(f"[Cookie] Success! Got cookies: {list(cookies.keys())}")

                _CACHED_COOKIES = cookies
                _COOKIES_FETCH_TIME = time.time()
                return cookies
            else:
                if verbose:
                    print(f"[Cookie] Warning: NID not received.")
                return None

    except Exception as e:
        if verbose:
            print(f"[Cookie] Error: {e}")
        return None


def parse_cookie_string(cookie_string: str) -> dict:
    """Parse a cookie string from browser into a dictionary."""
    cookies = {}
    for pair in cookie_string.split(';'):
        pair = pair.strip()
        if '=' in pair:
            key, value = pair.split('=', 1)
            cookies[key.strip()] = value.strip()
    return cookies


def update_cookies_from_string(cookie_string: str) -> dict:
    """Update cached cookies from a browser cookie string."""
    global _CACHED_COOKIES, _COOKIES_FETCH_TIME

    cookies = parse_cookie_string(cookie_string)
    if cookies.get('NID'):
        _CACHED_COOKIES = cookies
        _COOKIES_FETCH_TIME = time.time()
        print(f"[Cookie] Updated cookies: {list(cookies.keys())}")
        return cookies
    else:
        print("[Cookie] Warning: NID cookie not found")
        return None


def get_google_cookies(auto_fetch: bool = True, verbose: bool = False):
    """Get Google cookies for reviews."""
    import json

    env_cookies = os.environ.get("GMAPS_COOKIES")
    if env_cookies:
        try:
            return json.loads(env_cookies)
        except json.JSONDecodeError:
            pass

    if _CACHED_COOKIES and (time.time() - _COOKIES_FETCH_TIME) < _COOKIES_TTL:
        return _CACHED_COOKIES

    if auto_fetch:
        cookies = fetch_fresh_cookies(verbose=verbose)
        if cookies:
            return cookies

    if _DEFAULT_COOKIES.get('NID'):
        return _DEFAULT_COOKIES

    return None
