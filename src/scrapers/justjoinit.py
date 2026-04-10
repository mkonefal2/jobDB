from __future__ import annotations

from config.settings import SOURCES
from src.models.schema import Source
from src.scrapers._justjoin_base import JustJoinBaseScraper

# JustJoin.it categoryId → human-readable name
_CATEGORY_MAP = {
    1: "JavaScript",
    2: "HTML",
    3: "PHP",
    4: "Ruby",
    5: "Python",
    6: "Java",
    7: ".NET",
    8: "Scala",
    9: "C",
    10: "Mobile",
    11: "Testing",
    12: "DevOps",
    13: "Admin",
    14: "UX/UI",
    15: "PM",
    16: "Game",
    17: "Analytics",
    18: "Security",
    19: "Data",
    20: "Go",
    21: "Support",
    22: "ERP",
    23: "Architecture",
    24: "Other",
    25: "AI",
}


class JustJoinITScraper(JustJoinBaseScraper):
    source = Source.JUSTJOINIT
    base_url = SOURCES["justjoinit"]["base_url"]
    delay = SOURCES["justjoinit"]["delay"]

    api_url = "https://api.justjoin.it/v2/user-panel/offers"
    offer_url_prefix = "https://justjoin.it/job-offer/"
    category_map = _CATEGORY_MAP
