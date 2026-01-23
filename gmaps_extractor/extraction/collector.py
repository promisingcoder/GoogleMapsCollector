"""
Business Collector

Main orchestration module for collecting businesses from Google Maps.
Handles grid-based search with parallel processing, CSV output, and enrichment.
"""

import time
import json
import csv
import os
import httpx
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

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
)
from ..geo import get_area_boundary, generate_grid, is_in_boundary, calculate_cell_size
from .search import execute_search
from .enrichment import enrich_businesses


def check_api_available() -> bool:
    """Check if the API server is running and healthy."""
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{API_BASE_URL}/api/health")
            return response.status_code == 200
    except:
        return False


def query_cell(
    cell,
    category: str,
    results_per_page: int,
    max_radius: int,
    viewport_dist: int,
) -> Tuple[int, List[Dict]]:
    """
    Query a single cell with pagination. Returns (cell_id, businesses).
    Thread-safe function for parallel execution.
    """
    all_results = []
    offset = 0

    while True:
        try:
            businesses = execute_search(
                category,
                cell.center_lat,
                cell.center_lng,
                results_per_page,
                max_radius,
                viewport_dist,
                offset=offset,
            )

            if len(businesses) == 0:
                break

            all_results.extend(businesses)

            if len(businesses) < results_per_page:
                break

            offset += results_per_page
            time.sleep(DELAY_BETWEEN_PAGES)

        except Exception:
            break

    return (cell.cell_id, all_results)


def write_csv_header(csv_path: str):
    """Write CSV header row."""
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(CSV_COLUMNS)


