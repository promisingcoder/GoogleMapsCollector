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
- **Pip-installable** — Install from PyPI or source. Use as a Python library or from the command line.

## Installation

### From PyPI

```bash
pip install gmaps-extractor
```

### From Source

```bash
git clone https://github.com/promisingcoder/google_maps_business_extractor.git
cd google_maps_business_extractor

pip install -e .
```

### Requirements

- Python 3.9+
- A residential/sticky proxy (required — Google blocks datacenter IPs)

## Quick Start

### Python Library (Recommended)

The `GMapsExtractor` class is the main entry point for library usage. It automatically starts the internal API server in the background — no separate server process needed.

```python
from gmaps_extractor import GMapsExtractor

with GMapsExtractor(proxy="http://user:pass@host:port") as extractor:
    result = extractor.collect("New York, USA", "lawyers", enrich=True)
    print(f"Found {len(result)} businesses")
    for biz in result:
        print(biz["name"], biz["address"])
```

See the [Python Library API](#python-library-api) section below for full details.

### Command Line

```bash
# Start the API server (required for CLI usage)
gmaps-server
# Or: python run_server.py

# Basic collection
gmaps-collect "New York, USA" "lawyers"

# Enhanced collector (V2) with reviews
gmaps-collect-v2 "Paris, France" "restaurants" --enrich --reviews -l 50
```

See the [CLI Reference](#cli-reference) section below for all available flags.

## Python Library API

### GMapsExtractor

The `GMapsExtractor` class manages server lifecycle and configuration. Use it as a context manager for clean startup and shutdown.

```python
from gmaps_extractor import GMapsExtractor

# Proxy via constructor argument
with GMapsExtractor(proxy="http://user:pass@host:port") as extractor:
    result = extractor.collect("New York, USA", "lawyers", enrich=True)

# Proxy via environment variables (GMAPS_PROXY_HOST, GMAPS_PROXY_USER, GMAPS_PROXY_PASS)
with GMapsExtractor() as extractor:
    result = extractor.collect("London, UK", "dentists", subdivide=True)
```

#### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `proxy` | `str` | `None` | Proxy URL (e.g., `"http://user:pass@host:port"`). Falls back to `GMAPS_PROXY_*` env vars. |
| `cookies` | `dict` | `None` | Explicit cookie override. If `None`, cookies are handled automatically. |
| `workers` | `int` | `20` | Default number of parallel search workers. |
| `server_port` | `int` | `8000` | Port for the internal API server. |
| `auto_start_server` | `bool` | `True` | Whether to auto-start the API server in the background. |
| `verbose` | `bool` | `True` | Whether to print progress output. |

#### collect() — V1 Collector

```python
result = extractor.collect(
    "New York, USA",          # area (required)
    "lawyers",                # category (required)
    enrich=True,              # fetch place details (hours, phone, website)
    reviews=True,             # fetch reviews
    reviews_limit=20,         # max reviews per business
    workers=30,               # parallel search workers
    subdivide=True,           # use subdivision mode
    buffer_km=5.0,            # boundary filter buffer in km
    output_file="out.json",   # save JSON to file (None = auto-generate)
    output_csv="out.csv",     # save CSV to file (False = disable CSV)
    verbose=False,            # suppress progress output
)
```

#### collect_v2() — Enhanced Collector (Recommended for Large Jobs)

```python
result = extractor.collect_v2(
    "Paris, France",          # area (required)
    "restaurants",            # category (required)
    enrich=True,              # fetch place details
    reviews=True,             # fetch reviews
    reviews_limit=50,         # max reviews per business
    workers=30,               # parallel search workers
    enrichment_workers=10,    # parallel enrichment workers
    checkpoint_interval=100,  # save checkpoint every N businesses
    resume=True,              # resume from checkpoint if available
    subdivide=True,           # use subdivision mode
    buffer_km=5.0,            # boundary filter buffer in km
    output_file="out.json",   # save JSON to file
    output_csv="out.csv",     # save CSV to file
)
```

### CollectionResult

Both `collect()` and `collect_v2()` return a `CollectionResult` object that supports iteration, indexing, and length.

```python
result = extractor.collect("New York, USA", "lawyers")

# Length
print(f"Found {len(result)} businesses")

# Iteration
for biz in result:
    print(biz["name"], biz["rating"])

# Indexing
first = result[0]
last_five = result[-5:]

# Access structured data
print(result.metadata)     # {"area": "New York, USA", "category": "lawyers", ...}
print(result.statistics)   # {"total_collected": 1234, "duplicates_removed": 89, ...}
print(result.businesses)   # [{"name": "...", "address": "...", ...}, ...]

# Full dict (matches the JSON output structure)
data = result.to_dict()    # {"metadata": {...}, "statistics": {...}, "businesses": [...]}
```

### Exception Handling

All library exceptions inherit from `GMapsExtractorError`, so you can catch them broadly or handle specific cases.

```python
from gmaps_extractor import GMapsExtractor
from gmaps_extractor.exceptions import (
    GMapsExtractorError,   # base exception for all errors
    ServerError,           # API server failed to start or is unreachable
    BoundaryError,         # area boundaries could not be resolved via Nominatim
    ConfigurationError,    # invalid or incomplete configuration
    RateLimitError,        # rate-limiting exceeded retry capacity
    AuthenticationError,   # proxy or cookie authentication failed
)

try:
    with GMapsExtractor(proxy="http://user:pass@host:port") as extractor:
        result = extractor.collect("New York, USA", "lawyers")
except ServerError:
    print("Could not start the API server")
except BoundaryError:
    print("Could not resolve area boundaries")
except GMapsExtractorError as e:
    print(f"Extraction failed: {e}")
```

### Low-Level Functions

The lower-level `collect_businesses()` and `collect_businesses_v2()` functions are still available for advanced use. These require the API server to be running separately (via `gmaps-server` or `python run_server.py`).

```python
from gmaps_extractor import collect_businesses, collect_businesses_v2

# Requires server running on localhost:8000
businesses = collect_businesses("New York, USA", "lawyers", enrich=True)
```

### Important Notes

- **Proxy is required** for production use. Pass via the `proxy` constructor argument or set `GMAPS_PROXY_HOST`, `GMAPS_PROXY_USER`, and `GMAPS_PROXY_PASS` environment variables.
- **Cookies are handled automatically.** The system auto-fetches cookies from Google. You only need to provide them explicitly if the automatic flow fails.
- **One instance at a time.** Only one `GMapsExtractor` instance should be active at a time, since configuration is applied to shared module-level globals.
- **Use the context manager.** The `with` statement ensures the background server shuts down cleanly. Without it, call `extractor.shutdown()` manually when done.

## Console Scripts

After installing with `pip install gmaps-extractor`, the following commands are available globally:

| Command | Equivalent Script | Description |
|---------|-------------------|-------------|
| `gmaps-collect` | `python collect.py` | V1 collector |
| `gmaps-collect-v2` | `python collect_v2.py` | V2 enhanced collector (recommended) |
| `gmaps-enrich-reviews` | `python enrich_reviews_only.py` | Add reviews to existing collection |
| `gmaps-server` | `python run_server.py` | Start the API server |

All flags are identical to their script equivalents:

```bash
# These are equivalent
gmaps-collect-v2 "Manhattan, New York" "lawyers" --enrich --reviews -l 100
python collect_v2.py "Manhattan, New York" "lawyers" --enrich --reviews -l 100
```

## CLI Reference

### collect.py / gmaps-collect

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

### collect_v2.py / gmaps-collect-v2 (Enhanced)

All flags from `collect.py` plus:

| Flag | Default | Description |
|------|---------|-------------|
| `-w, --workers N` | 20 | Parallel workers for cell queries |
| `--enrich-workers N` | 5 | Parallel workers for enrichment |
| `-c, --checkpoint N` | 100 | Save checkpoint every N businesses |
| `--resume` | on | Resume from checkpoint if available |
| `--no-resume` | off | Start fresh, ignore existing checkpoint |

### CLI Quick Examples

```bash
# Start the server (required for CLI usage only — library API auto-starts it)
gmaps-server

# Basic collection
gmaps-collect "New York, USA" "lawyers"

# With place details and reviews
gmaps-collect "Paris, France" "restaurants" --enrich --reviews --reviews-limit 20

# Subdivision mode for large areas
gmaps-collect "London, UK" "dentists" --subdivide

# V2 with parallel enrichment and resumability
gmaps-collect-v2 "Manhattan, New York" "lawyers" --enrich --reviews -l 100

# Resume an interrupted V2 collection
gmaps-collect-v2 "Manhattan, New York" "lawyers" --resume

# Add reviews to an existing collection
gmaps-enrich-reviews output/lawyers_in_manhattan.json -l 50

# Full control
gmaps-collect-v2 "Los Angeles, CA" "restaurants" \
  --enrich --reviews -l 50 \
  --workers 30 --enrich-workers 10 \
  --checkpoint 100 --subdivide
```

## Configuration

### Option 1: Constructor Arguments (Library Only)

```python
with GMapsExtractor(
    proxy="http://user:pass@host:port",
    workers=30,
    server_port=9000,
    verbose=False,
) as extractor:
    result = extractor.collect("New York, USA", "lawyers")
```

### Option 2: Environment Variables (Recommended for CLI)

```bash
export GMAPS_PROXY_HOST="your-proxy-host:port"
export GMAPS_PROXY_USER="your-username"
export GMAPS_PROXY_PASS="your-password"

# Optional: provide Google cookies as JSON
export GMAPS_COOKIES='{"NID":"...","SOCS":"...","AEC":"..."}'
```

### Option 3: Config File

Edit `gmaps_extractor/config.py` (copied from `config.example.py`):

```python
_DIRECT_PROXY_HOST = "your-proxy-host:port"
_DIRECT_PROXY_USER = "username"
_DIRECT_PROXY_PASS = "password_country-us_session-XXX_lifetime-30m_streaming-1"
```

**Note:** When using the library API (`GMapsExtractor`), constructor arguments take highest priority, followed by environment variables, then `config.py` defaults. When using the CLI, environment variables and `config.py` are the configuration sources.

### Proxy Requirements

- **Sticky session proxy** with 30+ minute lifetime recommended
- Residential proxies work best (Google blocks datacenter IPs)
- The `_lifetime-30m` parameter in the proxy password configures session stickiness (provider-specific)

### Cookie Management

The system handles cookies automatically:

- **NID, AEC, __Secure-BUCKET** — Auto-fetched by visiting Google pages in sequence
- **SOCS** — Consent cookie provided in defaults, rarely needs updating
- Cookies are cached for 1 hour and refreshed automatically
- You can also provide cookies manually via the `GMAPS_COOKIES` environment variable or the `cookies` constructor argument

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

**Note:** When using the library API, the server is started automatically in the background. You only need to start it manually for CLI usage or direct API access.

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
├── __init__.py              # Package entry, exports GMapsExtractor + collect functions
├── extractor.py             # GMapsExtractor class and CollectionResult wrapper
├── config_manager.py        # ExtractorConfig dataclass, bridges to config.py
├── exceptions.py            # Custom exception hierarchy (GMapsExtractorError, etc.)
├── _config_defaults.py      # Safe fallback config for pip-only installs (no config.py)
├── cli.py                   # CLI argument parsing (V1)
├── cli_v2.py                # CLI argument parsing (V2)
├── cli_enrich.py            # CLI for reviews-only enrichment
├── config.py                # Proxy, cookies, rate limits, search parameters (gitignored)
├── config.example.py        # Template config with placeholders
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

collect.py                   # CLI entry point (V1) — still works standalone
collect_v2.py                # CLI entry point (V2) — still works standalone
enrich_reviews_only.py       # Standalone tool to add reviews to existing collections
run_server.py                # Starts the FastAPI server — still works standalone
pyproject.toml               # Package metadata, dependencies, console script entry points
```

## License

MIT License - See [LICENSE](LICENSE) for details.

## Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) — API server
- [httpx](https://www.python-httpx.org/) — HTTP client
- [OpenStreetMap Nominatim](https://nominatim.org/) — Geocoding and boundary detection
