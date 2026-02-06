"""
Configuration manager for library usage.

Provides a clean configuration interface that bridges to the existing
config.py module without modifying its structure. Cookie handling is
NOT duplicated here — the existing config.py system handles cookies
comprehensively (env vars, auto-fetch, caching).
"""

import os
import sys
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class ExtractorConfig:
    """Configuration for GMapsExtractor.

    For proxy: explicit arg > env vars (GMAPS_PROXY_HOST/USER/PASS) > config.py defaults.
    For cookies: left to the existing config.py system (auto-fetch, GMAPS_COOKIES env var, etc.)
    unless explicitly overridden via the cookies parameter.

    Args:
        proxy_url: Full proxy URL (e.g., "http://user:pass@host:port").
                   If None, falls back to GMAPS_PROXY_* env vars, then config.py defaults.
        cookies: Optional explicit cookie override. If None, the existing cookie
                 system handles everything (env var, auto-fetch, caching).
        default_workers: Default number of parallel workers for search.
        max_workers: Maximum allowed parallel workers.
        server_port: Port for the internal API server.
        delay_between_cells: Rate limiting between cell queries (seconds).
        delay_between_pages: Rate limiting between pagination requests (seconds).
        delay_between_details: Rate limiting between detail requests (seconds).
        delay_between_reviews: Rate limiting between review requests (seconds).
        results_per_page: Results per API request.
        max_radius: Search radius in meters.
        viewport_dist: Viewport distance for search.
        verbose: Whether to print progress output.
    """

    proxy_url: Optional[str] = None
    cookies: Optional[Dict[str, str]] = None
    default_workers: int = 20
    max_workers: int = 50
    server_port: int = 8000
    delay_between_cells: float = 0.05
    delay_between_pages: float = 0.1
    delay_between_details: float = 0.2
    delay_between_reviews: float = 0.2
    results_per_page: int = 400
    max_radius: int = 5000
    viewport_dist: int = 10000
    verbose: bool = True

    def __post_init__(self):
        """Resolve proxy from env vars if not explicitly set."""
        if self.proxy_url is None:
            host = os.environ.get("GMAPS_PROXY_HOST")
            user = os.environ.get("GMAPS_PROXY_USER")
            passwd = os.environ.get("GMAPS_PROXY_PASS")
            if host and user and passwd:
                self.proxy_url = f"http://{user}:{passwd}@{host}"

    def apply(self):
        """Apply this configuration to the existing config module.

        Bridges the new config API to the legacy module-level constants
        that internal modules import. Only called when GMapsExtractor is
        instantiated — direct config.py users are never affected.
        """
        from . import config

        # Proxy — only override if we have an explicit URL
        if self.proxy_url:
            from urllib.parse import urlparse
            parsed = urlparse(self.proxy_url)
            if parsed.hostname:
                port_str = f":{parsed.port}" if parsed.port else ""
                config.PROXY_HOST = f"{parsed.hostname}{port_str}"
                config.PROXY_USER = parsed.username or ""
                config.PROXY_PASS = parsed.password or ""

        # Cookies — only override if user explicitly passed them
        # Otherwise, the existing get_google_cookies() system handles everything
        if self.cookies is not None:
            import time
            config._CACHED_COOKIES = self.cookies
            config._COOKIES_FETCH_TIME = time.time()

        # Server
        config.API_PORT = self.server_port
        config.API_BASE_URL = f"http://localhost:{self.server_port}"

        # Workers
        config.DEFAULT_PARALLEL_WORKERS = self.default_workers
        config.MAX_PARALLEL_WORKERS = self.max_workers

        # Rate limiting
        config.DELAY_BETWEEN_CELLS = self.delay_between_cells
        config.DELAY_BETWEEN_PAGES = self.delay_between_pages
        config.DELAY_BETWEEN_DETAILS = self.delay_between_details
        config.DELAY_BETWEEN_REVIEWS = self.delay_between_reviews

        # Search params
        config.DEFAULT_RESULTS_PER_PAGE = self.results_per_page
        config.DEFAULT_MAX_RADIUS = self.max_radius
        config.DEFAULT_VIEWPORT_DIST = self.viewport_dist

        # Propagate to already-imported modules that used `from config import X`.
        # Python's `from module import name` binds the value at import time into
        # the importing module's namespace. If those modules were imported before
        # apply() ran, their local names still point to the old defaults. This
        # loop patches them so custom server_port, rate limits, etc. take effect.
        _CONFIG_ATTRS = (
            'API_BASE_URL', 'DEFAULT_RESULTS_PER_PAGE', 'DEFAULT_MAX_RADIUS',
            'DEFAULT_VIEWPORT_DIST', 'DELAY_BETWEEN_CELLS', 'DELAY_BETWEEN_PAGES',
            'DELAY_BETWEEN_DETAILS', 'DELAY_BETWEEN_REVIEWS',
            'DEFAULT_PARALLEL_WORKERS', 'MAX_PARALLEL_WORKERS',
        )
        _CONSUMER_MODULES = (
            'gmaps_extractor.extraction.search',
            'gmaps_extractor.extraction.collector',
            'gmaps_extractor.extraction.collector_v2',
            'gmaps_extractor.extraction.enrichment',
            'gmaps_extractor.geo.grid',
            'gmaps_extractor.geo.nominatim',
        )
        for mod_name in _CONSUMER_MODULES:
            mod = sys.modules.get(mod_name)
            if mod is None:
                continue
            for attr in _CONFIG_ATTRS:
                if hasattr(mod, attr):
                    setattr(mod, attr, getattr(config, attr))
