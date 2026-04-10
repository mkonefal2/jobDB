from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models.schema import Source
from src.pipeline.orchestrator import run_pipeline

SOURCE_CHOICES = [s.value for s in Source]


def main():
    parser = argparse.ArgumentParser(description="JobDB — scrape job offers from Polish portals")
    parser.add_argument(
        "-s",
        "--sources",
        nargs="*",
        choices=SOURCE_CHOICES,
        help=f"Sources to scrape. Available: {', '.join(SOURCE_CHOICES)}. Default: all registered.",
    )
    parser.add_argument(
        "-p",
        "--max-pages",
        type=int,
        default=None,
        help="Maximum number of listing pages to scrape per source (default: unlimited)",
    )
    parser.add_argument(
        "-d",
        "--details",
        action="store_true",
        help="Fetch detail pages for each offer (slower but more data)",
    )

    args = parser.parse_args()

    sources = [Source(s) for s in args.sources] if args.sources else None

    run_pipeline(
        sources=sources,
        max_pages=args.max_pages,
        fetch_details=args.details,
    )


if __name__ == "__main__":
    main()
