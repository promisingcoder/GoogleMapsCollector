"""
Package entry point.

Allows running: python -m gmaps_extractor "New York" "lawyers"
"""

from .cli import main

if __name__ == "__main__":
    main()
