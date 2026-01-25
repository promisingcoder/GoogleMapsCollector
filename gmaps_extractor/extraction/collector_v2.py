"""
Business Collector V2 - Enhanced Version with Full Subdivision Support

Features:
1. Checkpoint saves and resume capability
2. Adaptive rate limiting with exponential backoff
3. Retry queue for failed cells
4. Stream results to disk (memory efficient)
5. Batch yielding for agent/pipeline interface
6. Parallel enrichment
7. Proper subdivision mode with flattened cell parallelization
8. Always filter to main boundary
9. Better deduplication by place_id and hex_id
"""

import time
import json
import csv
import os
import random
import sys
import httpx
from typing import Dict, List, Optional, Tuple, Generator, Any, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from dataclasses import dataclass, field, asdict
from datetime import datetime

from ..config import (
    API_BASE_URL,
    DEFAULT_RESULTS_PER_PAGE,
    DEFAULT_MAX_RADIUS,
    DEFAULT_VIEWPORT_DIST,
    DELAY_BETWEEN_CELLS,
    DELAY_BETWEEN_PAGES,
    DEFAULT_PARALLEL_WORKERS,
    MAX_PARALLEL_WORKERS,
    CSV_COLUMNS,
    get_google_cookies,
)
from ..geo import get_area_boundary, generate_grid, is_in_boundary, calculate_cell_size, get_subdivision_areas, SubArea, AreaBoundary
from .search import execute_search
from .enrichment import fetch_place_details, fetch_reviews


# =============================================================================
# Rate Limiter with Adaptive Delays
# =============================================================================

@dataclass
class RateLimiter:
    """Adaptive rate limiter with exponential backoff. Thread-safe."""

    base_delay: float = 0.1
    max_delay: float = 30.0
    backoff_factor: float = 2.0
    jitter: float = 0.3

    # Internal state
    current_delay: float = field(default=0.1, init=False)
    consecutive_errors: int = field(default=0, init=False)
    consecutive_successes: int = field(default=0, init=False)
    _lock: Lock = field(default_factory=Lock, init=False)

    def record_success(self, response_time: float = 0.0):
        """Record a successful request."""
        with self._lock:
            self.consecutive_successes += 1
            self.consecutive_errors = 0
            if self.consecutive_successes >= 5:
                self.current_delay = max(self.base_delay, self.current_delay * 0.9)
                self.consecutive_successes = 0

    def record_error(self, is_rate_limit: bool = False):
        """Record a failed request."""
        with self._lock:
            self.consecutive_errors += 1
            self.consecutive_successes = 0
            multiplier = self.backoff_factor * 2 if is_rate_limit else self.backoff_factor
            self.current_delay = min(self.max_delay, self.current_delay * multiplier)

    def wait(self):
        """Wait for the appropriate delay with jitter."""
        with self._lock:
            delay = self.current_delay
        jitter_amount = delay * self.jitter
        actual_delay = delay + random.uniform(-jitter_amount, jitter_amount)
        time.sleep(max(0.01, actual_delay))

    def get_backoff_delay(self, attempt: int) -> float:
        """Get delay for retry attempt."""
        delay = self.base_delay * (self.backoff_factor ** attempt)
        return min(delay, self.max_delay)


# =============================================================================
# Checkpoint State Management
# =============================================================================

