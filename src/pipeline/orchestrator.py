from __future__ import annotations

import uuid
from datetime import datetime

from rich.console import Console

from src.db.migrations import init_db
from src.db.queries import insert_scrape_log, upsert_offers
from src.models.schema import ScrapedResult, ScrapeLogEntry, ScrapeStatus, Source
from src.pipeline.normalizer import normalize_offers
from src.scrapers.base import BaseScraper
from src.scrapers.pracapl import PracaPLScraper

console = Console()

SCRAPER_REGISTRY: dict[Source, type[BaseScraper]] = {
    Source.PRACAPL: PracaPLScraper,
}


def run_pipeline(
    sources: list[Source] | None = None,
    max_pages: int | None = None,
    fetch_details: bool = False,
) -> dict[Source, ScrapeLogEntry]:
    """Run the full scrape → normalize → store pipeline for given sources."""
    init_db()

    if sources is None:
        sources = list(SCRAPER_REGISTRY.keys())

    run_id = uuid.uuid4().hex[:12]
    results: dict[Source, ScrapeLogEntry] = {}

    console.rule(f"[bold blue]JobDB Pipeline — Run {run_id}")

    for source in sources:
        scraper_cls = SCRAPER_REGISTRY.get(source)
        if not scraper_cls:
            console.print(f"[yellow]Skipping {source.value}: no scraper registered[/]")
            continue

        log_entry = ScrapeLogEntry(
            run_id=run_id,
            source=source,
            started_at=datetime.utcnow(),
        )

        try:
            with scraper_cls(max_pages=max_pages) as scraper:
                result: ScrapedResult = scraper.scrape()

                # Optionally fetch detail pages
                if fetch_details and result.offers:
                    console.print(f"  Fetching details for {len(result.offers)} offers...")
                    for i, offer in enumerate(result.offers):
                        try:
                            result.offers[i] = scraper.scrape_detail(offer)
                            scraper._wait()
                        except Exception:
                            result.errors += 1

                # Normalize
                console.print("  Normalizing...")
                normalized = normalize_offers(result.offers)

                # Store
                console.print("  Storing to DuckDB...")
                new_count, updated_count = upsert_offers(normalized)

                log_entry.offers_scraped = len(normalized)
                log_entry.offers_new = new_count
                log_entry.offers_updated = updated_count
                log_entry.errors = result.errors
                log_entry.status = result.status

                console.print(f"  [green]Done: {new_count} new, {updated_count} updated, {result.errors} errors[/]")

        except Exception as e:
            console.print(f"  [bold red]Pipeline failed for {source.value}: {e}[/]")
            log_entry.status = ScrapeStatus.FAILED
            log_entry.errors += 1

        finally:
            log_entry.finished_at = datetime.utcnow()
            insert_scrape_log(log_entry)
            results[source] = log_entry

    console.rule("[bold blue]Pipeline Complete")

    # Print summary
    for source, log in results.items():
        emoji = "✓" if log.status == ScrapeStatus.SUCCESS else "✗"
        console.print(
            f"  {emoji} {source.value}: {log.offers_scraped} scraped, "
            f"{log.offers_new} new, {log.offers_updated} updated"
        )

    return results
