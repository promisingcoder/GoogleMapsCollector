#!/usr/bin/env python
"""
Google Maps Business Extractor - CLI

Collect all businesses of a category in a geographic area.

Usage:
    python collect.py "New York, USA" "lawyers"
    python collect.py "Paris, France" "restaurants" --enrich --reviews
    python collect.py "New York, USA" "lawyers" --subdivide  # More results via sub-areas

Requires the API server to be running:
    python run_server.py
"""

import sys
from gmaps_extractor.cli import main

if __name__ == "__main__":
    sys.exit(main())
