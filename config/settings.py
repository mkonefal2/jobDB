import os
from pathlib import Path

from dotenv import load_dotenv

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")
DATA_DIR = PROJECT_ROOT / "data"
EXPORTS_DIR = DATA_DIR / "exports"

# MySQL (override via environment variables)
MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", "root"),
    "database": os.getenv("MYSQL_DATABASE", "jobdb"),
}

# Scraping
DEFAULT_DELAY_SECONDS = 2.0
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    " (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
]

# Sources
SOURCES = {
    "pracapl": {
        "name": "praca.pl",
        "base_url": "https://www.praca.pl",
        "delay": 2.0,
    },
    "justjoinit": {
        "name": "justjoin.it",
        "base_url": "https://justjoin.it",
        "delay": 1.5,
    },
    "rocketjobs": {
        "name": "rocketjobs.pl",
        "base_url": "https://rocketjobs.pl",
        "delay": 1.5,
    },
    "pracuj": {
        "name": "pracuj.pl",
        "base_url": "https://www.pracuj.pl",
        "delay": 3.0,
    },
    "nofluffjobs": {
        "name": "nofluffjobs.com",
        "base_url": "https://nofluffjobs.com",
        "delay": 1.0,
    },
    # "jooble" disabled — aggregator that duplicates offers from other sources
    # "jooble": {
    #     "name": "jooble.org",
    #     "base_url": "https://pl.jooble.org",
    #     "delay": 2.5,
    # },
}

# Playwright settings (for browser-based scrapers)
PLAYWRIGHT_GOTO_TIMEOUT = 60_000  # ms — page.goto() timeout
PLAYWRIGHT_SELECTOR_TIMEOUT = 15_000  # ms — wait_for_selector() timeout
PLAYWRIGHT_MAX_RETRIES = 3  # retry attempts for page fetch
