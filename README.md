# Google Maps Business Extractor

Extract every business in any geographic area from Google Maps — no browser needed.

This tool reverse-engineers Google Maps' internal API (protobuf-encoded search endpoints) to collect business data at scale using raw HTTP requests. Point it at a city and a category, and it systematically covers the entire area using a grid-based search with automatic geographic subdivision via OpenStreetMap Nominatim.

**100K+ records/week capable** with parallel processing and proxy support.

## Features

- **Full area coverage** — Automatically divides any city, region, or country into a grid of searchable cells. No results missed.
- **Subdivision mode** — Breaks large areas into named sub-areas (boroughs, districts, neighborhoods) for even better coverage.
- **No browser required** — Pure HTTP requests against Google's internal endpoints. No Selenium, no Puppeteer, no headless Chrome.
- **Parallel processing** — Configurable worker pool (up to 50 concurrent requests) for fast extraction.
- **Resumable collection** — V2 collector saves checkpoints. If it crashes, run again and it picks up where it left off.
- **Parallel enrichment** — Fetch place details (hours, phone, website) and reviews concurrently, not one-by-one.
- **Adaptive rate limiting** — Exponential backoff with jitter. Automatically slows down on errors and speeds up on success.
- **Dual output** — JSON and CSV generated simultaneously. JSONL streaming for large datasets.
- **Smart deduplication** — Deduplicates by both `place_id` and `hex_id` across overlapping grid cells.
- **Auto cookie management** — Builds Google sessions automatically by visiting google.com -> consent.google.com -> maps.google.com to obtain required cookies.
- **Boundary filtering** — Removes results that fall outside the target area with configurable buffer distance.
- **Reviews with pagination** — Fetches up to hundreds of reviews per business using Google's `listugcposts` endpoint.

## Installation

```bash
git clone https://github.com/promisingcoder/GoogleMapsCollector.git
cd GoogleMapsCollector

pip install -r requirements.txt

# Setup configuration
cp gmaps_extractor/config.example.py gmaps_extractor/config.py
# Edit config.py with your proxy credentials (or use environment variables)
```

### Requirements

- Python 3.8+
- A residential/sticky proxy (required — Google blocks datacenter IPs)

## Quick Start

### 1. Start the API Server

```bash
python run_server.py
```

The server runs on `http://localhost:8000` and handles all communication with Google's endpoints.

### 2. Collect Businesses

```bash
# Basic collection
python collect.py "New York, USA" "lawyers"

# With place details and reviews
python collect.py "Paris, France" "restaurants" --enrich --reviews --reviews-limit 20

# Subdivision mode for large areas (searches each neighborhood separately)
python collect.py "London, UK" "dentists" --subdivide

# Custom parallelism and output
python collect.py "Tokyo, Japan" "hotels" --parallel 30 -o my_output.json
```

### 3. Enhanced Collector (V2) — Recommended for Large Jobs

```bash
# Resumable collection with parallel enrichment
python collect_v2.py "Manhattan, New York" "lawyers" --enrich --reviews -l 100

# Resume an interrupted collection
python collect_v2.py "Manhattan, New York" "lawyers" --resume

# Full control
python collect_v2.py "Los Angeles, CA" "restaurants" \
  --enrich --reviews -l 50 \
  --workers 30 --enrich-workers 10 \
  --checkpoint 100 --subdivide
```

## CLI Reference

### collect.py

| Flag | Default | Description |
|------|---------|-------------|
| `area` | required | Area to search (e.g., `"New York, USA"`) |
| `category` | required | Business category (e.g., `"lawyers"`) |
| `--enrich` | off | Fetch detailed place info (hours, phone, website, photos) |
| `--reviews` | off | Fetch reviews for each business |
| `--reviews-limit N` | 5 | Max reviews per business |
| `-p, --parallel N` | 20 | Number of parallel search workers (max 50) |
| `--subdivide` | off | Use named sub-areas for better coverage |
| `-b, --buffer N` | 5.0 | Boundary filter buffer in km |
| `-o, --output PATH` | auto | JSON output file path |
| `--csv PATH` | auto | CSV output file path |
| `--no-csv` | off | Disable CSV output |
| `-q, --quiet` | off | Suppress progress output |

### collect_v2.py (Enhanced)

All flags from `collect.py` plus:

| Flag | Default | Description |
|------|---------|-------------|
| `-w, --workers N` | 20 | Parallel workers for cell queries |
| `--enrich-workers N` | 5 | Parallel workers for enrichment |
| `-c, --checkpoint N` | 100 | Save checkpoint every N businesses |
| `--resume` | on | Resume from checkpoint if available |
| `--no-resume` | off | Start fresh, ignore existing checkpoint |

## Configuration

### Option 1: Environment Variables (Recommended)

```bash
export GMAPS_PROXY_HOST="your-proxy-host:port"
export GMAPS_PROXY_USER="your-username"
export GMAPS_PROXY_PASS="your-password"

# Optional: provide Google cookies as JSON
export GMAPS_COOKIES='{"NID":"...","SOCS":"...","AEC":"..."}'
```

### Option 2: Config File

Edit `gmaps_extractor/config.py` (copied from `config.example.py`):

```python
_DIRECT_PROXY_HOST = "your-proxy-host:port"
_DIRECT_PROXY_USER = "username"
_DIRECT_PROXY_PASS = "password_country-us_session-XXX_lifetime-30m_streaming-1"
```

