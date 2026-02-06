# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Google Maps Business Extractor - A pip-installable Python library and CLI tool that reverse-engineers Google Maps' internal API to extract business information at scale using raw HTTP requests.

**Input:** Area name (e.g., "New York, USA") + Category (e.g., "lawyers")
**Output:** JSON + CSV files with all businesses matching the criteria

## Installation

```bash
# From PyPI
pip install gmaps-extractor

# From source (editable)
pip install -e .

# Legacy (still works)
pip install -r requirements.txt
```

## Commands

### Library Usage (Recommended)
```python
from gmaps_extractor import GMapsExtractor

# Server auto-starts in background — no need for run_server.py
with GMapsExtractor(proxy="http://user:pass@host:port") as extractor:
    result = extractor.collect("New York, USA", "lawyers", enrich=True)
    result = extractor.collect_v2("Paris, France", "restaurants", reviews=True, reviews_limit=50)
```

### Console Scripts (after pip install)
```bash
gmaps-collect "New York, USA" "lawyers"
gmaps-collect-v2 "Manhattan, New York" "lawyers" --enrich --reviews -l 100
gmaps-enrich-reviews output/lawyers_in_manhattan.json -l 50
gmaps-server  # start API server manually (only needed for CLI or low-level functions)
```

### Legacy CLI (still works from repo root)
```bash
# Basic collection (V1)
python collect.py "New York, USA" "lawyers"

# With enrichment (details + reviews)
python collect.py "Paris, France" "restaurants" --enrich --reviews --reviews-limit 20

# Subdivision mode for better coverage
python collect.py "London, UK" "dentists" --subdivide

# Enhanced collector (V2) — resumable, parallel enrichment
python collect_v2.py "Manhattan, New York" "lawyers" --enrich --reviews -l 100

# Resume interrupted V2 collection
python collect_v2.py "Manhattan, New York" "lawyers" --resume

# Add reviews to existing collection
python enrich_reviews_only.py output/lawyers_in_manhattan.json -l 50

# Start API server (required for legacy CLI and low-level functions)
python run_server.py
```

### Configuration
```bash
# Environment variables (works for both library and CLI)
export GMAPS_PROXY_HOST="host:port"
export GMAPS_PROXY_USER="username"
export GMAPS_PROXY_PASS="password"
export GMAPS_COOKIES='{"NID":"...","SOCS":"..."}'

# Config file (legacy, for CLI usage)
cp gmaps_extractor/config.example.py gmaps_extractor/config.py
```

## Library API

### GMapsExtractor class (gmaps_extractor/extractor.py)
- Main public API: `GMapsExtractor` with `collect()` and `collect_v2()` methods
- Auto-starts FastAPI server in a background daemon thread
- Context manager recommended (`with` statement) for clean server shutdown
- Only one instance should be active at a time (shared module-level config)
- Constructor args: `proxy`, `cookies`, `workers`, `server_port`, `auto_start_server`, `verbose`
- Config priority: constructor args > env vars > config.py defaults

### CollectionResult class (gmaps_extractor/extractor.py)
- Wrapper around result dict with `.businesses`, `.metadata`, `.statistics`
- Supports `len()`, iteration, indexing, slicing
- `to_dict()` returns the full result as a plain dict

### Exception Hierarchy (gmaps_extractor/exceptions.py)
- `GMapsExtractorError` — base exception
- `ServerError` — server start/connection failure
- `BoundaryError` — Nominatim area resolution failure
- `ConfigurationError` — invalid config
- `RateLimitError` — retry capacity exceeded
- `AuthenticationError` — proxy/cookie auth failure

### Low-Level Functions (still available)
- `collect_businesses()` — V1 collector, requires server running separately
- `collect_businesses_v2()` — V2 collector, requires server running separately
- These are lazy-imported via `__getattr__` in `__init__.py` to avoid import overhead

## Architecture

```
gmaps_extractor/
├── __init__.py              # Package entry, exports GMapsExtractor + lazy collect functions
├── extractor.py             # GMapsExtractor class and CollectionResult wrapper
├── config_manager.py        # ExtractorConfig dataclass, bridges constructor args to config.py
├── exceptions.py            # Custom exception hierarchy (GMapsExtractorError, etc.)
├── _config_defaults.py      # Safe fallback config for pip-only installs (no config.py)
├── cli.py                   # CLI argument parsing (V1, entry point for gmaps-collect)
├── cli_v2.py                # CLI argument parsing (V2, entry point for gmaps-collect-v2)
├── cli_enrich.py            # CLI for reviews-only enrichment (gmaps-enrich-reviews)
├── config.py                # Proxy, cookies, rate limits, search params (gitignored)
├── config.example.py        # Template config with placeholders
├── server.py                # FastAPI server (all Google communication)
├── decoder/
│   ├── pb.py                # Decodes Google's !field_type_value protobuf format
│   ├── curl.py              # Parses curl commands
│   └── request.py           # Combined request decoder
├── parsers/
│   ├── business.py          # Extracts businesses from search response arrays
│   ├── place.py             # Extracts place details (hours, phone, etc.)
│   └── reviews.py           # Extracts reviews from place responses
├── geo/
│   ├── grid.py              # Grid cell generation and boundary math
│   └── nominatim.py         # OpenStreetMap Nominatim API (boundaries + sub-areas)
└── extraction/
    ├── search.py            # Builds and executes search queries
    ├── enrichment.py        # Fetches details + reviews per business
    ├── collector.py          # V1 orchestrator (parallel grid search)
    └── collector_v2.py       # V2 orchestrator (resumable, adaptive, parallel enrichment)

collect.py                   # Legacy CLI entry point (V1)
collect_v2.py                # Legacy CLI entry point (V2 - recommended)
enrich_reviews_only.py       # Standalone reviews enrichment tool
run_server.py                # Starts the FastAPI server
pyproject.toml               # Package metadata, dependencies, console script entry points
```

