# CLI Reference

> **Warning:** All CLI commands require `gmaps-server` running in a separate terminal. The CLI does not auto-start the server (unlike the Python library API).

## Starting the Server

```bash
gmaps-server
```

The server starts on `0.0.0.0:8000` by default. It must be running before any CLI collection command.

Configure the proxy via environment variables before starting the server. See [Configuration](configuration.md).

---

## gmaps-collect-v2 (Recommended)

Enhanced collector with checkpoint/resume, parallel enrichment, and adaptive rate limiting.

```bash
gmaps-collect-v2 "Manhattan, New York" "lawyers"
```

### Flags

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `area` | positional | *required* | Geographic area name |
| `category` | positional | *required* | Business category |
| `-b`, `--buffer` | float | `5.0` | Buffer in km for boundary filtering |
| `--enrich` | flag | off | Fetch place details (hours, phone, website) |
| `--reviews` | flag | off | Fetch reviews |
| `-l`, `--reviews-limit` | int | `20` | Max reviews per business |
| `-w`, `--workers` | int | `20` | Parallel workers for cell queries |
| `--enrich-workers` | int | `5` | Parallel workers for enrichment |
| `-c`, `--checkpoint` | int | `100` | Save checkpoint every N businesses |
| `--resume` | flag | on | Resume from checkpoint (default behavior) |
| `--no-resume` | flag | off | Ignore existing checkpoint, start fresh |
| `--subdivide` | flag | off | Use [subdivision mode](subdivision-mode.md) |
| `-o`, `--output` | string | auto | JSON output path |
| `--csv` | string | auto | CSV output path |
| `-q`, `--quiet` | flag | off | Suppress progress output |

### Examples

```bash
# Basic collection
gmaps-collect-v2 "Paris, France" "restaurants"

# Full enrichment with reviews
gmaps-collect-v2 "Los Angeles, CA" "dentists" --enrich --reviews -l 50

# Large area with subdivision
gmaps-collect-v2 "New York, USA" "lawyers" --subdivide --enrich

# Custom output path, more workers
gmaps-collect-v2 "Chicago, IL" "hotels" -w 30 --enrich-workers 10 -o hotels_chicago.json

# Fresh start (ignore checkpoint)
gmaps-collect-v2 "Boston, MA" "cafes" --no-resume
```

---

## gmaps-collect (V1)

Original collector. Lacks resume, parallel enrichment, and adaptive rate limiting. Use `gmaps-collect-v2` instead.

```bash
gmaps-collect "New York, USA" "lawyers"
```

### Flags

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `area` | positional | *required* | Geographic area name |
| `category` | positional | *required* | Business category |
| `-o`, `--output` | string | auto | JSON output path |
| `--csv` | string | auto | CSV output path |
| `--no-csv` | flag | off | Disable CSV output |
| `-b`, `--buffer` | float | `5.0` | Buffer in km for filtering |
| `-p`, `--parallel` | int | `20` | Parallel workers (max 50) |
| `--enrich` | flag | off | Fetch place details |
| `--reviews` | flag | off | Fetch reviews |
| `--reviews-limit` | int | `5` | Max reviews per business |
| `-q`, `--quiet` | flag | off | Suppress progress output |
| `--subdivide` | flag | off | Use subdivision mode |

> **Note:** V1 uses `-p`/`--parallel` for workers, while V2 uses `-w`/`--workers`. V1 defaults to 5 reviews per business; V2 defaults to 20.

---

## gmaps-enrich-reviews

Add reviews to an existing collection JSON file. Requires the server running.

```bash
gmaps-enrich-reviews output/lawyers_in_manhattan.json -l 50
```

### Flags

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `input_file` | positional | *required* | JSON file from a previous collection |
| `-o`, `--output` | string | `{input}_with_reviews.json` | Output file path |
| `-l`, `--limit` | int | `100` | Reviews per business |
| `-b`, `--batch-size` | int | `5` | Requests per batch |
| `-d`, `--batch-delay` | float | `1.5` | Delay between businesses (seconds) |
| `-s`, `--save-interval` | int | `100` | Save progress every N businesses |
| `-p`, `--page-size` | int | `10` | Reviews per API request (max 20) |
| `--page-delay` | float | `0.5` | Delay between pagination requests |

### Examples

```bash
# Add up to 100 reviews per business
gmaps-enrich-reviews output/lawyers_in_manhattan.json

# Custom limits and output
gmaps-enrich-reviews output/data.json -l 200 -o enriched.json --page-size 20

# Slower pace to avoid rate limits
gmaps-enrich-reviews output/data.json -d 3.0 --page-delay 1.0
```

Businesses that already have `reviews_data` or lack a `hex_id` are skipped automatically. Progress is saved periodically based on `--save-interval`.