### Proxy Requirements

- **Sticky session proxy** with 30+ minute lifetime recommended
- Residential proxies work best (Google blocks datacenter IPs)
- The `_lifetime-30m` parameter in the proxy password configures session stickiness (provider-specific)

### Cookie Management

The system handles cookies automatically:

- **NID, AEC, __Secure-BUCKET** — Auto-fetched by visiting Google pages in sequence
- **SOCS** — Consent cookie provided in defaults, rarely needs updating
- Cookies are cached for 1 hour and refreshed automatically
- You can also provide cookies manually via the `GMAPS_COOKIES` environment variable or `update_cookies_from_string()` function

## Output Format

Both JSON and CSV files are generated by default in the `output/` directory.

### JSON Structure

```json
{
  "metadata": {
    "area": "New York, USA",
    "category": "lawyers",
    "boundary": { "name": "New York", "north": 40.91, "south": 40.49, "east": -73.70, "west": -74.25 },
    "search_mode": "grid",
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
      "name": "Smith & Associates Law Firm",
      "address": "123 Broadway, New York, NY 10006",
      "place_id": "ChIJ...",
      "hex_id": "0x89c259a8669c0f0d:0x25d4109319b4f5a0",
      "ftid": "/g/11b5wlq0vc",
      "rating": 4.5,
      "review_count": 123,
      "latitude": 40.7128,
      "longitude": -74.0060,
      "phone": "+1 212-555-0123",
      "website": "https://example.com",
      "category": "Lawyer",
      "categories": ["Lawyer", "Legal Services"],
      "found_in": "Manhattan, New York",
      "hours": {
        "monday": "9:00 AM - 5:00 PM",
        "tuesday": "9:00 AM - 5:00 PM"
      },
      "reviews_data": [
        {
          "review_id": "...",
          "author": "John Smith",
          "author_photo": "https://...",
          "rating": 5,
          "text": "Excellent service!",
          "date": "2 months ago"
        }
      ]
    }
  ]
}
```

### CSV Columns

`name, address, place_id, hex_id, ftid, rating, review_count, latitude, longitude, phone, website, category, categories, hours, found_in, reviews_data`

## API Endpoints

The FastAPI server exposes these endpoints on `http://localhost:8000`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/decode` | POST | Decode a curl command into structured parameters |
| `/api/execute` | POST | Execute a search query, return businesses |
| `/api/place-details` | POST | Fetch place details (hours, phone, photos) |
| `/api/reviews` | POST | Fetch paginated reviews for a place |

## How It Works

```
1. Input: area name + category
       |
2. Nominatim API --> get geographic boundaries
       |
3. Generate grid cells covering the entire area
   (or subdivide into named sub-areas, then grid each one)
       |
4. Parallel search: query each cell via Google's internal search endpoint
   - Paginate through all results per cell (400 per page)
   - Adaptive rate limiting with exponential backoff
       |
5. Deduplicate by place_id + hex_id across overlapping cells
       |
6. Filter: remove results outside the target boundary
       |
7. [Optional] Parallel enrichment:
   - Place details (hours, phone, website, photos)
   - Reviews with pagination (via listugcposts endpoint)
       |
8. Export to JSON + CSV (with JSONL streaming in V2)
```

### Google Maps PB Parameter Format

The tool constructs requests using Google's internal `pb` (protobuf) URL parameter format:

| Pattern | Type | Example Use |
|---------|------|-------------|
| `!1s` | string | Search query |
| `!2d` / `!3d` | double | Longitude / Latitude |
| `!7i` | integer | Results per page |
| `!8i` | integer | Pagination offset |
| `!74i` | integer | Max search radius (meters) |
| `!Nm` | message | N nested fields follow |

## Architecture

```
gmaps_extractor/
├── __init__.py              # Package entry, exports collect_businesses()
├── cli.py                   # CLI argument parsing
├── config.py                # Proxy, cookies, rate limits, search parameters
├── server.py                # FastAPI server (all Google communication goes through here)
├── decoder/
│   ├── pb.py                # Decodes Google's !field_type_value protobuf format
│   ├── curl.py              # Parses curl commands into structured data
│   └── request.py           # Combined request decoder
├── parsers/
│   ├── business.py          # Extracts businesses from search response arrays
│   ├── place.py             # Extracts place details (hours, phone, etc.)
│   └── reviews.py           # Extracts reviews from place responses
├── geo/
│   ├── grid.py              # Grid cell generation and boundary math
│   └── nominatim.py         # OpenStreetMap Nominatim API for boundaries + sub-areas
└── extraction/
    ├── search.py            # Builds and executes search queries
    ├── enrichment.py        # Fetches details + reviews per business
    ├── collector.py          # V1 orchestrator (parallel grid search)
    └── collector_v2.py       # V2 orchestrator (resumable, adaptive, parallel enrichment)

collect.py                   # CLI entry point (V1)
collect_v2.py                # CLI entry point (V2 - recommended)
enrich_reviews_only.py       # Standalone tool to add reviews to existing collections
run_server.py                # Starts the FastAPI server
```

## License

MIT License - See [LICENSE](LICENSE) for details.

## Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) — API server
- [httpx](https://www.python-httpx.org/) — HTTP client
- [OpenStreetMap Nominatim](https://nominatim.org/) — Geocoding and boundary detection
