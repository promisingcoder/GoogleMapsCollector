# Known Limitations

## Single Instance Constraint

Only one `GMapsExtractor` instance should be active at a time. Configuration is stored in shared module-level globals (`config.py` constants), and `ExtractorConfig.apply()` mutates these globals without any guard. Creating a second instance overwrites the first instance's settings.

## No Input Validation

Constructor arguments and method parameters are not validated. Invalid values (negative workers, non-existent proxy URLs, malformed area names) pass silently and cause failures later in the pipeline. The area name is validated only when Nominatim is queried, which raises `ValueError` if nothing is found.

## Output Always Written to Disk

Both `collect()` and `collect_v2()` write JSON and CSV files to disk. There is no option to suppress file output when using the library. If you only need the in-memory `CollectionResult`, the files are still created in the `output/` directory.

## verbose=True by Default

The constructor defaults to `verbose=True`, which prints detailed progress output to stdout. Library users embedding this in a larger application should set `verbose=False`:

```python
GMapsExtractor(proxy="...", verbose=False)
```

## V1 Collector Limitations

`collect()` (V1) lacks several features available in `collect_v2()`:

- No checkpoint/resume
- Sequential enrichment (one business at a time)
- Fixed rate limiting (no adaptive backoff)
- No JSONL streaming
- No retry queue for failed cells
- Deduplication by `place_id` only (V2 uses both `place_id` and `hex_id`)

## Custom Exceptions Mostly Unused

Five exception classes are defined in `gmaps_extractor.exceptions`, but only `ServerError` is actually raised. The collectors throw `RuntimeError`, `ValueError`, and generic `Exception` instead. See [Error Handling](error-handling.md).

## OUTPUT_SCHEMA Missing Fields

The `OUTPUT_SCHEMA` dictionary exported from the config module lists 13 fields, but actual output includes 16 fields. The three fields missing from the schema are `hex_id`, `ftid`, and `found_in`. The `CSV_COLUMNS` list correctly includes all 16.

## reviews_limit Defaults Differ

- `collect()` (V1): `reviews_limit` defaults to **5**
- `collect_v2()` (V2): `reviews_limit` defaults to **20**

The same applies to the corresponding CLI commands (`gmaps-collect` vs `gmaps-collect-v2`).

## Nominatim Rate Limits

The Nominatim API (OpenStreetMap) enforces a rate limit of 1 request per second. Subdivision discovery makes multiple sequential requests, which can take 10-30 seconds. This only affects the initial area resolution phase, not the main collection.

## V2 CSV Disable Not Supported

V1's `collect()` accepts `output_csv=False` to skip CSV output. V2's `collect_v2()` always generates a CSV file. There is no way to disable CSV output in V2.
