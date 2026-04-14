from __future__ import annotations

import uuid
from datetime import datetime

from rich.console import Console

from src.db.migrations import init_db
from src.db.queries import (
    create_daily_snapshot,
    get_active_offers_for_dedup,
    insert_scrape_log,
    mark_inactive,
    update_dedup_clusters,
    upsert_offers,
)
from src.models.schema import JobOffer, ScrapedResult, ScrapeLogEntry, ScrapeStatus, Source
from src.pipeline.deduplicator import are_duplicates, compute_dedup_key, deduplicate_offers
from src.pipeline.normalizer import normalize_offers
from src.scrapers.base import BaseScraper
from src.scrapers.justjoinit import JustJoinITScraper
from src.scrapers.pracapl import PracaPLScraper
from src.scrapers.pracujpl import PracujPLScraper
from src.scrapers.rocketjobs import RocketJobsScraper

console = Console()

SCRAPER_REGISTRY: dict[Source, type[BaseScraper]] = {
    Source.PRACAPL: PracaPLScraper,
    Source.PRACUJ: PracujPLScraper,
    Source.JUSTJOINIT: JustJoinITScraper,
    Source.ROCKETJOBS: RocketJobsScraper,
    # Jooble disabled — aggregator that duplicates offers from primary sources
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
                console.print("  Storing to MySQL...")
                new_count, updated_count = upsert_offers(normalized)

                # Mark offers not seen in this scrape as inactive
                active_ids = {o.id for o in normalized}
                inactive_count = mark_inactive(source.value, active_ids)
                if inactive_count:
                    console.print(f"  [dim]{inactive_count} offers marked inactive[/]")

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

    # Global cross-source deduplication
    if len([s for s in results if results[s].status != ScrapeStatus.FAILED]) > 1:
        try:
            console.print("  [bold]Running cross-source deduplication...[/]")
            dedup_count = _run_global_dedup(sources)
            if dedup_count:
                console.print(f"  [green]{dedup_count} offers assigned to dedup clusters[/]")
        except Exception as e:
            console.print(f"  [yellow]Deduplication failed: {e}[/]")

    # Daily snapshot of active offers
    try:
        snapshot_count = create_daily_snapshot()
        console.print(f"  Daily snapshot: {snapshot_count} active offers captured")
    except Exception as e:
        console.print(f"  [yellow]Snapshot failed: {e}[/]")

    # Print summary
    for source, log in results.items():
        emoji = "✓" if log.status == ScrapeStatus.SUCCESS else "✗"
        console.print(
            f"  {emoji} {source.value}: {log.offers_scraped} scraped, "
            f"{log.offers_new} new, {log.offers_updated} updated"
        )

    return results


def _run_global_dedup(sources: list[Source]) -> int:
    """Run cross-source deduplication on active offers in the database.

    Fetches minimal offer data, runs dedup in-memory, then batch-updates
    dedup_cluster_id in the database. Returns count of offers tagged.
    """
    from collections import defaultdict

    rows = get_active_offers_for_dedup(sources)
    if len(rows) < 2:
        return 0

    # Build lightweight proxy objects for deduplication
    proxies: list[JobOffer] = []
    for r in rows:
        proxy = JobOffer(
            source=Source(r["source"]),
            source_id=r["id"],  # use offer id as source_id (only for dedup)
            source_url="",
            title=r["title"] or "",
            company_name=r["company_name"],
            location_city=r["location_city"],
            dedup_cluster_id=r["dedup_cluster_id"],
        )
        proxy._db_id = r["id"]  # type: ignore[attr-defined]
        proxies.append(proxy)

    deduplicate_offers(proxies)

    # Collect only newly assigned clusters
    updates: list[tuple[str, str]] = []
    for i, proxy in enumerate(proxies):
        if proxy.dedup_cluster_id and proxy.dedup_cluster_id != rows[i].get("dedup_cluster_id"):
            updates.append((proxy._db_id, proxy.dedup_cluster_id))  # type: ignore[attr-defined]

    if updates:
        update_dedup_clusters(updates)

    return len(updates)
