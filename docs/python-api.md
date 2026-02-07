# Python Library API

## GMapsExtractor

The primary interface. Manages the internal API server, proxy configuration, and exposes collection methods.

```python
from gmaps_extractor import GMapsExtractor

with GMapsExtractor(proxy="http://user:pass@host:port") as extractor:
    result = extractor.collect_v2("New York, USA", "lawyers")
```

### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `proxy` | `Optional[str]` | `None` | Proxy URL (e.g., `"http://user:pass@host:port"`). Falls back to env vars, then config.py. |
| `cookies` | `Optional[Dict[str, str]]` | `None` | Explicit cookie override. If `None`, cookies are auto-managed. |
| `workers` | `int` | `20` | Default number of parallel search workers. |
| `server_port` | `int` | `8000` | Port for the internal FastAPI server. |
| `auto_start_server` | `bool` | `True` | Auto-start the server in a background thread. |
| `verbose` | `bool` | `True` | Print progress output to stdout. |

### Lifecycle

- The constructor applies configuration and starts the server (if `auto_start_server=True`).
- If a server is already running on the configured port, it is reused.
- Use as a context manager (`with` statement) for automatic cleanup.
- Call `extractor.shutdown()` manually if not using a context manager.
- Only one `GMapsExtractor` instance should be active at a time (see [Known Limitations](known-limitations.md)).

### Configuration Priority

Constructor args override environment variables, which override config.py defaults. Full details in [Configuration](configuration.md).

---

## collect_v2() -- Recommended

Enhanced collector with checkpoint/resume, parallel enrichment, adaptive rate limiting, and JSONL streaming.

```python
result = extractor.collect_v2(
    "Manhattan, New York",
    "lawyers",
    enrich=True,
    reviews=True,
    reviews_limit=50,
)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `area` | `str` | *required* | Geographic area (e.g., `"New York, USA"`). Resolved via Nominatim. |
| `category` | `str` | *required* | Business category (e.g., `"lawyers"`, `"restaurants"`). |
| `buffer_km` | `float` | `5.0` | Buffer in km added around the area boundary for filtering. |
| `enrich` | `bool` | `False` | Fetch place details (hours, phone, website). |
| `reviews` | `bool` | `False` | Fetch reviews for each business. |
| `reviews_limit` | `int` | `20` | Max reviews per business. |
| `output_file` | `Optional[str]` | `None` | JSON output path. Auto-generated as `output/{category}_in_{area}.json` if `None`. |
| `output_csv` | `Optional[str]` | `None` | CSV output path. Auto-generated if `None`. |
| `workers` | `Optional[int]` | `None` | Search workers. Overrides constructor default. |
| `enrichment_workers` | `int` | `5` | Parallel workers for detail/review fetching. |
| `checkpoint_interval` | `int` | `100` | Save checkpoint every N businesses. |
| `resume` | `bool` | `True` | Resume from existing checkpoint. |
| `subdivide` | `bool` | `False` | Use [subdivision mode](subdivision-mode.md). |
| `verbose` | `Optional[bool]` | `None` | Override constructor verbose setting. |

### Returns

A `CollectionResult` object (see below).

---

## collect() -- V1

Original collector. Use `collect_v2()` instead unless you have a specific reason.

```python
result = extractor.collect("New York, USA", "lawyers", enrich=True)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `area` | `str` | *required* | Geographic area. |
| `category` | `str` | *required* | Business category. |
| `buffer_km` | `float` | `5.0` | Buffer in km for filtering. |
| `enrich` | `bool` | `False` | Fetch place details. |
| `reviews` | `bool` | `False` | Fetch reviews. |
| `reviews_limit` | `int` | `5` | Max reviews per business. |
| `output_file` | `Optional[str]` | `None` | JSON output path. |
| `output_csv` | `Optional[Union[str, bool]]` | `None` | CSV path, `True` for auto, `False` to disable. |
| `workers` | `Optional[int]` | `None` | Search workers. |
| `subdivide` | `bool` | `False` | Use subdivision mode. |
| `verbose` | `Optional[bool]` | `None` | Override constructor verbose. |

### Returns

A `CollectionResult` object.

---

## V1 vs V2 Comparison

| Feature | `collect()` (V1) | `collect_v2()` (V2) |
|---------|-------------------|---------------------|
| Checkpoint/resume | No | Yes (auto, on by default) |
| Enrichment | Sequential | Parallel (separate worker pool) |
| Rate limiting | Fixed delays | Adaptive with exponential backoff |
| JSONL streaming | No | Yes (writes as collected) |
| Retry queue | No | Yes (failed cells retried with 5 attempts) |
| Deduplication | By `place_id` only | By both `place_id` and `hex_id` |
| Default `reviews_limit` | 5 | 20 |
| CSV disable | `output_csv=False` | Not supported (always writes CSV) |
| Return type (internal) | `Dict[str, Dict]` keyed by place_id | `Dict` with metadata/statistics/businesses |

**Recommendation:** Use `collect_v2()` for all use cases.

---

## CollectionResult

Wrapper around the result dictionary. Returned by both `collect()` and `collect_v2()`.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `.businesses` | `List[Dict]` | List of business dictionaries. |
| `.metadata` | `Dict` | Area, category, boundary, search mode, enrichment info. |
| `.statistics` | `Dict` | Counts, timing, dedup stats. |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `.to_dict()` | `Dict[str, Any]` | Full result as a plain dictionary. |

### Supported Operations

```python
result = extractor.collect_v2("NYC", "lawyers")

len(result)          # Number of businesses
result[0]            # First business dict
result[0:5]          # First five businesses
for biz in result:   # Iterate all businesses
    print(biz["name"])
```

### Representation

```python
>>> result
<CollectionResult: 142 businesses for 'lawyers' in 'Manhattan, New York'>
```
