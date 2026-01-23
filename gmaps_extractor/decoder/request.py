"""
Google Maps Request Decoder

Combines curl parsing and pb decoding into a single interface.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from urllib.parse import unquote
import json

from .curl import CurlParser
from .pb import PbDecoder


@dataclass
class DecodedRequest:
    """Complete decoded Google Maps request"""
    # URL Components
    url: str = ""
    scheme: str = ""
    host: str = ""
    path: str = ""
    method: str = "GET"

    # URL Parameters (non-pb)
    url_params: Dict[str, str] = field(default_factory=dict)

    # PB Parameter (raw and decoded)
    pb_raw: str = ""
    pb_decoded: List[Dict] = field(default_factory=list)
    pb_flat: List[Dict] = field(default_factory=list)

    # Headers and Cookies
    headers: Dict[str, str] = field(default_factory=dict)
    cookies: Dict[str, str] = field(default_factory=dict)

    # Key extracted values
    search_query: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    viewport_distance: Optional[float] = None
    results_count: Optional[int] = None
    offset: Optional[int] = None
    max_radius: Optional[int] = None
    zoom_level: Optional[float] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'url': self.url,
            'scheme': self.scheme,
            'host': self.host,
            'path': self.path,
            'method': self.method,
            'url_params': self.url_params,
            'pb_raw': self.pb_raw,
            'pb_decoded': self.pb_decoded,
            'pb_flat': self.pb_flat,
            'headers': self.headers,
            'cookies': self.cookies,
            'extracted': {
                'search_query': self.search_query,
                'latitude': self.latitude,
                'longitude': self.longitude,
                'viewport_distance': self.viewport_distance,
                'results_count': self.results_count,
                'offset': self.offset,
                'max_radius': self.max_radius,
                'zoom_level': self.zoom_level,
            }
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


class GoogleMapsRequestDecoder:
    """Complete decoder for Google Maps requests"""

    def __init__(self):
        self.curl_parser = CurlParser()
        self.pb_decoder = PbDecoder()

    def decode_curl(self, curl_command: str) -> DecodedRequest:
        """
        Decode a complete curl command.

        Args:
            curl_command: Full curl command string

        Returns:
            DecodedRequest with all parsed components
        """
        result = DecodedRequest()

        # Parse curl command
        parsed = self.curl_parser.parse(curl_command)

        # Copy basic info
        result.url = parsed.url
        result.scheme = parsed.scheme
        result.host = parsed.host
        result.path = parsed.path
        result.method = parsed.method
        result.headers = parsed.headers
        result.cookies = parsed.cookies

        # Separate pb from other URL params
        for key, value in parsed.query_params.items():
            if key == 'pb':
                result.pb_raw = unquote(value)
            else:
                result.url_params[key] = value

        # Decode pb parameter
        if result.pb_raw:
            result.pb_decoded = self.pb_decoder.decode_to_dict(result.pb_raw)
            result.pb_flat = self.pb_decoder.decode_to_flat(result.pb_raw)
            self._extract_key_values(result)

        # Also check q parameter for search query
        if 'q' in result.url_params and not result.search_query:
            result.search_query = unquote(result.url_params['q'])

        return result

    def _extract_key_values(self, result: DecodedRequest):
        """Extract commonly needed values from decoded pb"""
        for entry in result.pb_flat:
            field_num = entry.get('field')
            field_type = entry.get('type')
            value = entry.get('value')
            path = entry.get('path', '')

            # Search query (!1s at root)
            if field_num == 1 and field_type == 's' and path == '!1s':
                result.search_query = value

            # Results count (!7i)
            elif field_num == 7 and field_type == 'i' and '!7i' in path and 'm' not in path.split('!7i')[0][-2:]:
                result.results_count = int(value) if value else None

            # Offset (!8i)
            elif field_num == 8 and field_type == 'i':
                result.offset = int(value) if value is not None else None

            # Coordinates and viewport (inside !4m)
            elif '!4m' in path:
                if '!1m' in path:
                    if field_num == 1 and field_type == 'd':
                        result.viewport_distance = float(value) if value else None
                    elif field_num == 2 and field_type == 'd':
                        result.longitude = float(value) if value else None
                    elif field_num == 3 and field_type == 'd':
                        result.latitude = float(value) if value else None
                elif field_num == 4 and field_type == 'f':
                    result.zoom_level = float(value) if value else None

            # Max radius (!74i inside !6m)
            elif field_num == 74 and field_type == 'i':
                result.max_radius = int(value) if value else None

    def decode_pb_only(self, pb_string: str) -> Dict:
        """Decode just a pb parameter string."""
        decoded = self.pb_decoder.decode_to_dict(pb_string)
        flat = self.pb_decoder.decode_to_flat(pb_string)

        return {
            'pb_raw': pb_string,
            'pb_decoded': decoded,
            'pb_flat': flat,
        }


def decode_google_maps_curl(curl_command: str) -> DecodedRequest:
    """
    Convenience function to decode a Google Maps curl command.

    Args:
        curl_command: Full curl command string

    Returns:
        DecodedRequest with all parsed components
    """
    decoder = GoogleMapsRequestDecoder()
    return decoder.decode_curl(curl_command)