def append_to_csv(csv_path: str, businesses: List[Dict], lock: Lock):
    """Append businesses to CSV file (thread-safe)."""
    with lock:
        with open(csv_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for biz in businesses:
                row = []
                for col in CSV_COLUMNS:
                    value = biz.get(col, '')
                    if isinstance(value, (dict, list)):
                        value = json.dumps(value, ensure_ascii=False)
                    elif value is None:
                        value = ''
                    row.append(value)
                writer.writerow(row)


def collect_businesses(
    area_name: str,
    category: str,
    buffer_km: float = 5.0,
    enrich: bool = False,
    enrich_reviews: bool = False,
    reviews_limit: int = 5,
    output_file: str = None,
    output_csv: str = None,
    parallel_workers: int = DEFAULT_PARALLEL_WORKERS,
    verbose: bool = True,
) -> Dict[str, Dict]:
    """
    Collect all businesses of a category in an area.

    Args:
        area_name: Name of the area (e.g., "New York, USA")
        category: Business category to search (e.g., "lawyers")
        buffer_km: Buffer in km for coordinate filtering
        enrich: Whether to fetch detailed place info
        enrich_reviews: Whether to fetch reviews
        reviews_limit: Number of reviews per business
        output_file: Path to save JSON results (auto-generated if None)
        output_csv: Path to save CSV results (auto-generated if None, set to False to disable)
        parallel_workers: Number of parallel workers for cell queries
        verbose: Whether to print progress

    Returns:
        Dictionary of place_id -> business data
    """
    start_time = time.time()

    if verbose:
        print("=" * 70)
        print(f"COLLECTING: {category} in {area_name}")
        print("=" * 70)

    # Check API availability
    if verbose:
        print("\nChecking API availability...")
    if not check_api_available():
        raise RuntimeError("API server not available. Start it with: python run_server.py")
    if verbose:
        print("  [OK] API is running")

    # Fetch boundaries
    if verbose:
        print(f"\nFetching boundaries for '{area_name}'...")
    try:
        grid_boundary, filter_boundary = get_area_boundary(area_name, buffer_km)
        if verbose:
            print(f"  [OK] Boundaries fetched")
    except Exception as e:
        raise RuntimeError(f"Failed to fetch boundaries: {e}")

    if verbose:
        print(f"\nGrid Area: {grid_boundary.name}")
        print(f"  N={grid_boundary.north:.4f}, S={grid_boundary.south:.4f}")
        print(f"  E={grid_boundary.east:.4f}, W={grid_boundary.west:.4f}")

    # Calculate cell size and generate grid
    cell_size = calculate_cell_size(grid_boundary)
    cells = generate_grid(grid_boundary, cell_size_meters=cell_size)

    # Limit parallel workers (minimum 1)
    parallel_workers = max(1, min(parallel_workers, MAX_PARALLEL_WORKERS, len(cells)))

    if verbose:
        print(f"\nGrid Configuration:")
        print(f"  Cell Size: {cell_size}m")
        print(f"  Total Cells: {len(cells)}")
        print(f"  Parallel Workers: {parallel_workers}")

    # Setup output paths
    safe_area = area_name.split(",")[0].replace(" ", "_").lower()
    safe_category = category.replace(" ", "_").lower()

    if output_file is None:
        output_file = f"output/{safe_category}_in_{safe_area}.json"

    if output_csv is None:
        output_csv = f"output/{safe_category}_in_{safe_area}.csv"

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else "output", exist_ok=True)

    # Initialize CSV if enabled
    csv_lock = Lock()
    if output_csv:
        write_csv_header(output_csv)
        if verbose:
            print(f"\nCSV output: {output_csv}")

    if verbose:
        print(f"\nSearch Parameters:")
        print(f"  Query: '{category}'")
        print(f"  Results per page: {DEFAULT_RESULTS_PER_PAGE}")
        print(f"  Max radius: {DEFAULT_MAX_RADIUS}m")

    # Collect businesses from all cells using parallel processing
    all_businesses = {}
    businesses_lock = Lock()
    completed_cells = 0
    total_new = 0
    total_duplicates = 0

    if verbose:
        print(f"\n{'='*70}")
        print(f"QUERYING {len(cells)} CELLS ({parallel_workers} parallel workers)...")
        print("=" * 70)

    def process_cell_result(cell_id: int, businesses: List[Dict]) -> Tuple[int, int]:
        """Process results from a cell query. Returns (new_count, duplicate_count)."""
        nonlocal all_businesses
        new_businesses = []
        new_count = 0
        dup_count = 0

        with businesses_lock:
            for biz in businesses:
                place_id = biz.get('place_id') or biz.get('name')
                if place_id:
                    if place_id not in all_businesses:
                        all_businesses[place_id] = biz
                        new_businesses.append(biz)
                        new_count += 1
                    else:
                        dup_count += 1

        # Append new businesses to CSV
        if output_csv and new_businesses:
            append_to_csv(output_csv, new_businesses, csv_lock)

        return new_count, dup_count

    # Execute parallel queries
    with ThreadPoolExecutor(max_workers=parallel_workers) as executor:
        # Submit all cell queries
        future_to_cell = {
            executor.submit(
                query_cell,
                cell,
                category,
                DEFAULT_RESULTS_PER_PAGE,
                DEFAULT_MAX_RADIUS,
                DEFAULT_VIEWPORT_DIST,
            ): cell
            for cell in cells
        }

        # Process results as they complete
        for future in as_completed(future_to_cell):
            cell = future_to_cell[future]
            completed_cells += 1

            try:
                cell_id, businesses = future.result()
                new_count, dup_count = process_cell_result(cell_id, businesses)
                total_new += new_count
                total_duplicates += dup_count

                if verbose:
                    elapsed = time.time() - start_time
                    print(f"  [{completed_cells}/{len(cells)}] Cell {cell_id}: "
                          f"+{new_count} new, {dup_count} dups | "
                          f"Total: {len(all_businesses)} | "
                          f"Time: {elapsed:.1f}s")

            except Exception as e:
                if verbose:
                    print(f"  [{completed_cells}/{len(cells)}] Cell {cell.cell_id}: ERROR - {e}")

    search_time = time.time() - start_time

    if verbose:
        print(f"\n  Search completed in {search_time:.1f}s")
        print(f"  Found {len(all_businesses)} unique businesses")

    # Filter by coordinates
    if verbose:
        print(f"\n{'='*70}")
        print("FILTERING BY COORDINATES")
        print("=" * 70)

    before_filter = len(all_businesses)
    filtered_businesses = {}
    removed_count = 0

    for place_id, biz in all_businesses.items():
        lat = biz.get('latitude')
        lng = biz.get('longitude')

        if lat is None or lng is None:
            filtered_businesses[place_id] = biz
        elif is_in_boundary(lat, lng, filter_boundary):
            filtered_businesses[place_id] = biz
        else:
            removed_count += 1

    all_businesses = filtered_businesses

    if verbose:
        print(f"\n  Before filtering: {before_filter}")
        print(f"  Removed (outside boundary): {removed_count}")
        print(f"  After filtering: {len(all_businesses)}")

    # Update CSV with filtered results (rewrite with only filtered)
    if output_csv:
        write_csv_header(output_csv)
        append_to_csv(output_csv, list(all_businesses.values()), csv_lock)
        if verbose:
            print(f"  CSV updated with filtered results")

    # Enrichment
    if (enrich or enrich_reviews) and len(all_businesses) > 0:
        if verbose:
            print(f"\n{'='*70}")
            print("ENRICHING BUSINESSES")
            print("=" * 70)

        all_businesses = enrich_businesses(
            all_businesses,
            fetch_details=enrich,
            fetch_reviews_flag=enrich_reviews,
            reviews_limit=reviews_limit,
            verbose=verbose,
        )

        # Update CSV with enriched data
        if output_csv:
            write_csv_header(output_csv)
            append_to_csv(output_csv, list(all_businesses.values()), csv_lock)

    total_time = time.time() - start_time

    # Save JSON results
    result_data = {
        'metadata': {
            'area': area_name,
            'category': category,
            'boundary': {
                'name': filter_boundary.name,
                'north': filter_boundary.north,
                'south': filter_boundary.south,
                'east': filter_boundary.east,
                'west': filter_boundary.west,
            },
            'cell_size_meters': cell_size,
            'cells_queried': len(cells),
            'parallel_workers': parallel_workers,
            'enrichment': {
                'details_fetched': enrich,
                'reviews_fetched': enrich_reviews,
                'reviews_limit': reviews_limit if enrich_reviews else 0,
            },
        },
        'statistics': {
            'total_before_filter': before_filter,
            'removed_outside_boundary': removed_count,
            'total_collected': len(all_businesses),
            'search_time_seconds': round(search_time, 1),
            'total_time_seconds': round(total_time, 1),
        },
        'businesses': list(all_businesses.values()),
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result_data, f, indent=2, ensure_ascii=False)

    if verbose:
        print(f"\n{'='*70}")
        print("COLLECTION COMPLETE")
        print("=" * 70)
        print(f"\n  Total businesses: {len(all_businesses)}")
        print(f"  Search time: {search_time:.1f}s")
        print(f"  Total time: {total_time:.1f}s")
        print(f"  JSON output: {output_file}")
        if output_csv:
            print(f"  CSV output: {output_csv}")

    return all_businesses
