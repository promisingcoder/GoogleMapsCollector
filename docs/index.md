# gmaps-extractor Documentation

`gmaps-extractor` is a Python library and CLI tool that extracts business data from Google Maps at scale. Give it an area and a category, and it returns every matching business with details, reviews, and contact information.

**New here?** Install the package, set up a proxy, and run your first collection:

1. [Install the package](installation.md)
2. [Set up prerequisites (proxy)](prerequisites.md)
3. [Run the quick start example](quick-start.md)

## Documentation

| Article | Description |
|---------|-------------|
| [Installation](installation.md) | Install from PyPI or source |
| [Prerequisites & Setup](prerequisites.md) | Proxy requirements, cookies |
| [Quick Start](quick-start.md) | Get running in 5 minutes |
| [Python Library API](python-api.md) | `GMapsExtractor`, `collect()`, `collect_v2()`, `CollectionResult` |
| [Configuration](configuration.md) | Constructor args, environment variables, config file |
| [CLI Reference](cli-reference.md) | `gmaps-collect-v2`, `gmaps-collect`, `gmaps-enrich-reviews`, `gmaps-server` |
| [Output Format](output-format.md) | JSON structure, CSV columns, JSONL streaming |
| [Subdivision Mode](subdivision-mode.md) | Break large areas into neighborhoods for better coverage |
| [Resuming Collections](resuming-collections.md) | Checkpoint/resume in V2 |
| [Rate Limiting & Performance](rate-limiting.md) | Adaptive delays, worker tuning, cell sizes |
| [Error Handling](error-handling.md) | Exceptions, error patterns |
| [Troubleshooting](troubleshooting.md) | Common problems and fixes |
| [Examples](examples.md) | Complete working examples for Python and CLI |
| [Known Limitations](known-limitations.md) | Constraints and caveats |

## Package Info

- **PyPI name:** `gmaps-extractor`
- **Import name:** `gmaps_extractor`
- **Version:** 1.0.0
- **Python:** 3.9+
- **License:** MIT
