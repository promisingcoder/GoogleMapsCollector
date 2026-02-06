"""
Reviews Enrichment CLI

Entry point for the gmaps-enrich-reviews console script.
Mirrors the top-level enrich_reviews_only.py for pip-installed usage.
"""

import sys
import json
import time
import random
import argparse

from .extraction.enrichment import fetch_reviews


def enrich_reviews(
    input_file: str,
    output_file: str,
    reviews_limit: int = 100,
    batch_size: int = 5,
    batch_delay: float = 1.5,
    save_interval: int = 100,
    page_size: int = 10,
    page_delay: float = 0.5,
):
    """Add reviews to existing collection using batch processing with pagination.

    Args:
        input_file: Path to JSON file from a previous collection.
        output_file: Path to save enriched JSON output.
        reviews_limit: Total reviews to fetch per business.
        batch_size: Requests per batch (unused, kept for API compat).
        batch_delay: Delay between businesses (seconds).
        save_interval: Save progress every N businesses.
        page_size: Reviews per API request (max 20).
        page_delay: Delay between pagination requests within same business.
    """
    print(f"Loading {input_file}...")
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    businesses = data['businesses']
    total = len(businesses)

    print(f"Found {total} businesses")
    print(f"Fetching up to {reviews_limit} reviews per business")
    print(f"Page size: {page_size}, delay between pages: {page_delay}s")
    print(f"Delay between businesses: {batch_delay}s")
    print(f"Saving every {save_interval} businesses")
    print()

    success_count = 0
    no_reviews_count = 0
    error_count = 0
    start_time = time.time()

    for i, biz in enumerate(businesses):
        raw_name = biz.get('name', 'Unknown')[:35]
        name = raw_name.encode('ascii', 'replace').decode('ascii')
        hex_id = biz.get('hex_id')

        elapsed = time.time() - start_time
        rate = (i + 1) / elapsed if elapsed > 0 else 0
        eta = (total - i - 1) / rate if rate > 0 else 0

        if not hex_id:
            print(f"[{i+1}/{total}] {name:35} SKIP (no hex_id)     ({rate:.1f}/s, ETA: {eta:.0f}s)")
            continue

        if biz.get('reviews_data'):
            print(f"[{i+1}/{total}] {name:35} SKIP (already done)  ({rate:.1f}/s, ETA: {eta:.0f}s)")
            success_count += 1
            continue

        try:
            result = fetch_reviews(
                place_id=biz.get('place_id', ''),
                hex_id=hex_id,
                limit=reviews_limit,
                page_size=page_size,
                page_delay=page_delay,
            )

            if result.get('reviews'):
                biz['reviews_data'] = result['reviews']
                status = f"OK {len(result['reviews'])} reviews"
                success_count += 1
            else:
                status = "- no reviews"
                no_reviews_count += 1

        except Exception as e:
            status = f"ERR: {str(e)[:15]}"
            error_count += 1

        print(f"[{i+1}/{total}] {name:35} {status:20} ({rate:.1f}/s, ETA: {eta:.0f}s)")

        jitter = random.uniform(0.5, 1.5)
        actual_delay = batch_delay * jitter
        time.sleep(actual_delay)

        if (i + 1) % save_interval == 0:
            print(f"    >> Saving progress ({success_count} with reviews so far)...")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

    data.setdefault('metadata', {}).setdefault('enrichment', {})
    data['metadata']['enrichment']['reviews_fetched'] = True
    data['metadata']['enrichment']['reviews_limit'] = reviews_limit

    print(f"\nSaving to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    total_time = time.time() - start_time
    print(f"\nDone in {total_time:.1f}s ({total_time/60:.1f} min)!")
    print(f"  With reviews: {success_count}")
    print(f"  No reviews: {no_reviews_count}")
    print(f"  Errors: {error_count}")
    print(f"  Output: {output_file}")


def main():
    """Main entry point for reviews enrichment CLI."""
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except AttributeError:
        pass

    parser = argparse.ArgumentParser(description="Add reviews to existing collection")
    parser.add_argument("input_file", help="Input JSON file from a previous collection")
    parser.add_argument("-o", "--output", default=None, help="Output file")
    parser.add_argument("-l", "--limit", type=int, default=100, help="Reviews per business")
    parser.add_argument("-b", "--batch-size", type=int, default=5, help="Requests per batch")
    parser.add_argument("-d", "--batch-delay", type=float, default=1.5, help="Delay between batches (seconds)")
    parser.add_argument("-s", "--save-interval", type=int, default=100, help="Save every N businesses")
    parser.add_argument("-p", "--page-size", type=int, default=10, help="Reviews per page (max 20)")
    parser.add_argument("--page-delay", type=float, default=0.5, help="Delay between pagination requests (seconds)")

    args = parser.parse_args()
    output_file = args.output or args.input_file.replace('.json', '_with_reviews.json')

    enrich_reviews(
        args.input_file,
        output_file,
        reviews_limit=args.limit,
        batch_size=args.batch_size,
        batch_delay=args.batch_delay,
        save_interval=args.save_interval,
        page_size=args.page_size,
        page_delay=args.page_delay,
    )


if __name__ == "__main__":
    main()
