"""
Google Maps Business Extractor

A data collection tool for extracting business information from Google Maps.

Usage:
    python collect.py "New York, USA" "lawyers"

Or as a module:
    from gmaps_extractor import collect_businesses
    businesses = collect_businesses("New York, USA", "lawyers")
"""

from .extraction import collect_businesses
from .config import OUTPUT_SCHEMA

__version__ = "1.0.0"
__all__ = ["collect_businesses", "OUTPUT_SCHEMA"]
