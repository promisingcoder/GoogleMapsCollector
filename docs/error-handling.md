# Error Handling

## Exception Hierarchy

The package defines custom exceptions in `gmaps_extractor.exceptions`:

```
GMapsExtractorError (base)
  +-- ServerError
  +-- BoundaryError
  +-- ConfigurationError
  +-- RateLimitError
  +-- AuthenticationError
```

> **Important:** Of these, only `ServerError` is actually raised by the code. It is thrown by `GMapsExtractor.__init__()` when the internal API server fails to start within 5 seconds. The remaining exceptions are defined but never raised by the current implementation.

## What Is Actually Raised

| Exception | Where | Cause |
|-----------|-------|-------|
| `ServerError` | `GMapsExtractor._ensure_server()` | Server did not become ready on the configured port within 5 seconds |
| `RuntimeError` | V1 `collect_businesses()` | API server not running (`"API server not available"`) or boundary fetch failure |
| `ValueError` | `get_area_boundary()` | Nominatim returned no results for the area name |
| `Exception` | Various collectors | Network errors, JSON parse failures, unexpected Google responses |

## Recommended Patterns

### Catch server startup failure

```python
from gmaps_extractor import GMapsExtractor
from gmaps_extractor.exceptions import ServerError

try:
    with GMapsExtractor(proxy="http://user:pass@host:port") as extractor:
        result = extractor.collect_v2("NYC", "lawyers")
except ServerError as e:
    print(f"Server failed to start: {e}")
```

### Catch common runtime errors

```python
try:
    result = extractor.collect_v2("NYC", "lawyers")
except ValueError as e:
    # Nominatim could not resolve the area name
    print(f"Area not found: {e}")
except Exception as e:
    # Network errors, Google response issues, etc.
    print(f"Collection failed: {e}")
```

### Broad catch (simplest)

```python
try:
    result = extractor.collect_v2("NYC", "lawyers")
except Exception as e:
    print(f"Error: {e}")
```

## KeyboardInterrupt

Both V1 and V2 CLI entry points handle `KeyboardInterrupt`:

- **V1:** Prints `"Interrupted by user."` and exits with code 130.
- **V2:** Prints `"Interrupted! Progress saved to checkpoint."` and exits with code 1. The checkpoint enables [resuming](resuming-collections.md) later.

When using the Python library directly, `KeyboardInterrupt` propagates normally. The context manager (`with` statement) ensures the server is shut down cleanly.
