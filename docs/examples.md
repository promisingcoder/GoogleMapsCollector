# Examples

## Python Library

### Basic Collection

```python
from gmaps_extractor import GMapsExtractor

with GMapsExtractor(proxy="http://user:pass@host:port") as extractor:
    result = extractor.collect_v2("Manhattan, New York", "lawyers")
    print(f"Found {len(result)} businesses")
```

### Collection with Full Enrichment

```python
with GMapsExtractor(proxy="http://user:pass@host:port") as extractor:
    result = extractor.collect_v2(
        "Paris, France",
        "restaurants",
        enrich=True,
        reviews=True,
        reviews_limit=50,
        enrichment_workers=10,
    )

    for biz in result:
        print(f"{biz['name']} - {biz.get('phone', 'N/A')}")
        if biz.get('reviews_data'):
            print(f"  {len(biz['reviews_data'])} reviews")
```

### Large Area with Subdivision

```python
with GMapsExtractor(proxy="http://user:pass@host:port") as extractor:
    result = extractor.collect_v2(
        "New York, USA",
        "dentists",
        subdivide=True,
        enrich=True,
        workers=30,
    )
    print(f"Found {len(result)} dentists across New York")
```

### Processing Results Programmatically

```python
with GMapsExtractor(proxy="http://user:pass@host:port") as extractor:
    result = extractor.collect_v2("Chicago, IL", "cafes", enrich=True)

    # Filter by rating
    top_rated = [b for b in result if (b.get("rating") or 0) >= 4.5]
    print(f"{len(top_rated)} cafes with 4.5+ rating")

    # Extract phone numbers
    phones = [b["phone"] for b in result if b.get("phone")]
    print(f"{len(phones)} businesses with phone numbers")

    # Group by category
    from collections import Counter
    categories = Counter(b.get("category", "Unknown") for b in result)
    for cat, count in categories.most_common(5):
        print(f"  {cat}: {count}")

    # Access metadata
    print(f"Search mode: {result.metadata.get('search_mode')}")
    print(f"Time: {result.statistics.get('total_time_seconds')}s")
```

### Resume After Interruption

```python
# First run -- gets interrupted (Ctrl+C) or crashes
with GMapsExtractor(proxy="http://user:pass@host:port") as extractor:
    result = extractor.collect_v2("London, UK", "hotels", enrich=True)

# Second run -- automatically resumes from checkpoint
with GMapsExtractor(proxy="http://user:pass@host:port") as extractor:
    result = extractor.collect_v2("London, UK", "hotels", enrich=True)
    # Picks up where it left off
```

### Custom Output Paths

```python
with GMapsExtractor(proxy="http://user:pass@host:port") as extractor:
    result = extractor.collect_v2(
        "Tokyo, Japan",
        "ramen",
        output_file="data/tokyo_ramen.json",
        output_csv="data/tokyo_ramen.csv",
    )
```

### Silent Mode

```python
with GMapsExtractor(proxy="http://user:pass@host:port", verbose=False) as extractor:
    result = extractor.collect_v2("Berlin, Germany", "bakeries")
    # No progress output printed
```

### Using the Full Result Dict

```python
with GMapsExtractor(proxy="http://user:pass@host:port") as extractor:
    result = extractor.collect_v2("NYC", "lawyers")

    # Get the raw dictionary
    data = result.to_dict()
    print(data["metadata"]["boundary"])
    print(data["statistics"]["total_collected"])
```

---

## CLI

All CLI examples assume `gmaps-server` is running in a separate terminal.

### Basic Collection

```bash
gmaps-collect-v2 "Manhattan, New York" "lawyers"
```

### With Reviews

```bash
gmaps-collect-v2 "Los Angeles, CA" "dentists" --enrich --reviews -l 100
```

### Subdivision Mode

```bash
gmaps-collect-v2 "New York, USA" "restaurants" --subdivide --enrich
```

### Resume After Interruption

```bash
# First run (interrupted with Ctrl+C)
gmaps-collect-v2 "London, UK" "hotels" --enrich

# Second run (resumes automatically)
gmaps-collect-v2 "London, UK" "hotels" --enrich
```

### Fresh Start

```bash
gmaps-collect-v2 "London, UK" "hotels" --no-resume
```

### Custom Output

```bash
gmaps-collect-v2 "Chicago, IL" "pizza" -o chicago_pizza.json --csv chicago_pizza.csv
```

### Quiet Mode

```bash
gmaps-collect-v2 "Berlin, Germany" "bakeries" -q
```

### Add Reviews to Existing Data

```bash
gmaps-enrich-reviews output/lawyers_in_manhattan.json -l 50
```
