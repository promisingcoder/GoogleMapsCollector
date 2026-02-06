"""
GMapsExtractor - High-level API for Google Maps business extraction.

Provides the main user-facing class for the library. Manages server
lifecycle, configuration, and exposes clean methods for collecting
and enriching business data.

Usage:
    from gmaps_extractor import GMapsExtractor

    with GMapsExtractor(proxy="http://user:pass@host:port") as extractor:
        result = extractor.collect("New York, USA", "lawyers", enrich=True)
        for biz in result:
            print(biz["name"], biz["address"])
"""

import socket
import threading
import time
from typing import Any, Dict, List, Optional, Union

from .config_manager import ExtractorConfig
from .exceptions import ServerError


class CollectionResult:
    """Result object returned by collect() and collect_v2().

    Attributes:
        businesses: List of business dictionaries.
        metadata: Dictionary with area, category, boundary, search mode info.
        statistics: Dictionary with counts, timing, and dedup info.
    """

    def __init__(self, data: Dict[str, Any]):
        self._data = data
        self.businesses: List[Dict] = data.get("businesses", [])
        self.metadata: Dict = data.get("metadata", {})
        self.statistics: Dict = data.get("statistics", {})

    def __len__(self):
        return len(self.businesses)

    def __iter__(self):
        return iter(self.businesses)

    def __getitem__(self, index):
        return self.businesses[index]

    def to_dict(self) -> Dict[str, Any]:
        """Return the full result as a plain dictionary."""
        return self._data

    def __repr__(self):
        count = len(self.businesses)
        area = self.metadata.get("area", "unknown")
        category = self.metadata.get("category", "unknown")
        return f"<CollectionResult: {count} businesses for '{category}' in '{area}'>"


