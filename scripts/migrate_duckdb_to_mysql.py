"""One-time migration script: DuckDB → MySQL.

Reads all data from the existing DuckDB file and inserts it into the MySQL database.
Run once after setting up MySQL. Safe to re-run (uses INSERT IGNORE).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import duckdb
import mysql.connector

from config.settings import DB_PATH, MYSQL_CONFIG


def migrate():
    if not DB_PATH.exists():
        print(f"DuckDB file not found: {DB_PATH}")
        sys.exit(1)

    duck = duckdb.connect(str(DB_PATH), read_only=True)
    my = mysql.connector.connect(**MYSQL_CONFIG)
    cur = my.cursor()

    # ── job_offers ────────────────────────────────────────────────────────
    print("Migrating job_offers...")
    rows = duck.execute("""
        SELECT id, source, source_id, source_url, title, company_name,
               location_raw, location_city, location_region, work_mode,
               seniority, employment_type,
               salary_min, salary_max, salary_currency, salary_period, salary_type,
               category, technologies, description_text,
               published_at, first_seen_at, last_seen_at, is_active, scraped_at,
               dedup_cluster_id
        FROM job_offers
    """).fetchall()

    insert_sql = """
        INSERT IGNORE INTO job_offers (
            id, source, source_id, source_url, title, company_name,
            location_raw, location_city, location_region, work_mode,
            seniority, employment_type,
            salary_min, salary_max, salary_currency, salary_period, salary_type,
            category, technologies, description_text,
            published_at, first_seen_at, last_seen_at, is_active, scraped_at,
            dedup_cluster_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    count = 0
    for row in rows:
        row = list(row)
        # Convert technologies list to JSON string
        if row[18] is not None:
            row[18] = json.dumps(row[18]) if isinstance(row[18], list) else str(row[18])
        cur.execute(insert_sql, row)
        count += 1

    my.commit()
    print(f"  Inserted {count} job offers.")

    # ── scrape_log ────────────────────────────────────────────────────────
    print("Migrating scrape_log...")
    rows = duck.execute("""
        SELECT run_id, source, started_at, finished_at,
               offers_scraped, offers_new, offers_updated, errors, status
        FROM scrape_log
    """).fetchall()

    cur.executemany("""
        INSERT IGNORE INTO scrape_log (
            run_id, source, started_at, finished_at,
            offers_scraped, offers_new, offers_updated, errors, status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, rows)
    my.commit()
    print(f"  Inserted {len(rows)} scrape log entries.")

    # ── job_snapshots ─────────────────────────────────────────────────────
    print("Migrating job_snapshots...")
    rows = duck.execute("SELECT snapshot_date, offer_id, salary_min, salary_max, is_active FROM job_snapshots").fetchall()
    if rows:
        cur.executemany("""
            INSERT IGNORE INTO job_snapshots (snapshot_date, offer_id, salary_min, salary_max, is_active)
            VALUES (%s, %s, %s, %s, %s)
        """, rows)
        my.commit()
    print(f"  Inserted {len(rows)} snapshots.")

    # ── daily_stats ───────────────────────────────────────────────────────
    print("Migrating daily_stats...")
    rows = duck.execute("""
        SELECT stat_date, source, COALESCE(category, ''), COALESCE(location_city, ''),
               total_offers, offers_with_salary, avg_salary_min, avg_salary_max,
               new_offers, expired_offers
        FROM daily_stats
    """).fetchall()
    if rows:
        cur.executemany("""
            INSERT IGNORE INTO daily_stats (
                stat_date, source, category, location_city,
                total_offers, offers_with_salary, avg_salary_min, avg_salary_max,
                new_offers, expired_offers
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, rows)
        my.commit()
    print(f"  Inserted {len(rows)} daily stats entries.")

    # ── Verify ────────────────────────────────────────────────────────────
    cur.execute("SELECT count(*) FROM job_offers")
    mysql_count = cur.fetchone()[0]
    duck_count = duck.execute("SELECT count(*) FROM job_offers").fetchone()[0]
    print(f"\nVerification: DuckDB has {duck_count} offers, MySQL has {mysql_count} offers.")
    if mysql_count == duck_count:
        print("✅ Migration successful — counts match!")
    else:
        print("⚠️  Count mismatch — check for duplicates or errors.")

    cur.close()
    my.close()
    duck.close()


if __name__ == "__main__":
    migrate()
