from __future__ import annotations

from config.settings import SOURCES
from src.models.schema import Source
from src.scrapers._justjoin_base import JustJoinBaseScraper

# RocketJobs categoryId → human-readable name (non-IT job categories)
_CATEGORY_MAP = {
    2: "Marketing",
    3: "Sprzedaż",
    4: "SEM/SEO",
    5: "PR",
    6: "Copywriting",
    7: "E-commerce",
    11: "Księgowość",
    12: "Kontroling",
    19: "Automatyka",
    26: "Grafika",
    27: "3D",
    28: "UX/UI",
    39: "Finanse",
    41: "PM",
    44: "Inne",
    46: "HR",
    48: "Logistyka",
    54: "Medycyna",
    69: "Inne",
    87: "Projektowanie",
    94: "Administracja",
    95: "Produkcja",
    97: "Produkcja",
    100: "Asystent",
    101: "Edukacja",
    103: "Wycena",
    104: "Nieruchomości",
    112: "Turystyka",
    113: "Gastronomia",
    116: "Mechanika",
    119: "Flota",
    127: "Prawo",
    131: "Dziennikarstwo",
    133: "Produkcja",
    135: "Strategia",
    137: "Telekomunikacja",
    141: "IT",
    146: "Administracja",
    151: "Telekomunikacja",
    152: "Media",
    159: "Budownictwo",
    167: "Produkcja",
    168: "Telekomunikacja",
    169: "Media",
    170: "Transport",
    172: "Usługi profesjonalne",
}


class RocketJobsScraper(JustJoinBaseScraper):
    source = Source.ROCKETJOBS
    base_url = SOURCES["rocketjobs"]["base_url"]
    delay = SOURCES["rocketjobs"]["delay"]

    api_url = "https://api.rocketjobs.pl/v2/user-panel/offers"
    offer_url_prefix = "https://rocketjobs.pl/oferta-pracy/"
    category_map = _CATEGORY_MAP