@dataclass
class CollectionState:
    """Persistent state for resumable collection."""

    area_name: str
    category: str
    buffer_km: float = 5.0
    use_subdivision: bool = False

    # Cell tracking
    completed_cells: List[str] = field(default_factory=list)  # cell_id strings
    failed_cells: List[str] = field(default_factory=list)

    # Business tracking
    businesses_count: int = 0
    collected_place_ids: Set[str] = field(default_factory=set)
    collected_hex_ids: Set[str] = field(default_factory=set)

    # Enrichment tracking
    enriched_place_ids: Set[str] = field(default_factory=set)

    # Timing
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_checkpoint: str = field(default_factory=lambda: datetime.now().isoformat())

    def save(self, checkpoint_path: str):
        """Save state to checkpoint file."""
        self.last_checkpoint = datetime.now().isoformat()
        data = {
            'area_name': self.area_name,
            'category': self.category,
            'buffer_km': self.buffer_km,
            'use_subdivision': self.use_subdivision,
            'completed_cells': self.completed_cells,
            'failed_cells': self.failed_cells,
            'businesses_count': self.businesses_count,
            'collected_place_ids': list(self.collected_place_ids),
            'collected_hex_ids': list(self.collected_hex_ids),
            'enriched_place_ids': list(self.enriched_place_ids),
            'started_at': self.started_at,
            'last_checkpoint': self.last_checkpoint,
        }
        with open(checkpoint_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, checkpoint_path: str) -> Optional['CollectionState']:
        """Load state from checkpoint file."""
        if not os.path.exists(checkpoint_path):
            return None
        try:
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            state = cls(
                area_name=data['area_name'],
                category=data['category'],
                buffer_km=data.get('buffer_km', 5.0),
                use_subdivision=data.get('use_subdivision', False),
            )
            state.completed_cells = data.get('completed_cells', [])
            state.failed_cells = data.get('failed_cells', [])
            state.businesses_count = data.get('businesses_count', 0)
            state.collected_place_ids = set(data.get('collected_place_ids', []))
            state.collected_hex_ids = set(data.get('collected_hex_ids', []))
            state.enriched_place_ids = set(data.get('enriched_place_ids', []))
            state.started_at = data.get('started_at', datetime.now().isoformat())
            return state
        except Exception:
            return None


# =============================================================================
# Cell with Source Tracking
# =============================================================================

@dataclass
class TaggedCell:
    """A grid cell tagged with its source (for subdivision mode)."""
    cell_id: str
    center_lat: float
    center_lng: float
    source_area: str  # Name of the sub-area this cell belongs to


# =============================================================================
# Cell Query with Retry
# =============================================================================

def query_cell_with_retry(
    cell: TaggedCell,
    category: str,
    results_per_page: int,
    max_radius: int,
    viewport_dist: int,
    rate_limiter: RateLimiter,
    max_retries: int = 3,
) -> Tuple[str, List[Dict], bool]:
    """
    Query a single cell with pagination and retry logic.
    Returns (cell_id, businesses, success).
    """
    all_results = []
    offset = 0

    while True:
        success = False

        for attempt in range(max_retries):
            try:
                rate_limiter.wait()
                start_time = time.time()

                businesses = execute_search(
                    category,
                    cell.center_lat,
                    cell.center_lng,
                    results_per_page,
                    max_radius,
                    viewport_dist,
                    offset=offset,
                )

                response_time = time.time() - start_time
                rate_limiter.record_success(response_time)

                if len(businesses) == 0:
                    return (cell.cell_id, all_results, True)

                # Tag businesses with source area
                for biz in businesses:
                    biz['found_in'] = cell.source_area

                all_results.extend(businesses)
                success = True
                break

            except Exception as e:
                is_rate_limit = '429' in str(e) or 'rate' in str(e).lower()
                rate_limiter.record_error(is_rate_limit=is_rate_limit)

                if attempt < max_retries - 1:
                    delay = rate_limiter.get_backoff_delay(attempt)
                    time.sleep(delay)

        if not success:
            return (cell.cell_id, all_results, False)

        if len(businesses) < results_per_page:
            break

        offset += results_per_page

    return (cell.cell_id, all_results, True)


# =============================================================================
# Parallel Enrichment
# =============================================================================

def enrich_single_business(
    business: Dict,
    fetch_details: bool,
    fetch_reviews_flag: bool,
    reviews_limit: int,
    rate_limiter: RateLimiter,
    cookies: Dict = None,
    page_size: int = 10,
    page_delay: float = 0.3,
) -> Tuple[str, Dict, bool]:
    """Enrich a single business. Returns (place_id, enriched_business, success)."""
    place_id = business.get('place_id')
    enriched = dict(business)
    success = True

    try:
        if fetch_details and place_id:
            rate_limiter.wait()
            details = fetch_place_details(
                place_id,
                name=business.get('name'),
                latitude=business.get('latitude'),
                longitude=business.get('longitude'),
                hex_id=business.get('hex_id'),
                ftid=business.get('ftid'),
            )
            if details:
                for key, value in details.items():
                    if value is not None and (key not in enriched or enriched[key] is None):
                        enriched[key] = value
                rate_limiter.record_success()
            else:
                rate_limiter.record_error()

        if fetch_reviews_flag and place_id:
            rate_limiter.wait()
            review_info = fetch_reviews(
                place_id,
                name=business.get('name'),
                latitude=business.get('latitude'),
                longitude=business.get('longitude'),
                hex_id=business.get('hex_id'),
                ftid=business.get('ftid'),
                limit=reviews_limit,
                cookies=cookies,
                page_size=page_size,
                page_delay=page_delay,
            )
            if review_info and review_info.get('reviews'):
                enriched['reviews_data'] = review_info['reviews']
                rate_limiter.record_success()
            else:
                rate_limiter.record_error()

    except Exception:
        success = False

    return (place_id, enriched, success)


