"""
Curl Command Parser

Parses curl commands to extract URL, headers, cookies, and other components.
"""

import re
from urllib.parse import urlparse, parse_qs, unquote
from typing import Dict, Optional
from dataclasses import dataclass, field


@dataclass
class ParsedCurl:
    """Represents a parsed curl command"""
    url: str = ""
    method: str = "GET"
    headers: Dict[str, str] = field(default_factory=dict)
    cookies: Dict[str, str] = field(default_factory=dict)
    data: Optional[str] = None
    query_params: Dict[str, str] = field(default_factory=dict)

    # Parsed URL components
    scheme: str = ""
    host: str = ""
    path: str = ""


class CurlParser:
    """Parser for curl commands"""

    def __init__(self):
        self.header_pattern = re.compile(r"^-H\s*['\"]?(.+?)['\"]?$")
        self.cookie_pattern = re.compile(r"^-b\s*['\"]?(.+?)['\"]?$")
        self.data_pattern = re.compile(r"^(?:-d|--data|--data-raw)\s*['\"]?(.+?)['\"]?$")

    def parse(self, curl_command: str) -> ParsedCurl:
        """
        Parse a curl command string into its components.

        Args:
            curl_command: The full curl command as a string

        Returns:
            ParsedCurl object with all extracted components
        """
        result = ParsedCurl()

        # Clean up the command
        curl_command = self._clean_command(curl_command)

        # Extract URL
        result.url = self._extract_url(curl_command)

        # Parse URL components
        if result.url:
            parsed_url = urlparse(result.url)
            result.scheme = parsed_url.scheme
            result.host = parsed_url.netloc
            result.path = parsed_url.path
            result.query_params = self._parse_query_params(parsed_url.query)

        # Extract headers, cookies, method, data
        result.headers = self._extract_headers(curl_command)
        result.cookies = self._extract_cookies(curl_command)
        result.method = self._extract_method(curl_command)
        result.data = self._extract_data(curl_command)

        return result

    def _clean_command(self, command: str) -> str:
        """Clean up curl command - handle line continuations and extra whitespace"""
        command = re.sub(r'\\\s*\n\s*', ' ', command)
        command = re.sub(r'\s+', ' ', command)
        return command.strip()

    def _extract_url(self, command: str) -> str:
        """Extract the URL from the curl command"""
        patterns = [
            r"curl\s+['\"]([^'\"]+)['\"]",
            r"curl\s+(\S+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, command)
            if match:
                url = match.group(1)
                if url.startswith('http'):
                    return url

        url_match = re.search(r"(https?://[^\s'\"]+)", command)
        if url_match:
            return url_match.group(1)

        return ""

    def _parse_query_params(self, query_string: str) -> Dict[str, str]:
        """Parse query string into dictionary"""
        if not query_string:
            return {}

        params = {}
        parsed = parse_qs(query_string, keep_blank_values=True)

        for key, values in parsed.items():
            decoded_key = unquote(key)
            decoded_value = unquote(values[0]) if values else ""
            params[decoded_key] = decoded_value

        return params

    def _extract_headers(self, command: str) -> Dict[str, str]:
        """Extract all headers from -H flags"""
        headers = {}
        patterns = [
            r"-H\s+['\"]([^'\"]+)['\"]",
            r"-H\s+([^\s]+)",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, command)
            for match in matches:
                if ':' in match:
                    key, value = match.split(':', 1)
                    headers[key.strip().lower()] = value.strip()

        return headers

    def _extract_cookies(self, command: str) -> Dict[str, str]:
        """Extract cookies from -b flag"""
        cookies = {}
        patterns = [
            r"-b\s+['\"]([^'\"]+)['\"]",
            r"--cookie\s+['\"]([^'\"]+)['\"]",
        ]

        for pattern in patterns:
            match = re.search(pattern, command)
            if match:
                cookie_string = match.group(1)
                for cookie in cookie_string.split(';'):
                    cookie = cookie.strip()
                    if '=' in cookie:
                        name, value = cookie.split('=', 1)
                        cookies[name.strip()] = value.strip()
                break

        return cookies

    def _extract_method(self, command: str) -> str:
        """Extract HTTP method from -X flag"""
        match = re.search(r"-X\s+['\"]?(\w+)['\"]?", command)
        if match:
            return match.group(1).upper()

        if re.search(r"(?:-d|--data|--data-raw)", command):
            return "POST"

        return "GET"

    def _extract_data(self, command: str) -> Optional[str]:
        """Extract request body data from -d or --data flags"""
        patterns = [
            r"(?:-d|--data|--data-raw)\s+['\"]([^'\"]+)['\"]",
            r"(?:-d|--data|--data-raw)\s+(\S+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, command)
            if match:
                return match.group(1)

        return None


def parse_curl(curl_command: str) -> ParsedCurl:
    """Convenience function to parse a curl command."""
    parser = CurlParser()
    return parser.parse(curl_command)
