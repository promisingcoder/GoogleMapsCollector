#!/usr/bin/env python
"""
Run the API Server

Starts the FastAPI server for Google Maps data extraction.

Usage:
    python run_server.py

The server runs on http://localhost:8000

Endpoints:
    GET  /api/health        - Health check
    POST /api/execute       - Execute search request
    POST /api/place-details - Get place details
    POST /api/reviews       - Get reviews
"""

import sys
import os
import shutil

# Clear any cached modules (both old and new)
for mod in list(sys.modules.keys()):
    if 'pb_decoder' in mod or 'gmaps_extractor' in mod:
        del sys.modules[mod]

# Clear __pycache__ directories
for cache_dir in [
    os.path.join(os.path.dirname(__file__), 'pb_decoder', '__pycache__'),
    os.path.join(os.path.dirname(__file__), 'gmaps_extractor', '__pycache__'),
]:
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)
        print(f"Cleared cache: {cache_dir}")

# Run the server
import uvicorn
uvicorn.run("gmaps_extractor.server:app", host="0.0.0.0", port=8000, reload=False)
