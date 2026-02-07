# Subdivision Mode

Subdivision mode breaks a large area into smaller named sub-areas (boroughs, districts, neighborhoods) and searches each one independently. This can yield more results than a standard grid search, especially for large or densely populated areas.

## When to Use

- **Large cities** with distinct neighborhoods (e.g., New York, London, Tokyo)
- **Regions or states** where a single grid would be too coarse
- **Areas where standard grid search misses results** -- subdivision provides better geographic coverage by leveraging OpenStreetMap's knowledge of local administrative boundaries

## How It Works

1. The area name is sent to the **Nominatim API** (OpenStreetMap) to resolve the main boundary
2. Nominatim is queried again for **administrative subdivisions** within that boundary
3. Sub-area types searched (in order): `borough`, `city_district`, `district`, `suburb`, `neighbourhood`, `quarter`
4. Each sub-area gets its own **grid** with a cell size appropriate to its dimensions
5. All cells from all sub-areas are queried in **parallel**
6. Results are deduplicated and filtered to the main area boundary
7. If **no sub-areas are found**, the collector falls back to standard grid mode automatically

Each business in the results includes a `found_in` field indicating which sub-area it was discovered in.

## Usage

**Python:**

```python
result = extractor.collect_v2("New York, USA", "lawyers", subdivide=True)
```

**CLI:**

```bash
gmaps-collect-v2 "New York, USA" "lawyers" --subdivide
```

## Behavior Differences Between V1 and V2

Both collectors support `--subdivide`, but they handle it differently:

- **V2** flattens all cells from all sub-areas into a single parallel work queue. Every cell is tagged with its source sub-area for the `found_in` field.
- **V1** queries entire sub-areas as units -- each sub-area runs its grid sequentially, but sub-areas run in parallel.

V2's approach gives more even parallelism and enables checkpoint/resume at the cell level.

## Nominatim Rate Limits

Nominatim enforces a rate limit of 1 request per second. Subdivision discovery makes multiple queries (one per sub-area type, with multiple query formats), so the discovery phase can take 10-30 seconds depending on how many sub-area types are searched.

## Fallback

If Nominatim returns no sub-areas for the given area, the collector prints a message and falls back to standard grid mode. No manual intervention is needed.
