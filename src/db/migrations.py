from __future__ import annotations

from src.db.database import get_connection

SCHEMA_SQLS = [
    """
    CREATE TABLE IF NOT EXISTS job_offers (
        id                VARCHAR(64) PRIMARY KEY,
        source            VARCHAR(50) NOT NULL,
        source_id         VARCHAR(255) NOT NULL,
        source_url        VARCHAR(2048) NOT NULL,
        title             VARCHAR(500) NOT NULL,
        company_name      VARCHAR(500),
        company_logo_url  VARCHAR(2048),

        location_raw      VARCHAR(500),
        location_city     VARCHAR(255),
        location_region   VARCHAR(255),
        work_mode         VARCHAR(50) DEFAULT 'unknown',

        seniority         VARCHAR(50) DEFAULT 'unknown',
        employment_type   VARCHAR(100),

        salary_min        DOUBLE,
        salary_max        DOUBLE,
        salary_currency   VARCHAR(10),
        salary_period     VARCHAR(20),
        salary_type       VARCHAR(20),

        category          VARCHAR(255),
        technologies      JSON,
        description_text  LONGTEXT,

        published_at      DATETIME,
        first_seen_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        last_seen_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        is_active         BOOLEAN DEFAULT true,
        scraped_at        DATETIME NOT NULL,
        dedup_cluster_id  VARCHAR(64),

        UNIQUE KEY uq_source_source_id (source, source_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS job_snapshots (
        snapshot_date  DATE NOT NULL,
        offer_id       VARCHAR(64) NOT NULL,
        salary_min     DOUBLE,
        salary_max     DOUBLE,
        is_active      BOOLEAN NOT NULL,
        PRIMARY KEY (snapshot_date, offer_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS daily_stats (
        stat_date          DATE NOT NULL,
        source             VARCHAR(50) NOT NULL,
        category           VARCHAR(255) NOT NULL DEFAULT '',
        location_city      VARCHAR(255) NOT NULL DEFAULT '',
        total_offers       INT DEFAULT 0,
        offers_with_salary INT DEFAULT 0,
        avg_salary_min     DOUBLE,
        avg_salary_max     DOUBLE,
        new_offers         INT DEFAULT 0,
        expired_offers     INT DEFAULT 0,
        PRIMARY KEY (stat_date, source, category, location_city)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS scrape_log (
        run_id          VARCHAR(64) NOT NULL,
        source          VARCHAR(50) NOT NULL,
        started_at      DATETIME NOT NULL,
        finished_at     DATETIME,
        offers_scraped  INT DEFAULT 0,
        offers_new      INT DEFAULT 0,
        offers_updated  INT DEFAULT 0,
        errors          INT DEFAULT 0,
        status          VARCHAR(50) DEFAULT 'success',
        KEY idx_scrape_log_started (started_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
]


def init_db() -> None:
    conn = get_connection()
    cursor = conn.cursor()
    for sql in SCHEMA_SQLS:
        cursor.execute(sql)
    conn.commit()
    cursor.close()


def drop_all() -> None:
    conn = get_connection()
    cursor = conn.cursor()
    for table in ["scrape_log", "daily_stats", "job_snapshots", "job_offers"]:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")
    conn.commit()
    cursor.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