def enrich_businesses_parallel(
    businesses: List[Dict],
    fetch_details: bool = True,
    fetch_reviews_flag: bool = True,
    reviews_limit: int = 20,
    parallel_workers: int = 5,
    rate_limiter: RateLimiter = None,
    cookies: Dict = None,
    verbose: bool = True,
    state: CollectionState = None,
    checkpoint_path: str = None,
    checkpoint_interval: int = 50,
) -> List[Dict]:
    """Enrich businesses in parallel with checkpoint support."""
    if rate_limiter is None:
        rate_limiter = RateLimiter(base_delay=0.3)

    if cookies is None:
        cookies = get_google_cookies()

    # Filter out already enriched businesses
    to_enrich = []
    already_enriched = []
    for biz in businesses:
        place_id = biz.get('place_id')
        if state and place_id in state.enriched_place_ids:
            already_enriched.append(biz)
        else:
            to_enrich.append(biz)

    if verbose and already_enriched:
        print(f"  Skipping {len(already_enriched)} already enriched businesses")

    total = len(to_enrich)
    if total == 0:
        return businesses

    enriched_list = list(already_enriched)
    completed = 0
    success_count = 0
    start_time = time.time()

    if verbose:
        print(f"\nEnriching {total} businesses with {parallel_workers} workers...")

    with ThreadPoolExecutor(max_workers=parallel_workers) as executor:
        future_to_biz = {
            executor.submit(
                enrich_single_business,
                biz,
                fetch_details,
                fetch_reviews_flag,
                reviews_limit,
                rate_limiter,
                cookies,
            ): biz
            for biz in to_enrich
        }

        for future in as_completed(future_to_biz):
            completed += 1
            try:
                place_id, enriched_biz, success = future.result()
                enriched_list.append(enriched_biz)

                if success:
                    success_count += 1
                    if state and place_id:
                        state.enriched_place_ids.add(place_id)

                if verbose and completed % 10 == 0:
                    elapsed = time.time() - start_time
                    rate = completed / elapsed if elapsed > 0 else 0
                    eta = (total - completed) / rate if rate > 0 else 0
                    print(f"  [{completed}/{total}] {success_count} enriched | {rate:.1f}/s | ETA: {eta:.0f}s")

                # Checkpoint during enrichment
                if state and checkpoint_path and completed % checkpoint_interval == 0:
                    state.save(checkpoint_path)

            except Exception as e:
                if verbose:
                    print(f"  [{completed}/{total}] Error: {e}")

    if verbose:
        elapsed = time.time() - start_time
        print(f"\n  Enrichment complete: {success_count}/{total} in {elapsed:.1f}s")

    return enriched_list


# =============================================================================
# Main Collection Function
# =============================================================================

