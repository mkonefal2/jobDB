"""Schedule daily job scraping via Windows Task Scheduler.

Usage:
    python scripts/schedule_scraper.py                  # run scrape now (all sources)
    python scripts/schedule_scraper.py --schedule       # register daily task (07:00)
    python scripts/schedule_scraper.py --schedule --time 09:30  # daily at 09:30
    python scripts/schedule_scraper.py --unschedule     # remove scheduled task
    python scripts/schedule_scraper.py --status         # check if task is registered
    python scripts/schedule_scraper.py -s pracapl pracujpl  # scrape specific sources
    python scripts/schedule_scraper.py --details        # fetch detail pages too
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.models.schema import Source
from src.pipeline.orchestrator import run_pipeline

TASK_NAME = "JobDB_DailyScrape"
LOG_DIR = PROJECT_ROOT / "data" / "logs"

SOURCE_CHOICES = [s.value for s in Source]


def _setup_logging() -> logging.Logger:
    """Configure file + console logging for scheduled runs."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"scrape_{datetime.now():%Y%m%d_%H%M%S}.log"

    logger = logging.getLogger("jobdb.scheduler")
    logger.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger


def run_scrape(
    sources: list[Source] | None = None,
    max_pages: int | None = None,
    fetch_details: bool = False,
) -> None:
    """Execute the scraping pipeline with logging."""
    logger = _setup_logging()
    logger.info("Scheduled scrape started")

    src_names = ", ".join(s.value for s in sources) if sources else "all"
    logger.info("Sources: %s | max_pages: %s | details: %s", src_names, max_pages, fetch_details)

    try:
        results = run_pipeline(sources=sources, max_pages=max_pages, fetch_details=fetch_details)

        for source, log in results.items():
            logger.info(
                "%s: %d scraped, %d new, %d updated, %d errors, status=%s",
                source.value,
                log.offers_scraped,
                log.offers_new,
                log.offers_updated,
                log.errors,
                log.status.value,
            )
        logger.info("Scrape completed successfully")

    except Exception:
        logger.exception("Scrape failed with unhandled error")
        sys.exit(1)

    _cleanup_old_logs(keep=30)


def _cleanup_old_logs(keep: int = 30) -> None:
    """Remove old log files, keeping the most recent `keep`."""
    if not LOG_DIR.exists():
        return
    logs = sorted(LOG_DIR.glob("scrape_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in logs[keep:]:
        old.unlink()


def schedule_task(time_str: str = "07:00") -> None:
    """Register a Windows scheduled task for daily scraping."""
    python_exe = sys.executable
    script_path = Path(__file__).resolve()

    cmd = [
        "schtasks",
        "/Create",
        "/F",
        "/TN",
        TASK_NAME,
        "/TR",
        f'"{python_exe}" "{script_path}"',
        "/SC",
        "DAILY",
        "/ST",
        time_str,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"Scheduled task '{TASK_NAME}' created (daily at {time_str}).")
        print(f"  Python: {python_exe}")
        print(f"  Script: {script_path}")
    else:
        print(f"Failed to create task: {result.stderr.strip()}")
        print("Hint: run as Administrator if permission denied.")
        sys.exit(1)


def unschedule_task() -> None:
    """Remove the Windows scheduled task."""
    result = subprocess.run(
        ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(f"Scheduled task '{TASK_NAME}' removed.")
    else:
        print(f"Failed to remove task: {result.stderr.strip()}")


def show_status() -> None:
    """Check if the scheduled task exists and show its status."""
    result = subprocess.run(
        ["schtasks", "/Query", "/TN", TASK_NAME, "/FO", "LIST", "/V"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(result.stdout)
    else:
        print(f"Task '{TASK_NAME}' is not registered.")


def main() -> None:
    parser = argparse.ArgumentParser(description="JobDB — scheduled daily scraping")
    parser.add_argument(
        "-s",
        "--sources",
        nargs="*",
        choices=SOURCE_CHOICES,
        help=f"Sources to scrape. Available: {', '.join(SOURCE_CHOICES)}. Default: all.",
    )
    parser.add_argument(
        "-p",
        "--max-pages",
        type=int,
        default=None,
        help="Max listing pages per source (default: unlimited)",
    )
    parser.add_argument(
        "-d",
        "--details",
        action="store_true",
        help="Fetch detail pages for each offer",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Register Windows scheduled task for daily scraping",
    )
    parser.add_argument(
        "--unschedule",
        action="store_true",
        help="Remove Windows scheduled task",
    )
    parser.add_argument(
        "--time",
        default="07:00",
        help="Time for daily scheduled run (HH:MM, default: 07:00)",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show scheduled task status",
    )

    args = parser.parse_args()

    if args.schedule:
        schedule_task(args.time)
        return

    if args.unschedule:
        unschedule_task()
        return

    if args.status:
        show_status()
        return

    sources = [Source(s) for s in args.sources] if args.sources else None
    run_scrape(sources=sources, max_pages=args.max_pages, fetch_details=args.details)


if __name__ == "__main__":
    main()
