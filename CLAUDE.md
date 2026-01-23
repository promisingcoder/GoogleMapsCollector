# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Google Maps Business Extractor - A data collection tool that extracts business information from Google Maps for a given area and category.

**Input:** Area name (e.g., "New York, USA") + Category (e.g., "lawyers")
**Output:** JSON file with all businesses matching the criteria

## Commands

### Collect Businesses
```bash
# Basic collection
python collect.py "New York, USA" "lawyers"

# With enrichment (details + reviews)
python collect.py "Paris, France" "restaurants" --enrich --reviews

# All options
python collect.py "Area" "category" --enrich --reviews --reviews-limit 10 -o output.json
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

## Architecture

```
gmaps_extractor/
├── __init__.py          # Package entry point, exports collect_businesses()
├── cli.py               # Command-line interface
├── config.py            # Configuration constants
├── server.py            # FastAPI server with endpoints
├── decoder/
│   ├── pb.py            # Decodes Google's !field_type_value format
│   ├── curl.py          # Parses curl commands
│   └── request.py       # Combined request decoder
├── parsers/
│   ├── business.py      # Extracts business data from search response
│   ├── place.py         # Extracts place details
│   └── reviews.py       # Extracts reviews
├── geo/
│   ├── grid.py          # Grid cell generation
│   └── nominatim.py     # OpenStreetMap boundary API
└── extraction/
    ├── search.py        # Executes search queries
    ├── enrichment.py    # Fetches details/reviews
    └── collector.py     # Main orchestration
```

## Data Flow

```
1. CLI Input (area, category)
       ↓
2. Nominatim API → Get area boundaries
       ↓
3. Generate grid cells covering area
       ↓
4. For each cell:
   → Execute search with pagination
   → Deduplicate by place_id
       ↓
5. Filter by coordinates (inside boundary)
       ↓
6. [Optional] Enrich with details/reviews
       ↓
7. Save to JSON
```

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | Health check |
| `/api/execute` | POST | Execute search, return businesses |
| `/api/place-details` | POST | Get place details (hours, photos) |
| `/api/reviews` | POST | Get reviews for a place |

## Key Configuration (config.py)

| Setting | Value | Purpose |
|---------|-------|---------|
| `DEFAULT_RESULTS_PER_PAGE` | 400 | Results per API request |
| `DEFAULT_MAX_RADIUS` | 5000 | Search radius in meters |
| `DELAY_BETWEEN_CELLS` | 0.5s | Rate limiting |
| `DELAY_BETWEEN_PAGES` | 0.3s | Pagination rate limiting |

## Output Schema

```json
{
  "metadata": {
    "area": "New York, USA",
    "category": "lawyers",
    "boundary": { "north": ..., "south": ..., "east": ..., "west": ... }
  },
  "statistics": {
    "total_collected": 1234,
    "removed_outside_boundary": 56
  },
  "businesses": [
    {
      "name": "Business Name",
      "address": "Full Address",
      "place_id": "ChIJ...",
      "rating": 4.5,
      "review_count": 123,
      "latitude": 40.7128,
      "longitude": -74.0060,
      "phone": "+1 212-555-0123",
      "website": "https://...",
      "category": "Lawyer",
      "hours": { "monday": "9:00 AM - 5:00 PM", ... },
      "reviews_data": [ { "author": "...", "rating": 5, "text": "..." } ]
    }
  ]
}
```

## Google Maps PB Parameter Format

The `pb` URL parameter uses `!{field}{type}{value}` format:
- `!1s` - string (search query)
- `!7i` - integer (results count)
- `!8i` - integer (pagination offset)
- `!2d`/`!3d` - double (longitude/latitude)
- `!74i` - integer (max radius in meters)
- `!Nm` - message (N nested fields follow)
