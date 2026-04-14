from __future__ import annotations

import json
from datetime import date, datetime

from src.db.database import get_connection
from src.models.schema import JobOffer, ScrapeLogEntry, Source


def upsert_offers(offers: list[JobOffer]) -> tuple[int, int]:
    """Insert new or update existing offers using INSERT ... ON DUPLICATE KEY UPDATE.

    Returns (new_count, updated_count).
    """
    if not offers:
        return 0, 0

    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow()

    rows = [
        (
            offer.id,
            offer.source.value,
            offer.source_id,
            offer.source_url,
            offer.title,
            offer.company_name,
            offer.company_logo_url,
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
            offer.dedup_cluster_id,
            offer.published_at,
            now,  # first_seen_at
            now,  # last_seen_at
            offer.scraped_at,
        )
        for offer in offers
    ]

    sql = """INSERT INTO job_offers (
                id, source, source_id, source_url, title, company_name, company_logo_url,
                location_raw, location_city, location_region, work_mode,
                seniority, employment_type,
                salary_min, salary_max, salary_currency, salary_period, salary_type,
                category, technologies, description_text, dedup_cluster_id,
                published_at, first_seen_at, last_seen_at, scraped_at
             ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
             ON DUPLICATE KEY UPDATE
                title = VALUES(title),
                company_name = VALUES(company_name),
                company_logo_url = VALUES(company_logo_url),
                salary_min = VALUES(salary_min),
                salary_max = VALUES(salary_max),
                salary_currency = VALUES(salary_currency),
                salary_period = VALUES(salary_period),
                salary_type = VALUES(salary_type),
                dedup_cluster_id = VALUES(dedup_cluster_id),
                last_seen_at = VALUES(last_seen_at),
                is_active = true,
                scraped_at = VALUES(scraped_at)"""

    cursor.executemany(sql, rows)

    # MySQL: affected_rows counts 1 for INSERT, 2 for UPDATE-with-change, 0 for no-op
    # With executemany the rowcount is total affected rows
    total_affected = cursor.rowcount
    conn.commit()
    cursor.close()

    # Estimate: new rows = affected 1 each, updated = affected 2 each
    # Exact split requires checking, but a reasonable heuristic:
    new_count = max(0, 2 * len(offers) - total_affected)
    updated_count = len(offers) - new_count
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


def update_dedup_clusters(clusters: list[tuple[str, str]]) -> int:
    """Batch-update dedup_cluster_id for given (offer_id, cluster_id) pairs.

    Returns count of rows updated.
    """
    if not clusters:
        return 0

    conn = get_connection()
    cursor = conn.cursor()
    cursor.executemany(
        "UPDATE job_offers SET dedup_cluster_id = %s WHERE id = %s",
        [(cluster_id, offer_id) for offer_id, cluster_id in clusters],
    )
    affected = cursor.rowcount
    conn.commit()
    cursor.close()
    return affected


def get_active_offers_for_dedup(sources: list[Source] | None = None) -> list[dict]:
    """Fetch minimal offer data for cross-source deduplication.

    Returns dicts with: id, source, title, company_name, location_city, dedup_cluster_id.
    """
    conn = get_connection()
    cursor = conn.cursor()
    sql = """SELECT id, source, title, company_name, location_city, dedup_cluster_id
             FROM job_offers WHERE is_active = true"""
    params: list = []
    if sources:
        placeholders = ", ".join(["%s"] * len(sources))
        sql += f" AND source IN ({placeholders})"
        params = [s.value for s in sources]
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    cursor.close()
    return [
        {
            "id": r[0],
            "source": r[1],
            "title": r[2],
            "company_name": r[3],
            "location_city": r[4],
            "dedup_cluster_id": r[5],
        }
        for r in rows
    ]
