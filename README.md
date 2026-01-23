# Google Maps Business Extractor

A powerful data collection tool that extracts business information from Google Maps for any geographic area and category.

## Features

- **Area-based extraction**: Search any city, region, or country
- **Grid-based coverage**: Automatically divides large areas into searchable cells
- **Pagination support**: Retrieves all results, not just the first page
- **Business enrichment**: Fetches detailed information for each business
- **Reviews extraction**: Collects reviews with author, rating, date, and text
- **Parallel processing**: Fast extraction with configurable workers
- **Proxy support**: Built-in rotating/sticky proxy configuration
- **Auto cookie management**: Automatically fetches and manages Google session cookies

## Installation

```bash
# Clone the repository
git clone https://github.com/promisingcoder/GoogleMapsCollectorPrivate.git
cd GoogleMapsCollectorPrivate

# Install dependencies
pip install -r requirements.txt

# Setup configuration
cp gmaps_extractor/config.example.py gmaps_extractor/config.py
# Edit config.py with your proxy credentials
```

## Quick Start

### 1. Start the API Server

```bash
python run_server.py
```

Server runs on http://localhost:8000

### 2. Collect Businesses

```bash
# Basic collection
python collect.py "New York, USA" "lawyers"

# With enrichment (details + reviews)
python collect.py "Paris, France" "restaurants" --enrich --reviews

# Full options
python collect.py "Area" "category" --enrich --reviews --reviews-limit 10 -o output.json
```

## Configuration

Edit `gmaps_extractor/config.py` to configure:

### Proxy Settings

```python
_DIRECT_PROXY_HOST = "your-proxy-host:port"
_DIRECT_PROXY_USER = "username"
_DIRECT_PROXY_PASS = "password_with_session_lifetime"
```

**Important**: Use a sticky IP session (30+ minutes recommended) for reliable cookie handling:
```
_lifetime-30m  # 30 minute sticky session
```

### Google Cookies

The system auto-fetches most cookies. The SOCS consent cookie is provided in defaults and rarely needs updating.

```python
_DEFAULT_COOKIES = {
    '__Secure-BUCKET': 'CGA',
    'SOCS': '...',  # Consent cookie - reusable
    'AEC': '...',   # Auto-fetched
    'NID': '...',   # Auto-fetched
}
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/execute` | POST | Execute search query |
| `/api/place-details` | POST | Get place details |
| `/api/reviews` | POST | Get reviews for a place |

## Output Format

```json
{
  "metadata": {
    "area": "New York, USA",
    "category": "lawyers",
    "boundary": { "north": 40.9, "south": 40.5, "east": -73.7, "west": -74.2 }
  },
  "statistics": {
    "total_collected": 1234,
    "removed_outside_boundary": 56
  },
  "businesses": [
    {
      "name": "Business Name",
      "address": "123 Main St, New York, NY",
      "place_id": "ChIJ...",
      "rating": 4.5,
      "review_count": 123,
      "latitude": 40.7128,
      "longitude": -74.0060,
      "phone": "+1 212-555-0123",
      "website": "https://example.com",
      "category": "Lawyer",
      "hours": {
        "monday": "9:00 AM - 5:00 PM",
        "tuesday": "9:00 AM - 5:00 PM"
      },
      "reviews_data": [
        {
          "author": "John Smith",
          "rating": 5,
          "text": "Excellent service!",
          "date": "2024-01-15"
        }
      ]
    }
  ]
}
```

## Architecture

```
gmaps_extractor/
├── __init__.py          # Package entry point
├── cli.py               # Command-line interface
├── config.py            # Configuration & cookie management
├── server.py            # FastAPI server
├── decoder/
│   ├── pb.py            # Google's protobuf URL decoder
│   ├── curl.py          # Curl command parser
│   └── request.py       # Request decoder
├── parsers/
│   ├── business.py      # Business data parser
│   ├── place.py         # Place details parser
│   └── reviews.py       # Reviews parser
├── geo/
│   ├── grid.py          # Grid cell generation
│   └── nominatim.py     # OpenStreetMap boundary API
└── extraction/
    ├── search.py        # Search query execution
    ├── enrichment.py    # Details & reviews fetching
    └── collector.py     # Main orchestration
```

## How It Works

1. **Boundary Detection**: Uses Nominatim API to get geographic boundaries for the area
2. **Grid Generation**: Divides the area into searchable cells based on size
3. **Parallel Search**: Queries each cell with pagination to get all results
4. **Deduplication**: Removes duplicate businesses by place_id
5. **Boundary Filtering**: Removes results outside the target area
6. **Enrichment** (optional): Fetches detailed info and reviews for each business
7. **Export**: Saves results to JSON

## Cookie System

The system uses a smart cookie management approach:

- **Auto-fetched cookies**: NID, AEC, __Secure-BUCKET are obtained automatically
- **SOCS cookie**: Consent cookie that's reused from defaults (doesn't expire quickly)
- **Session building**: Visits google.com → consent.google.com → maps.google.com to establish trust
- **Sticky IP required**: 30-minute proxy sessions recommended for reliable operation

## License

Private repository - All rights reserved.

## Acknowledgments

Built with:
- FastAPI for the API server
- httpx for HTTP requests
- Nominatim for geocoding
