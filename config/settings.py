from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
EXPORTS_DIR = DATA_DIR / "exports"

# MySQL
MYSQL_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "root",
    "database": "jobdb",
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
    # "jooble" disabled — aggregator that duplicates offers from other sources
    # "jooble": {
    #     "name": "jooble.org",
    #     "base_url": "https://pl.jooble.org",
    #     "delay": 2.5,
    # },
}
