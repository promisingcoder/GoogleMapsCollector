# Rate Limiting & Performance

## Default Delays

| Delay | Default (seconds) | Purpose |
|-------|-------------------|---------|
| `DELAY_BETWEEN_CELLS` | 0.05 | Pause between grid cell queries |
| `DELAY_BETWEEN_PAGES` | 0.1 | Pause between pagination requests within a cell |
| `DELAY_BETWEEN_DETAILS` | 0.2 | Pause between place detail requests |
| `DELAY_BETWEEN_REVIEWS` | 0.2 | Pause between review requests |

## V2 Adaptive Rate Limiter

V2 uses a `RateLimiter` class that adjusts delays dynamically:

- **On success:** After 5 consecutive successes, the delay decreases by 10% (down to the base delay).
- **On error:** The delay doubles immediately (quadruples for rate-limit errors like HTTP 429).
- **Jitter:** Each wait adds random jitter of +/-30% to avoid thundering herd effects.
- **Maximum delay:** Caps at 30 seconds regardless of backoff accumulation.

V1 uses fixed delays with no adaptation.

## Worker Counts

### Search Workers

Control how many grid cells are queried simultaneously.

| Setting | Default | Maximum |
|---------|---------|---------|
| `workers` (constructor) | 20 | 50 |
| `-w`/`--workers` (V2 CLI) | 20 | -- |
| `-p`/`--parallel` (V1 CLI) | 20 | 50 |

### Enrichment Workers (V2 Only)

A separate worker pool for fetching place details and reviews.

| Setting | Default |
|---------|---------|
| `enrichment_workers` (Python) | 5 |
| `--enrich-workers` (V2 CLI) | 5 |

V1 performs enrichment sequentially (one business at a time).

## Grid Cell Size Auto-Selection

The cell size determines how fine-grained the search grid is. It is chosen automatically based on the area's dimensions:

| Area Dimension | Cell Size | Typical Use |
|----------------|-----------|-------------|
| Under 10 km | 1,000 m | City neighborhoods, small towns |
| 10-30 km | 2,000 m | Cities |
| 30-100 km | 5,000 m | Metro areas, counties |
| 100-500 km | 50,000 m | States, provinces |
| Over 500 km | 100,000 m | Countries |

Smaller cells mean more queries but better coverage. The dimensions used are the height and width of the resolved boundary.

## Tuning Tips

- **More workers is not always faster.** Google rate-limits aggressive scraping. If you see many errors or empty responses, reduce workers.
- **Enrichment is the bottleneck** for large collections with `--enrich --reviews`. Details and reviews each require a separate request per business. Increase `enrichment_workers` cautiously (10-15 is usually the practical limit).
- **Subdivision mode** can increase total cell count significantly. A city with 50 neighborhoods at 20 cells each is 1000 cells. Monitor the total cell count printed at startup.
- **Retry queue** (V2 only): Failed cells are retried with 5 attempts and increased backoff. If cells consistently fail, it usually indicates a proxy or rate-limit issue.
