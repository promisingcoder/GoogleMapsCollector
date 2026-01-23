"""
Command Line Interface

Entry point for running the collector from command line.

Usage:
    python -m gmaps_extractor "New York, USA" "lawyers"
    python -m gmaps_extractor "Paris, France" "restaurants" --enrich --reviews
    python -m gmaps_extractor "Manhattan, NY" "lawyers" --parallel 10
"""

import argparse
import sys

from .extraction import collect_businesses
from .config import DEFAULT_PARALLEL_WORKERS, MAX_PARALLEL_WORKERS


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Google Maps Business Extractor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m gmaps_extractor "New York, USA" "lawyers"
  python -m gmaps_extractor "Paris, France" "restaurants" --enrich
  python -m gmaps_extractor "Tokyo, Japan" "hotels" --enrich --reviews --reviews-limit 10
  python -m gmaps_extractor "Manhattan, NY" "lawyers" --parallel 10
  python -m gmaps_extractor "London, UK" "cafes" -o my_output.json --no-csv
        """
    )

    # Required arguments
    parser.add_argument(
        "area",
        help="Area to search (e.g., 'New York, USA', 'Paris, France')"
    )
    parser.add_argument(
        "category",
        help="Business category to search (e.g., 'lawyers', 'restaurants')"
    )

    # Optional arguments
    parser.add_argument(
        "-o", "--output",
        help="Output JSON file path (default: output/{category}_in_{area}.json)"
    )
    parser.add_argument(
        "--csv",
        help="Output CSV file path (default: output/{category}_in_{area}.csv)"
    )
    parser.add_argument(
        "--no-csv",
        action="store_true",
        help="Disable CSV output"
    )
    parser.add_argument(
        "-b", "--buffer",
        type=float,
        default=5.0,
        help="Buffer in km for coordinate filtering (default: 5.0)"
    )
    parser.add_argument(
        "-p", "--parallel",
        type=int,
        default=DEFAULT_PARALLEL_WORKERS,
        help=f"Number of parallel workers (default: {DEFAULT_PARALLEL_WORKERS}, max: {MAX_PARALLEL_WORKERS})"
    )
    parser.add_argument(
        "--enrich",
        action="store_true",
        help="Fetch detailed place information (hours, photos, etc.)"
    )
    parser.add_argument(
        "--reviews",
        action="store_true",
        help="Fetch reviews for each business"
    )
    parser.add_argument(
        "--reviews-limit",
        type=int,
        default=5,
        help="Number of reviews to fetch per business (default: 5)"
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress progress output"
    )

    args = parser.parse_args()

    # Handle CSV output
    output_csv = args.csv
    if args.no_csv:
        output_csv = False

    try:
        businesses = collect_businesses(
            area_name=args.area,
            category=args.category,
            buffer_km=args.buffer,
            enrich=args.enrich,
            enrich_reviews=args.reviews,
            reviews_limit=args.reviews_limit,
            output_file=args.output,
            output_csv=output_csv,
            parallel_workers=args.parallel,
            verbose=not args.quiet,
        )

        if not args.quiet:
            print(f"\nDone! Collected {len(businesses)} businesses.")

        return 0

    except RuntimeError as e:
        print(f"\nError: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
