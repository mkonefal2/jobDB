from __future__ import annotations

from datetime import date, datetime

from src.db.database import get_connection
from src.models.schema import JobOffer, ScrapeLogEntry


def upsert_offers(offers: list[JobOffer]) -> tuple[int, int]:
    """Insert new offers or update existing ones. Returns (new_count, updated_count)."""
    conn = get_connection()
    new_count = 0
    updated_count = 0
    now = datetime.utcnow()

    for offer in offers:
        existing = conn.execute("SELECT id FROM job_offers WHERE id = ?", [offer.id]).fetchone()

        if existing is None:
            conn.execute(
                """INSERT INTO job_offers (
                    id, source, source_id, source_url, title, company_name,
                    location_raw, location_city, location_region, work_mode,
                    seniority, employment_type,
                    salary_min, salary_max, salary_currency, salary_period, salary_type,
                    category, technologies, description_text,
                    published_at, first_seen_at, last_seen_at, is_active, scraped_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, true, ?)""",
                [
                    offer.id,
                    offer.source.value,
                    offer.source_id,
                    offer.source_url,
                    offer.title,
                    offer.company_name,
                    offer.location_raw,
                    offer.location_city,
                    offer.location_region,
                    offer.work_mode.value,
                    offer.seniority.value,
                    offer.employment_type,
                    offer.salary_min,
                    offer.salary_max,
                    offer.salary_currency,
                    offer.salary_period.value if offer.salary_period else None,
                    offer.salary_type,
                    offer.category,
                    offer.technologies,
                    offer.description_text,
                    offer.published_at,
                    now,
                    now,
                    offer.scraped_at,
                ],
            )
            new_count += 1
        else:
            conn.execute(
                """UPDATE job_offers SET
                    title = ?, company_name = ?,
                    salary_min = ?, salary_max = ?, salary_currency = ?, salary_period = ?,
                    salary_type = ?,
                    last_seen_at = ?, is_active = true, scraped_at = ?
                WHERE id = ?""",
                [
                    offer.title,
                    offer.company_name,
                    offer.salary_min,
                    offer.salary_max,
                    offer.salary_currency,
                    offer.salary_period.value if offer.salary_period else None,
                    offer.salary_type,
                    now,
                    offer.scraped_at,
                    offer.id,
                ],
            )
            updated_count += 1

    conn.commit()
    return new_count, updated_count


def mark_inactive(source: str, active_ids: set[str]) -> int:
    """Mark offers not seen in this scrape as inactive. Returns count marked."""
    conn = get_connection()
    if not active_ids:
        return 0

    placeholders = ", ".join(["?"] * len(active_ids))
    result = conn.execute(
        f"""UPDATE job_offers
            SET is_active = false
            WHERE source = ? AND is_active = true AND id NOT IN ({placeholders})""",
        [source, *active_ids],
    )
    conn.commit()
    return result.fetchone()[0] if result else 0


def insert_scrape_log(entry: ScrapeLogEntry) -> None:
    conn = get_connection()
    conn.execute(
        """INSERT INTO scrape_log (
            run_id, source, started_at, finished_at,
            offers_scraped, offers_new, offers_updated, errors, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            entry.run_id,
            entry.source.value,
            entry.started_at,
            entry.finished_at,
            entry.offers_scraped,
            entry.offers_new,
            entry.offers_updated,
            entry.errors,
            entry.status.value,
        ],
    )
    conn.commit()


def create_daily_snapshot(snapshot_date: date | None = None) -> int:
    """Create a snapshot of all active offers for the given date. Returns row count."""
    conn = get_connection()
    d = snapshot_date or date.today()
    conn.execute(
        """INSERT OR REPLACE INTO job_snapshots (snapshot_date, offer_id, salary_min, salary_max, is_active)
           SELECT ?, id, salary_min, salary_max, is_active
           FROM job_offers WHERE is_active = true""",
        [d],
    )
    count = conn.execute("SELECT count(*) FROM job_snapshots WHERE snapshot_date = ?", [d]).fetchone()[0]
    conn.commit()
    return count


def get_offer_count(source: str | None = None) -> int:
    conn = get_connection()
    if source:
        return conn.execute(
            "SELECT count(*) FROM job_offers WHERE source = ? AND is_active = true", [source]
        ).fetchone()[0]
    return conn.execute("SELECT count(*) FROM job_offers WHERE is_active = true").fetchone()[0]


def get_stats_summary() -> dict:
    conn = get_connection()
    row = conn.execute("""
        SELECT
            count(*) as total,
            count(*) FILTER (WHERE is_active) as active,
            count(*) FILTER (WHERE salary_min IS NOT NULL) as with_salary,
            count(DISTINCT source) as sources,
            count(DISTINCT location_city) FILTER (WHERE location_city IS NOT NULL) as cities
        FROM job_offers
    """).fetchone()
    return {
        "total": row[0],
        "active": row[1],
        "with_salary": row[2],
        "sources": row[3],
        "cities": row[4],
    }