class GMapsExtractor:
    """High-level interface for Google Maps business extraction.

    Manages server lifecycle, proxy configuration, and provides clean
    methods for collecting businesses.

    The server is auto-started in a background thread when needed. If a
    server is already running on the configured port, it is reused.

    Cookies are handled automatically by the existing system (auto-fetch,
    GMAPS_COOKIES env var, caching). You only need to pass cookies if you
    want to explicitly override them.

    Note: Only one GMapsExtractor instance should be active at a time.
    Configuration is applied to shared module-level globals.

    Args:
        proxy: Proxy URL string (e.g., "http://user:pass@host:port").
               Falls back to GMAPS_PROXY_* env vars, then config.py defaults.
        cookies: Optional explicit cookie override dict. If None, the existing
                 cookie system handles everything automatically.
        workers: Default number of parallel workers for search (default: 20).
        server_port: Port for the internal API server (default: 8000).
        auto_start_server: Whether to auto-start the server (default: True).
        verbose: Whether to print progress output (default: True).

    Example:
        with GMapsExtractor(proxy="http://user:pass@host:port") as ext:
            result = ext.collect("New York, USA", "lawyers")
            print(f"Found {len(result)} businesses")
    """

    def __init__(
        self,
        proxy: Optional[str] = None,
        cookies: Optional[Dict[str, str]] = None,
        workers: int = 20,
        server_port: int = 8000,
        auto_start_server: bool = True,
        verbose: bool = True,
    ):
        self._config = ExtractorConfig(
            proxy_url=proxy,
            cookies=cookies,
            default_workers=workers,
            server_port=server_port,
            verbose=verbose,
        )
        self._server_instance = None
        self._server_started = False
        self._auto_start = auto_start_server

        # Apply configuration to the global config module
        self._config.apply()

        if self._auto_start:
            self._ensure_server()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
        return False

    def __del__(self):
        self.shutdown()

    def _is_server_running(self) -> bool:
        """Check if the API server is already running on the configured port."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.settimeout(0.2)
                result = sock.connect_ex(("127.0.0.1", self._config.server_port))
                return result == 0
            finally:
                sock.close()
        except OSError:
            return False

    def _ensure_server(self):
        """Start the internal API server if not already running."""
        if self._is_server_running():
            self._server_started = True
            return

        # Start server in a background daemon thread
        from .server import app
        import uvicorn

        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=self._config.server_port,
            log_level="warning",
        )
        server = uvicorn.Server(config)
        self._server_instance = server

        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()

        # Wait for server to become ready (up to 5 seconds)
        for _ in range(50):
            if self._is_server_running():
                self._server_started = True
                return
            time.sleep(0.1)

        raise ServerError(
            f"Failed to start API server on port {self._config.server_port}"
        )

    def shutdown(self):
        """Shut down the managed API server if we started it."""
        if self._server_instance is not None:
            self._server_instance.should_exit = True
            self._server_instance = None

    def collect(
        self,
        area: str,
        category: str,
        *,
        buffer_km: float = 5.0,
        enrich: bool = False,
        reviews: bool = False,
        reviews_limit: int = 5,
        output_file: Optional[str] = None,
        output_csv: Optional[Union[str, bool]] = None,
        workers: Optional[int] = None,
        subdivide: bool = False,
        verbose: Optional[bool] = None,
    ) -> CollectionResult:
        """Collect businesses using the V1 collector.

        Args:
            area: Geographic area name (e.g., "New York, USA").
            category: Business category to search (e.g., "lawyers").
            buffer_km: Buffer in km for coordinate filtering.
            enrich: Whether to fetch detailed place information.
            reviews: Whether to fetch reviews.
            reviews_limit: Number of reviews per business.
            output_file: Path to save JSON results (None to auto-generate).
            output_csv: Path for CSV, True/None for auto-generate, False to disable.
            workers: Number of parallel workers (overrides constructor default).
            subdivide: Use subdivision mode for better coverage.
            verbose: Override constructor verbose setting.

        Returns:
            CollectionResult with businesses, metadata, and statistics.
        """
        from .extraction.collector import collect_businesses

        self._ensure_server()

        v = verbose if verbose is not None else self._config.verbose
        w = workers if workers is not None else self._config.default_workers

        csv_arg = output_csv
        if output_csv is False:
            csv_arg = False

        # V1 returns Dict[str, Dict] keyed by place_id
        businesses_dict = collect_businesses(
            area_name=area,
            category=category,
            buffer_km=buffer_km,
            enrich=enrich,
            enrich_reviews=reviews,
            reviews_limit=reviews_limit,
            output_file=output_file,
            output_csv=csv_arg,
            parallel_workers=w,
            subdivide=subdivide,
            verbose=v,
        )

        businesses_list = list(businesses_dict.values())
        return CollectionResult({
            "businesses": businesses_list,
            "metadata": {"area": area, "category": category},
            "statistics": {"total_collected": len(businesses_list)},
        })

    def collect_v2(
        self,
        area: str,
        category: str,
        *,
        buffer_km: float = 5.0,
        enrich: bool = False,
        reviews: bool = False,
        reviews_limit: int = 20,
        output_file: Optional[str] = None,
        output_csv: Optional[str] = None,
        workers: Optional[int] = None,
        enrichment_workers: int = 5,
        checkpoint_interval: int = 100,
        resume: bool = True,
        subdivide: bool = False,
        verbose: Optional[bool] = None,
    ) -> CollectionResult:
        """Collect businesses using the V2 enhanced collector.

        Includes checkpoint/resume, adaptive rate limiting, parallel enrichment,
        JSONL streaming, and retry queue.

        Args:
            area: Geographic area name (e.g., "New York, USA").
            category: Business category to search (e.g., "lawyers").
            buffer_km: Buffer in km for coordinate filtering.
            enrich: Whether to fetch detailed place information.
            reviews: Whether to fetch reviews.
            reviews_limit: Max reviews per business.
            output_file: Path to save JSON results.
            output_csv: Path for CSV results.
            workers: Number of parallel workers for cell queries.
            enrichment_workers: Number of parallel workers for enrichment.
            checkpoint_interval: Save checkpoint every N businesses.
            resume: Resume from checkpoint if available.
            subdivide: Use subdivision mode for better coverage.
            verbose: Override constructor verbose setting.

        Returns:
            CollectionResult with businesses, metadata, and statistics.
        """
        from .extraction.collector_v2 import collect_businesses_v2

        self._ensure_server()

        v = verbose if verbose is not None else self._config.verbose
        w = workers if workers is not None else self._config.default_workers

        # V2 returns dict with metadata, statistics, businesses keys
        result_dict = collect_businesses_v2(
            area_name=area,
            category=category,
            buffer_km=buffer_km,
            enrich=enrich,
            enrich_reviews=reviews,
            reviews_limit=reviews_limit,
            output_file=output_file,
            output_csv=output_csv,
            parallel_workers=w,
            enrichment_workers=enrichment_workers,
            checkpoint_interval=checkpoint_interval,
            resume=resume,
            subdivide=subdivide,
            verbose=v,
        )

        return CollectionResult(result_dict)
