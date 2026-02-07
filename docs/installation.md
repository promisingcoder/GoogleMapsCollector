# Installation

## From PyPI

```bash
pip install gmaps-extractor
```

This installs the `gmaps_extractor` package and four console scripts: `gmaps-collect`, `gmaps-collect-v2`, `gmaps-enrich-reviews`, and `gmaps-server`.

## From Source (Editable Mode)

Clone the repository and install in editable mode:

```bash
git clone https://github.com/promisingcoder/google_maps_business_extractor.git
cd google_maps_business_extractor
pip install -e .
```

Editable mode lets you modify the source and see changes immediately without reinstalling.

## Requirements

- **Python 3.9 or higher**
- Dependencies (installed automatically):
  - `fastapi>=0.104.0`
  - `uvicorn>=0.24.0`
  - `httpx>=0.25.0`
  - `pydantic>=2.0.0`

## Verify Installation

```bash
python -c "from gmaps_extractor import GMapsExtractor; print('OK')"
```

If this prints `OK`, the package is installed correctly.

Check that console scripts are available:

```bash
gmaps-collect-v2 --help
```

## Next Steps

Before running any collection, you need a residential proxy. See [Prerequisites & Setup](prerequisites.md).
