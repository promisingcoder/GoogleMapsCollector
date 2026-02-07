# Output Format

All collection methods write results to disk. Default output directory is `output/` with filenames derived from the category and area: `{category}_in_{area}.json` and `.csv`.

## JSON Structure

```json
{
  "metadata": {
    "area": "Manhattan, New York",
    "category": "lawyers",
    "boundary": {
      "name": "Manhattan Region",
      "north": 40.927,
      "south": 40.654,
      "east": -73.862,
      "west": -74.093
    },
    "search_mode": "grid",
    "enrichment": {
      "details_fetched": true,
      "reviews_fetched": true,
      "reviews_limit": 20
    }
  },
  "statistics": {
    "total_collected": 342,
    "duplicates_removed": 58,
    "filtered_outside_boundary": 23,
    "search_time_seconds": 45.2,
    "total_time_seconds": 180.7
  },
  "businesses": [
    {
      "name": "Smith & Associates Law Firm",
      "address": "123 Broadway, New York, NY 10006",
      "place_id": "ChIJabc123def456",
      "hex_id": "0x89c259a8669c0f0d:0x25d4109319b4f5a0",
      "ftid": "/g/1vs5xm_3",
      "rating": 4.5,
      "review_count": 87,
      "latitude": 40.7128,
      "longitude": -74.0060,
      "phone": "+1 212-555-0123",
      "website": "https://www.smithlaw.example.com",
      "category": "Lawyer",
      "categories": ["Lawyer", "Legal Services"],
      "hours": {
        "monday": "9:00 AM - 5:00 PM",
        "tuesday": "9:00 AM - 5:00 PM",
        "wednesday": "9:00 AM - 5:00 PM",
        "thursday": "9:00 AM - 5:00 PM",
        "friday": "9:00 AM - 5:00 PM"
      },
      "found_in": "Manhattan, New York, NY, USA",
      "reviews_data": [
        {
          "review_id": "ChdDSUh...",
          "author": "Jane Doe",
          "author_photo": "https://lh3.googleusercontent.com/...",
          "rating": 5,
          "date": "2 months ago",
          "text": "Excellent service..."
        }
      ]
    }
  ]
}
```

## Business Fields

Each business dictionary contains up to 16 fields:

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Business name |
| `address` | string | Full street address |
| `place_id` | string | Google Places ID (e.g., `"ChIJ..."`) |
| `hex_id` | string | Hex format ID (e.g., `"0x...:0x..."`) used for details/reviews |
| `ftid` | string | Feature ID (e.g., `"/g/1vs5xm_3"`) |
| `rating` | float | Average rating (1.0-5.0), or `null` |
| `review_count` | int | Number of Google reviews |
| `latitude` | float | Geographic latitude |
| `longitude` | float | Geographic longitude |
| `phone` | string | Phone number (requires enrichment) |
| `website` | string | Website URL (requires enrichment) |
| `category` | string | Primary business category |
| `categories` | list | All categories assigned to the business |
| `hours` | dict | Operating hours keyed by day of week (requires enrichment) |
| `found_in` | string | Sub-area or area name where the business was found |
| `reviews_data` | list | List of review dicts (requires `reviews=True`) |

Fields that require enrichment (`enrich=True` or `reviews=True`) are `null` or absent when enrichment is not enabled.

## CSV Format

The CSV file contains the same 16 fields as columns:

```
name, address, place_id, hex_id, ftid, rating, review_count, latitude, longitude, phone, website, category, categories, hours, found_in, reviews_data
```

Dictionary and list values (`categories`, `hours`, `reviews_data`) are serialized as JSON strings within their CSV cells.

## JSONL Streaming (V2 Only)

`collect_v2()` writes a `.jsonl` file alongside the JSON output. Each line is a single business as JSON, written as soon as it is collected:

```
output/lawyers_in_manhattan.jsonl
```

This is useful for monitoring progress or processing results before collection finishes. The JSONL file contains only the business objects (no metadata or statistics wrapper).

## Output File Paths

Default paths use a sanitized form of the area and category:

```
output/{category}_in_{area}.json
output/{category}_in_{area}.csv
output/{category}_in_{area}.jsonl    (V2 only)
```

Where `{area}` is the text before the first comma, lowercased, with spaces replaced by underscores. For example, `"Manhattan, New York"` becomes `manhattan`.

Custom paths:

```python
# Python
result = extractor.collect_v2("NYC", "lawyers", output_file="my_data.json", output_csv="my_data.csv")
```

```bash
# CLI
gmaps-collect-v2 "NYC" "lawyers" -o my_data.json --csv my_data.csv
```

> **Note:** Output files are always written to disk, even when using the Python library. There is no option to suppress file output.
