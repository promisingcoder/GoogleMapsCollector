"""
Google Maps Business Extractor

A Python library for extracting business information from Google Maps at scale.

Quick start (library usage):
    from gmaps_extractor import GMapsExtractor

    with GMapsExtractor(proxy="http://user:pass@host:port") as extractor:
        result = extractor.collect("New York, USA", "lawyers")
        for biz in result:
            print(biz["name"], biz["address"])

Or use the lower-level functions directly (requires server running separately):
    from gmaps_extractor import collect_businesses
    businesses = collect_businesses("New York, USA", "lawyers")
"""

# Config shim: if config.py doesn't exist (pip-installed without repo clone),
# fall back to _config_defaults.py which has safe placeholder values.
# This must run before any other imports since all submodules import from config.
import sys as _sys
try:
    from . import config as _config_test  # noqa: F401
except ImportError:
    from . import _config_defaults
    _sys.modules[__name__ + '.config'] = _config_defaults

# GMapsExtractor and CollectionResult are the primary library API.
# Imported eagerly since extractor.py has lightweight top-level deps.
from .extractor import GMapsExtractor, CollectionResult
from .config import OUTPUT_SCHEMA

__version__ = "1.0.0"
__all__ = [
    "GMapsExtractor",
    "CollectionResult",
    "collect_businesses",
    "collect_businesses_v2",
    "OUTPUT_SCHEMA",
]


def __getattr__(name):
    """Lazy imports for heavyweight collector functions.

    collect_businesses and collect_businesses_v2 trigger the full import chain
    (httpx, FastAPI, collectors, parsers, geo modules). Deferring them avoids
    ~200-400ms of import overhead for users who only use GMapsExtractor.

    This also fixes a config race condition: the collector modules bind config
    values at import time via `from ..config import X`. By deferring their
    import until after GMapsExtractor.__init__() calls config.apply(), the
    correct (user-configured) values are captured instead of defaults.
    """
    if name == "collect_businesses":
        from .extraction.collector import collect_businesses
        return collect_businesses
    if name == "collect_businesses_v2":
        from .extraction.collector_v2 import collect_businesses_v2
        return collect_businesses_v2
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
