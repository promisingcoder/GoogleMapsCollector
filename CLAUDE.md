# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Google Maps Business Extractor - A data collection tool that reverse-engineers Google Maps' internal API to extract business information at scale using raw HTTP requests.

**Input:** Area name (e.g., "New York, USA") + Category (e.g., "lawyers")
**Output:** JSON + CSV files with all businesses matching the criteria

## Commands

### Collect Businesses
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
```

### Start API Server (required for collection)
```bash
python run_server.py
```
Server runs on http://localhost:8000

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Configuration
```bash
# Copy example config
cp gmaps_extractor/config.example.py gmaps_extractor/config.py

# Or use environment variables
export GMAPS_PROXY_HOST="host:port"
export GMAPS_PROXY_USER="username"
export GMAPS_PROXY_PASS="password"
export GMAPS_COOKIES='{"NID":"...","SOCS":"..."}'
```

## Architecture

```
gmaps_extractor/
├── __init__.py              # Package entry, exports collect_businesses()
├── cli.py                   # CLI argument parsing
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

collect.py                   # CLI entry point (V1)
collect_v2.py                # CLI entry point (V2 - recommended)
enrich_reviews_only.py       # Standalone reviews enrichment tool
run_server.py                # Starts the FastAPI server
```

## Data Flow

```
1. CLI Input (area, category)
       ↓
2. Nominatim API → Get area boundaries
       ↓
3. Generate grid cells covering area
   (or subdivide into named sub-areas, then grid each one)
       ↓
4. Parallel search across all cells:
   → Paginate through results (400 per page)
   → Adaptive rate limiting with exponential backoff
   → Deduplicate by place_id + hex_id
       ↓
5. Filter by coordinates (inside boundary + buffer)
       ↓
6. [Optional] Parallel enrichment:
   → Place details (hours, phone, website)
   → Reviews with pagination (listugcposts endpoint)
       ↓
7. Save to JSON + CSV (JSONL streaming in V2)
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
