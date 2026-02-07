# Troubleshooting

## "Connection refused" / Server Errors

**CLI users:** The server must be running in a separate terminal before running any collection command.

```bash
# Terminal 1
gmaps-server

# Terminal 2
gmaps-collect-v2 "NYC" "lawyers"
```

**Library users:** The server auto-starts, but it may fail if the port is already in use. Check for other processes on port 8000, or change the port:

```python
GMapsExtractor(proxy="...", server_port=9000)
```

## No Results Returned

**Proxy not configured:** Without a residential proxy, Google silently returns empty responses. There is no error message. Verify your proxy is set correctly by checking that `get_proxy_url()` returns a URL:

```python
from gmaps_extractor.config import get_proxy_url
print(get_proxy_url())  # Should print http://user:pass@host:port
```

**Area name not recognized:** Nominatim may not resolve vague or misspelled area names. Use specific formats:

- `"Manhattan, New York"` (good)
- `"downtown NYC"` (may not resolve)

If you get `ValueError: No results found for: ...`, try a more specific area name.

## Empty Reviews

- **Missing `hex_id`:** The reviews endpoint requires a `hex_id` for each business. Businesses without one are skipped during review enrichment.
- **Cookies expired:** Cookies are auto-refreshed every hour. If reviews suddenly stop working, the auto-fetch may have failed. Try setting `GMAPS_COOKIES` manually or restarting the extractor.

## Slow Performance

- **Too many workers:** Increasing workers beyond 20-30 often triggers more rate limiting, making the overall collection slower. Try reducing workers.
- **Enrichment bottleneck:** Detail and review fetching is slower than search. With `--enrich --reviews`, most time is spent in enrichment. Increase `--enrich-workers` to 10-15 (V2 only).

## "API server not available"

This is a V1-specific error. The V1 collector explicitly checks if the server is running before starting. Solutions:

- **CLI:** Start `gmaps-server` first
- **Library:** The library auto-starts the server. If you see this error in library mode, the server failed to start. Check for port conflicts.

## Checkpoint Issues

If a collection behaves unexpectedly after resuming (wrong counts, repeated businesses), delete the checkpoint:

```bash
# Delete specific checkpoint
rm output/.checkpoint_lawyers_manhattan.json

# Or delete all checkpoints
rm output/.checkpoint_*.json
```

Then run with `--no-resume` or `resume=False`.

## Port Already in Use

Another server instance or application is using the port. Either:

1. Stop the other process
2. Use a different port:

```python
GMapsExtractor(proxy="...", server_port=9000)
```

## Single Instance Warning

Do not create two `GMapsExtractor` instances simultaneously. The configuration is stored in shared module-level globals, so the second instance would overwrite the first instance's settings. See [Known Limitations](known-limitations.md).

## "No sub-areas found" in Subdivision Mode

Nominatim may not have subdivision data for all areas. This is normal. The collector automatically falls back to standard grid mode. See [Subdivision Mode](subdivision-mode.md).
