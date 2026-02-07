# Quick Start

## Python Library

```python
from gmaps_extractor import GMapsExtractor

with GMapsExtractor(proxy="http://user:pass@host:port") as extractor:
    result = extractor.collect_v2("Manhattan, New York", "lawyers", enrich=True)
    print(f"Found {len(result)} businesses")
    for biz in result:
        print(biz["name"], biz["phone"])
```

The server starts automatically in the background. Results are saved to `output/lawyers_in_manhattan.json` and `output/lawyers_in_manhattan.csv`.

`collect_v2()` is the recommended method. See [Python Library API](python-api.md) for the full API reference.

## CLI

CLI commands require the API server running in a separate terminal.

**Terminal 1** -- start the server:

```bash
gmaps-server
```

**Terminal 2** -- run a collection:

```bash
gmaps-collect-v2 "Manhattan, New York" "lawyers" --enrich --reviews
```

Output files are written to the `output/` directory.

See [CLI Reference](cli-reference.md) for all commands and flags.

## What to Expect

A typical collection prints progress as it runs:

```
======================================================================
COLLECTING: lawyers in Manhattan, New York
Mode: Grid
======================================================================

Fetching boundaries for 'Manhattan, New York'...
  Main area: Manhattan
  N=40.8821, S=40.6996, E=-73.9068, W=-74.0479

Grid: 24 cells, 1000m cell size

======================================================================
QUERYING 24 CELLS (20 parallel workers)
======================================================================
  [1/24] 0: +12 new | Total: 12 | 2.3 cells/s | ETA: 10s
  ...
```

When complete, two files appear in `output/`:
- `lawyers_in_manhattan.json` -- full structured data
- `lawyers_in_manhattan.csv` -- flat table

See [Output Format](output-format.md) for the file structure.