def collect_businesses_v2(
    area_name: str,
    category: str,
    buffer_km: float = 5.0,
    enrich: bool = False,
    enrich_reviews: bool = False,
    reviews_limit: int = 20,
    output_file: str = None,
    output_csv: str = None,
    parallel_workers: int = DEFAULT_PARALLEL_WORKERS,
    enrichment_workers: int = 5,
    checkpoint_interval: int = 100,
    resume: bool = True,
    subdivide: bool = False,
    verbose: bool = True,
) -> Dict[str, Any]:
    """
    Enhanced business collection with all improvements.

    Args:
        area_name: Area to search (e.g., "New York, USA")
        category: Business category (e.g., "lawyers")
        buffer_km: Buffer for boundary filtering
        enrich: Fetch place details
        enrich_reviews: Fetch reviews
        reviews_limit: Max reviews per business
        output_file: JSON output path
        output_csv: CSV output path
        parallel_workers: Workers for cell queries
        enrichment_workers: Workers for enrichment
        checkpoint_interval: Save checkpoint every N businesses
        resume: Resume from checkpoint if available
        subdivide: Use subdivision mode for better coverage
        verbose: Print progress

    Returns:
        Result dict with metadata, statistics, and businesses
    """
    start_time = time.time()

    # Setup output paths
    safe_area = area_name.split(",")[0].replace(" ", "_").lower()
    safe_category = category.replace(" ", "_").lower()

    if output_file is None:
        output_file = f"output/{safe_category}_in_{safe_area}.json"
    if output_csv is None:
        output_csv = f"output/{safe_category}_in_{safe_area}.csv"

    checkpoint_path = f"output/.checkpoint_{safe_category}_{safe_area}.json"
    jsonl_path = output_file.replace('.json', '.jsonl')

    os.makedirs("output", exist_ok=True)

    if verbose:
        print("=" * 70)
        print(f"COLLECTING: {category} in {area_name}")
        print(f"Mode: {'Subdivision' if subdivide else 'Grid'}")
        print("=" * 70)

    # Try to resume from checkpoint
    state = None
    if resume:
        state = CollectionState.load(checkpoint_path)
        if state and verbose:
            print(f"\nResuming from checkpoint:")
            print(f"  Completed cells: {len(state.completed_cells)}")
            print(f"  Businesses collected: {state.businesses_count}")

    if state is None:
        state = CollectionState(
            area_name=area_name,
            category=category,
            buffer_km=buffer_km,
            use_subdivision=subdivide,
        )

    # Initialize rate limiter (shared across all workers)
    rate_limiter = RateLimiter(base_delay=DELAY_BETWEEN_CELLS)

    # Get boundaries
    if verbose:
        print(f"\nFetching boundaries for '{area_name}'...")

    grid_boundary, filter_boundary = get_area_boundary(area_name, buffer_km)

    if verbose:
        print(f"  Main area: {grid_boundary.name}")
        print(f"  N={grid_boundary.north:.4f}, S={grid_boundary.south:.4f}")
        print(f"  E={grid_boundary.east:.4f}, W={grid_boundary.west:.4f}")

    # Generate cells (from grid or subdivision)
    all_cells: List[TaggedCell] = []

    if subdivide:
        if verbose:
            print(f"\nGetting sub-areas for subdivision mode...")

        _, sub_areas = get_subdivision_areas(area_name, verbose=verbose)

        if sub_areas:
            if verbose:
                print(f"\nGenerating cells for {len(sub_areas)} sub-areas...")

            for sub_area in sub_areas:
                cell_size = calculate_cell_size(sub_area.boundary)
                cells = generate_grid(sub_area.boundary, cell_size_meters=cell_size)

                for cell in cells:
                    tagged_cell = TaggedCell(
                        cell_id=f"{sub_area.name}_{cell.cell_id}",
                        center_lat=cell.center_lat,
                        center_lng=cell.center_lng,
                        source_area=sub_area.full_name,
                    )
                    all_cells.append(tagged_cell)

            if verbose:
                print(f"  Total cells from sub-areas: {len(all_cells)}")
        else:
            if verbose:
                print(f"  No sub-areas found, falling back to grid mode")
            subdivide = False

    if not subdivide:
        # Standard grid mode
        cell_size = calculate_cell_size(grid_boundary)
        cells = generate_grid(grid_boundary, cell_size_meters=cell_size)

        for cell in cells:
            tagged_cell = TaggedCell(
                cell_id=str(cell.cell_id),
                center_lat=cell.center_lat,
                center_lng=cell.center_lng,
                source_area=area_name,
            )
            all_cells.append(tagged_cell)

        if verbose:
            print(f"\nGrid: {len(all_cells)} cells, {cell_size}m cell size")

    # Filter out completed cells
    completed_set = set(state.completed_cells)
    pending_cells = [c for c in all_cells if c.cell_id not in completed_set]

    if verbose:
        print(f"\nCell Status:")
        print(f"  Total cells: {len(all_cells)}")
        print(f"  Already completed: {len(completed_set)}")
        print(f"  Pending: {len(pending_cells)}")

    # Initialize JSONL for streaming (append mode if resuming)
    jsonl_mode = 'a' if resume and os.path.exists(jsonl_path) else 'w'

    # Initialize CSV
    if output_csv and not (resume and os.path.exists(output_csv)):
        with open(output_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(CSV_COLUMNS)

    # Collect businesses
    all_businesses: List[Dict] = []
    total_new = 0
    total_duplicates = 0
    total_filtered = 0

    workers = min(parallel_workers, len(pending_cells) or 1)

    if pending_cells:
        if verbose:
            print(f"\n{'='*70}")
            print(f"QUERYING {len(pending_cells)} CELLS ({workers} parallel workers)")
            print("=" * 70)

        completed_count = 0
        failed_cells = []

        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_cell = {
                executor.submit(
                    query_cell_with_retry,
                    cell,
                    category,
                    DEFAULT_RESULTS_PER_PAGE,
                    DEFAULT_MAX_RADIUS,
                    DEFAULT_VIEWPORT_DIST,
                    rate_limiter,
                ): cell
                for cell in pending_cells
            }

            for future in as_completed(future_to_cell):
                cell = future_to_cell[future]
                completed_count += 1

                try:
                    cell_id, businesses, success = future.result()

                    if success:
                        state.completed_cells.append(cell_id)
                    else:
                        state.failed_cells.append(cell_id)
                        failed_cells.append(cell)

                    # Process businesses - filter to main boundary and deduplicate
                    new_count = 0
                    dup_count = 0
                    filtered_count = 0

                    for biz in businesses:
                        place_id = biz.get('place_id')
                        hex_id = biz.get('hex_id')
                        lat = biz.get('latitude')
                        lng = biz.get('longitude')

                        # Filter to main boundary
                        if lat is not None and lng is not None:
                            if not is_in_boundary(lat, lng, filter_boundary):
                                filtered_count += 1
                                continue

                        # Deduplicate by place_id and hex_id
                        if place_id and place_id in state.collected_place_ids:
                            dup_count += 1
                            continue
                        if hex_id and hex_id in state.collected_hex_ids:
                            dup_count += 1
                            continue

                        # Add to collection
                        if place_id:
                            state.collected_place_ids.add(place_id)
                        if hex_id:
                            state.collected_hex_ids.add(hex_id)

                        all_businesses.append(biz)
                        new_count += 1

                        # Stream to JSONL
                        with open(jsonl_path, 'a', encoding='utf-8') as f:
                            f.write(json.dumps(biz, ensure_ascii=False) + '\n')

                        # Append to CSV
                        if output_csv:
                            with open(output_csv, 'a', newline='', encoding='utf-8') as f:
                                writer = csv.writer(f)
                                row = []
                                for col in CSV_COLUMNS:
                                    value = biz.get(col, '')
                                    if isinstance(value, (dict, list)):
                                        value = json.dumps(value, ensure_ascii=False)
                                    elif value is None:
                                        value = ''
                                    row.append(value)
                                writer.writerow(row)

                    total_new += new_count
                    total_duplicates += dup_count
                    total_filtered += filtered_count
                    state.businesses_count = len(all_businesses)

                    # Progress output
                    if verbose:
                        elapsed = time.time() - start_time
                        rate = completed_count / elapsed if elapsed > 0 else 0
                        eta = (len(pending_cells) - completed_count) / rate if rate > 0 else 0
                        # Sanitize cell_id for console
                        display_id = cell_id[:20] if len(cell_id) > 20 else cell_id
                        print(f"  [{completed_count}/{len(pending_cells)}] {display_id}: "
                              f"+{new_count} new | Total: {state.businesses_count} | "
                              f"{rate:.1f} cells/s | ETA: {eta:.0f}s")

                    # Checkpoint
                    if state.businesses_count % checkpoint_interval == 0:
                        state.save(checkpoint_path)
                        if verbose:
                            print(f"    >> Checkpoint saved ({state.businesses_count} businesses)")

                except Exception as e:
                    state.failed_cells.append(cell.cell_id)
                    if verbose:
                        print(f"  [{completed_count}/{len(pending_cells)}] Error: {e}")

        # Retry failed cells
        if failed_cells and verbose:
            print(f"\nRetrying {len(failed_cells)} failed cells...")

        for cell in failed_cells[:]:
            try:
                cell_id, businesses, success = query_cell_with_retry(
                    cell, category, DEFAULT_RESULTS_PER_PAGE,
                    DEFAULT_MAX_RADIUS, DEFAULT_VIEWPORT_DIST, rate_limiter,
                    max_retries=5,
                )
                if success:
                    failed_cells.remove(cell)
                    if cell.cell_id in state.failed_cells:
                        state.failed_cells.remove(cell.cell_id)
                    state.completed_cells.append(cell.cell_id)

                    for biz in businesses:
                        place_id = biz.get('place_id')
                        hex_id = biz.get('hex_id')
                        lat, lng = biz.get('latitude'), biz.get('longitude')

                        if lat and lng and not is_in_boundary(lat, lng, filter_boundary):
                            continue
                        if place_id and place_id in state.collected_place_ids:
                            continue
                        if hex_id and hex_id in state.collected_hex_ids:
                            continue

                        if place_id:
                            state.collected_place_ids.add(place_id)
                        if hex_id:
                            state.collected_hex_ids.add(hex_id)
                        all_businesses.append(biz)

                        with open(jsonl_path, 'a', encoding='utf-8') as f:
                            f.write(json.dumps(biz, ensure_ascii=False) + '\n')

            except Exception:
                pass

    search_time = time.time() - start_time

    if verbose:
        print(f"\n{'='*70}")
        print("SEARCH COMPLETE")
        print("=" * 70)
        print(f"  Total businesses: {len(all_businesses)}")
        print(f"  Duplicates removed: {total_duplicates}")
        print(f"  Filtered (outside boundary): {total_filtered}")
        print(f"  Search time: {search_time:.1f}s")

    # Enrichment
    if (enrich or enrich_reviews) and all_businesses:
        if verbose:
            print(f"\n{'='*70}")
            print("PARALLEL ENRICHMENT")
            print("=" * 70)

        enrichment_rate_limiter = RateLimiter(base_delay=0.3)

        all_businesses = enrich_businesses_parallel(
            all_businesses,
            fetch_details=enrich,
            fetch_reviews_flag=enrich_reviews,
            reviews_limit=reviews_limit,
            parallel_workers=enrichment_workers,
            rate_limiter=enrichment_rate_limiter,
            verbose=verbose,
            state=state,
            checkpoint_path=checkpoint_path,
            checkpoint_interval=50,
        )

    total_time = time.time() - start_time

    # Final output
    metadata = {
        'area': area_name,
        'category': category,
        'boundary': {
            'name': filter_boundary.name,
            'north': filter_boundary.north,
            'south': filter_boundary.south,
            'east': filter_boundary.east,
            'west': filter_boundary.west,
        },
        'search_mode': 'subdivision' if subdivide else 'grid',
        'enrichment': {
            'details_fetched': enrich,
            'reviews_fetched': enrich_reviews,
            'reviews_limit': reviews_limit if enrich_reviews else 0,
        },
    }

    statistics = {
        'total_cells': len(all_cells),
        'completed_cells': len(state.completed_cells),
        'failed_cells': len(state.failed_cells),
        'total_collected': len(all_businesses),
        'duplicates_removed': total_duplicates,
        'filtered_outside_boundary': total_filtered,
        'search_time_seconds': round(search_time, 1),
        'total_time_seconds': round(total_time, 1),
    }

    result = {
        'metadata': metadata,
        'statistics': statistics,
        'businesses': all_businesses,
    }

    # Write final JSON
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    # Update CSV with enriched data
    if output_csv and (enrich or enrich_reviews):
        with open(output_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(CSV_COLUMNS)
            for biz in all_businesses:
                row = []
                for col in CSV_COLUMNS:
                    value = biz.get(col, '')
                    if isinstance(value, (dict, list)):
                        value = json.dumps(value, ensure_ascii=False)
                    elif value is None:
                        value = ''
                    row.append(value)
                writer.writerow(row)

    # Clean up checkpoint on success
    if os.path.exists(checkpoint_path) and not state.failed_cells:
        os.remove(checkpoint_path)

    if verbose:
        print(f"\n{'='*70}")
        print("COLLECTION COMPLETE")
        print("=" * 70)
        print(f"  Total businesses: {len(all_businesses)}")
        print(f"  Total time: {total_time:.1f}s ({total_time/60:.1f} min)")
        print(f"  Output: {output_file}")
        if output_csv:
            print(f"  CSV: {output_csv}")

    return result
