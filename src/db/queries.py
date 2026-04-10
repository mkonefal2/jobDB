from __future__ import annotations

import json
from datetime import date, datetime

from src.db.database import get_connection
from src.models.schema import JobOffer, ScrapeLogEntry


def upsert_offers(offers: list[JobOffer]) -> tuple[int, int]:
    """Insert new offers or update existing ones. Returns (new_count, updated_count)."""
    conn = get_connection()
    cursor = conn.cursor()
    new_count = 0
    updated_count = 0
    now = datetime.utcnow()

    for offer in offers:
        cursor.execute("SELECT id FROM job_offers WHERE id = %s", (offer.id,))
        existing = cursor.fetchone()

        if existing is None:
            cursor.execute(
                """INSERT INTO job_offers (
                    id, source, source_id, source_url, title, company_name,
                    location_raw, location_city, location_region, work_mode,
                    seniority, employment_type,
                    salary_min, salary_max, salary_currency, salary_period, salary_type,
                    category, technologies, description_text,
                    published_at, first_seen_at, last_seen_at, is_active, scraped_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, true, %s)""",
                (
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
                    json.dumps(offer.technologies) if offer.technologies else None,
                    offer.description_text,
                    offer.published_at,
                    now,
                    now,
                    offer.scraped_at,
                ),
            )
            new_count += 1
        else:
            cursor.execute(
                """UPDATE job_offers SET
                    title = %s, company_name = %s,
                    salary_min = %s, salary_max = %s, salary_currency = %s, salary_period = %s,
                    salary_type = %s,
                    last_seen_at = %s, is_active = true, scraped_at = %s
                WHERE id = %s""",
                (
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
                ),
            )
            updated_count += 1

    conn.commit()
    cursor.close()
    return new_count, updated_count


def mark_inactive(source: str, active_ids: set[str]) -> int:
    """Mark offers not seen in this scrape as inactive. Returns count marked."""
    conn = get_connection()
    cursor = conn.cursor()
    if not active_ids:
        cursor.close()
        return 0

    placeholders = ", ".join(["%s"] * len(active_ids))
    cursor.execute(
        f"""UPDATE job_offers
            SET is_active = false
            WHERE source = %s AND is_active = true AND id NOT IN ({placeholders})""",
        (source, *active_ids),
    )
    affected = cursor.rowcount
    conn.commit()
    cursor.close()
    return affected


def insert_scrape_log(entry: ScrapeLogEntry) -> None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO scrape_log (
            run_id, source, started_at, finished_at,
            offers_scraped, offers_new, offers_updated, errors, status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            entry.run_id,
            entry.source.value,
            entry.started_at,
            entry.finished_at,
            entry.offers_scraped,
            entry.offers_new,
            entry.offers_updated,
            entry.errors,
            entry.status.value,
        ),
    )
    conn.commit()
    cursor.close()


def create_daily_snapshot(snapshot_date: date | None = None) -> int:
    """Create a snapshot of all active offers for the given date. Returns row count."""
    conn = get_connection()
    cursor = conn.cursor()
    d = snapshot_date or date.today()
    cursor.execute(
        """REPLACE INTO job_snapshots (snapshot_date, offer_id, salary_min, salary_max, is_active)
           SELECT %s, id, salary_min, salary_max, is_active
           FROM job_offers WHERE is_active = true""",
        (d,),
    )
    cursor.execute("SELECT count(*) FROM job_snapshots WHERE snapshot_date = %s", (d,))
    count = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    return count


def get_offer_count(source: str | None = None) -> int:
    conn = get_connection()
    cursor = conn.cursor()
    if source:
        cursor.execute(
            "SELECT count(*) FROM job_offers WHERE source = %s AND is_active = true", (source,)
        )
    else:
        cursor.execute("SELECT count(*) FROM job_offers WHERE is_active = true")
    result = cursor.fetchone()[0]
    cursor.close()
    return result


def get_stats_summary() -> dict:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            count(*) as total,
            SUM(is_active) as active,
            SUM(CASE WHEN salary_min IS NOT NULL THEN 1 ELSE 0 END) as with_salary,
            count(DISTINCT source) as sources,
            count(DISTINCT CASE WHEN location_city IS NOT NULL THEN location_city END) as cities
        FROM job_offers
    """)
    row = cursor.fetchone()
    cursor.close()
    return {
        "total": row[0],
        "active": int(row[1] or 0),
        "with_salary": int(row[2] or 0),
        "sources": row[3],
        "cities": row[4],
    }
