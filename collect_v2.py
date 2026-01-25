#!/usr/bin/env python3
"""
Enhanced Business Collector CLI (V2)

Features:
- Checkpoint saves for resumability
- Adaptive rate limiting with exponential backoff
- Retry queue for failed cells
- Streams to disk (memory efficient for large collections)
- Parallel enrichment

Usage:
    python collect_v2.py "New York, USA" "lawyers"
    python collect_v2.py "Paris, France" "restaurants" --enrich --reviews -l 50
    python collect_v2.py "London, UK" "hotels" --resume  # Resume interrupted collection
"""

import sys
import argparse

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

from gmaps_extractor.extraction.collector_v2 import collect_businesses_v2


def main():
    parser = argparse.ArgumentParser(
        description="Collect businesses from Google Maps (Enhanced V2)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python collect_v2.py "Manhattan, New York" "lawyers"
  python collect_v2.py "Los Angeles, CA" "restaurants" --enrich --reviews -l 100
  python collect_v2.py "Chicago, IL" "hotels" --workers 30 --enrich-workers 10
  python collect_v2.py "Boston, MA" "dentists" --resume  # Resume from checkpoint
        """
    )

    parser.add_argument("area", help="Area name (e.g., 'New York, USA')")
    parser.add_argument("category", help="Business category (e.g., 'lawyers')")

    parser.add_argument("-b", "--buffer", type=float, default=5.0,
                        help="Buffer in km for boundary filtering (default: 5.0)")

    parser.add_argument("--enrich", action="store_true",
                        help="Fetch detailed place information")
    parser.add_argument("--reviews", action="store_true",
                        help="Fetch reviews for each business")
    parser.add_argument("-l", "--reviews-limit", type=int, default=20,
                        help="Max reviews per business (default: 20)")

    parser.add_argument("-w", "--workers", type=int, default=20,
                        help="Parallel workers for cell queries (default: 20)")
    parser.add_argument("--enrich-workers", type=int, default=5,
                        help="Parallel workers for enrichment (default: 5)")

    parser.add_argument("-c", "--checkpoint", type=int, default=100,
                        help="Checkpoint every N businesses (default: 100)")
    parser.add_argument("--resume", action="store_true", default=True,
                        help="Resume from checkpoint if available (default: True)")
    parser.add_argument("--no-resume", action="store_true",
                        help="Start fresh, ignore existing checkpoint")

    parser.add_argument("--subdivide", action="store_true",
                        help="Use subdivision mode (search sub-areas for better coverage)")

    parser.add_argument("-o", "--output", type=str, default=None,
                        help="Output JSON file path")
    parser.add_argument("--csv", type=str, default=None,
                        help="Output CSV file path")

    parser.add_argument("-q", "--quiet", action="store_true",
                        help="Suppress progress output")

    args = parser.parse_args()

    # Handle resume flag
    resume = not args.no_resume

    try:
        result = collect_businesses_v2(
            area_name=args.area,
            category=args.category,
            buffer_km=args.buffer,
            enrich=args.enrich,
            enrich_reviews=args.reviews,
            reviews_limit=args.reviews_limit,
            output_file=args.output,
            output_csv=args.csv,
            parallel_workers=args.workers,
            enrichment_workers=args.enrich_workers,
            checkpoint_interval=args.checkpoint,
            resume=resume,
            subdivide=args.subdivide,
            verbose=not args.quiet,
        )

        print(f"\nDone! Collected {result['statistics']['total_collected']} businesses")

    except KeyboardInterrupt:
        print("\n\nInterrupted! Progress saved to checkpoint.")
        print("Run with --resume to continue from where you left off.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