## Console Script Entry Points (pyproject.toml)

| Command | Module:Function |
|---------|-----------------|
| `gmaps-collect` | `gmaps_extractor.cli:main` |
| `gmaps-collect-v2` | `gmaps_extractor.cli_v2:main` |
| `gmaps-enrich-reviews` | `gmaps_extractor.cli_enrich:main` |
| `gmaps-server` | `gmaps_extractor.server:run_server` |

## Data Flow

```
1. CLI Input or GMapsExtractor.collect()/collect_v2() call
       ↓
2. [Library only] Auto-start FastAPI server in background thread
       ↓
3. Nominatim API → Get area boundaries
       ↓
4. Generate grid cells covering area
   (or subdivide into named sub-areas, then grid each one)
       ↓
5. Parallel search across all cells:
   → Paginate through results (400 per page)
   → Adaptive rate limiting with exponential backoff
   → Deduplicate by place_id + hex_id
       ↓
6. Filter by coordinates (inside boundary + buffer)
       ↓
7. [Optional] Parallel enrichment:
   → Place details (hours, phone, website)
   → Reviews with pagination (listugcposts endpoint)
       ↓
8. Return CollectionResult / Save to JSON + CSV (JSONL streaming in V2)
```

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | Health check |
| `/api/decode` | POST | Decode curl command into structured params |
| `/api/execute` | POST | Execute search, return businesses |
| `/api/place-details` | POST | Get place details (hours, photos) |
| `/api/reviews` | POST | Get paginated reviews for a place |

## Key Configuration (config.py)

| Setting | Value | Purpose |
|---------|-------|---------|
| `DEFAULT_RESULTS_PER_PAGE` | 400 | Results per API request |
| `DEFAULT_MAX_RADIUS` | 5000 | Search radius in meters |
| `DEFAULT_PARALLEL_WORKERS` | 20 | Concurrent cell queries |
| `MAX_PARALLEL_WORKERS` | 50 | Max allowed workers |
| `DELAY_BETWEEN_CELLS` | 0.05s | Rate limiting between cells |
| `DELAY_BETWEEN_PAGES` | 0.1s | Rate limiting between pages |

## Output Schema

```json
{
  "metadata": {
    "area": "New York, USA",
    "category": "lawyers",
    "boundary": { "name": "...", "north": ..., "south": ..., "east": ..., "west": ... },
    "search_mode": "grid | subdivision",
    "enrichment": { "details_fetched": true, "reviews_fetched": true, "reviews_limit": 20 }
  },
  "statistics": {
    "total_collected": 1234,
    "duplicates_removed": 89,
    "filtered_outside_boundary": 56,
    "search_time_seconds": 120.5,
    "total_time_seconds": 340.2
  },
  "businesses": [
    {
      "name": "Business Name",
      "address": "Full Address",
      "place_id": "ChIJ...",
      "hex_id": "0x...:0x...",
      "ftid": "/g/...",
      "rating": 4.5,
      "review_count": 123,
      "latitude": 40.7128,
      "longitude": -74.0060,
      "phone": "+1 212-555-0123",
      "website": "https://...",
      "category": "Lawyer",
      "categories": ["Lawyer", "Legal Services"],
      "found_in": "Manhattan, New York",
      "hours": { "monday": "9:00 AM - 5:00 PM" },
      "reviews_data": [{ "review_id": "...", "author": "...", "rating": 5, "text": "...", "date": "..." }]
    }
  ]
}
```

## CSV Columns

`name, address, place_id, hex_id, ftid, rating, review_count, latitude, longitude, phone, website, category, categories, hours, found_in, reviews_data`

## Google Maps PB Parameter Format

The `pb` URL parameter uses `!{field}{type}{value}` format:
- `!1s` - string (search query)
- `!7i` - integer (results count)
- `!8i` - integer (pagination offset)
- `!2d`/`!3d` - double (longitude/latitude)
- `!74i` - integer (max radius in meters)
- `!Nm` - message (N nested fields follow)

## V2 Collector Extras

- **Checkpoint/resume**: Saves state to `output/.checkpoint_*.json`, auto-resumes on restart
- **Adaptive rate limiter**: `RateLimiter` class with exponential backoff and jitter
- **Parallel enrichment**: Separate worker pool for details/reviews (default 5 workers)
- **JSONL streaming**: Writes businesses as they're collected, not just at the end
- **Retry queue**: Failed cells are retried with increased retries (5 attempts)
- **Dual dedup**: Deduplicates by both `place_id` and `hex_id`

## Config Resolution Order

When using `GMapsExtractor` (library API), configuration priority is:
1. Constructor arguments (highest priority)
2. Environment variables (`GMAPS_PROXY_HOST`, `GMAPS_PROXY_USER`, `GMAPS_PROXY_PASS`, `GMAPS_COOKIES`)
3. `config.py` defaults (lowest priority)

`config_manager.py` bridges constructor args to the legacy `config.py` module-level constants via `ExtractorConfig.apply()`. It also patches already-imported consumer modules that used `from ..config import X`.
