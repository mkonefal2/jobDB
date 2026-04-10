from __future__ import annotations

from src.db.database import get_connection

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS job_offers (
    id                VARCHAR PRIMARY KEY,
    source            VARCHAR NOT NULL,
    source_id         VARCHAR NOT NULL,
    source_url        VARCHAR NOT NULL,
    title             VARCHAR NOT NULL,
    company_name      VARCHAR,

    location_raw      VARCHAR,
    location_city     VARCHAR,
    location_region   VARCHAR,
    work_mode         VARCHAR DEFAULT 'unknown',

    seniority         VARCHAR DEFAULT 'unknown',
    employment_type   VARCHAR,

    salary_min        DOUBLE,
    salary_max        DOUBLE,
    salary_currency   VARCHAR,
    salary_period     VARCHAR,
    salary_type       VARCHAR,

    category          VARCHAR,
    technologies      VARCHAR[],
    description_text  VARCHAR,

    published_at      TIMESTAMP,
    first_seen_at     TIMESTAMP NOT NULL DEFAULT current_timestamp,
    last_seen_at      TIMESTAMP NOT NULL DEFAULT current_timestamp,
    is_active         BOOLEAN DEFAULT true,
    scraped_at        TIMESTAMP NOT NULL,
    dedup_cluster_id  VARCHAR,

    UNIQUE (source, source_id)
);

CREATE TABLE IF NOT EXISTS job_snapshots (
    snapshot_date  DATE NOT NULL,
    offer_id       VARCHAR NOT NULL,
    salary_min     DOUBLE,
    salary_max     DOUBLE,
    is_active      BOOLEAN NOT NULL,
    PRIMARY KEY (snapshot_date, offer_id)
);

CREATE TABLE IF NOT EXISTS daily_stats (
    stat_date          DATE NOT NULL,
    source             VARCHAR NOT NULL,
    category           VARCHAR,
    location_city      VARCHAR,
    total_offers       INTEGER DEFAULT 0,
    offers_with_salary INTEGER DEFAULT 0,
    avg_salary_min     DOUBLE,
    avg_salary_max     DOUBLE,
    new_offers         INTEGER DEFAULT 0,
    expired_offers     INTEGER DEFAULT 0,
    PRIMARY KEY (stat_date, source, category, location_city)
);

CREATE TABLE IF NOT EXISTS scrape_log (
    run_id          VARCHAR NOT NULL,
    source          VARCHAR NOT NULL,
    started_at      TIMESTAMP NOT NULL,
    finished_at     TIMESTAMP,
    offers_scraped  INTEGER DEFAULT 0,
    offers_new      INTEGER DEFAULT 0,
    offers_updated  INTEGER DEFAULT 0,
    errors          INTEGER DEFAULT 0,
    status          VARCHAR DEFAULT 'success'
);
"""


def init_db() -> None:
    conn = get_connection()
    conn.execute(SCHEMA_SQL)
    conn.commit()


def drop_all() -> None:
    conn = get_connection()
    for table in ["scrape_log", "daily_stats", "job_snapshots", "job_offers"]:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.commit()


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
