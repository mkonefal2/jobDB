from __future__ import annotations

import re

from src.models.schema import JobOffer, WorkMode

# Mapping of common city name variants → canonical name
CITY_ALIASES: dict[str, str] = {
    "warszawa": "Warszawa",
    "warsaw": "Warszawa",
    "kraków": "Kraków",
    "krakow": "Kraków",
    "cracow": "Kraków",
    "wrocław": "Wrocław",
    "wroclaw": "Wrocław",
    "breslau": "Wrocław",
    "gdańsk": "Gdańsk",
    "gdansk": "Gdańsk",
    "poznań": "Poznań",
    "poznan": "Poznań",
    "łódź": "Łódź",
    "lodz": "Łódź",
    "katowice": "Katowice",
    "szczecin": "Szczecin",
    "lublin": "Lublin",
    "bydgoszcz": "Bydgoszcz",
    "białystok": "Białystok",
    "bialystok": "Białystok",
    "gdynia": "Gdynia",
    "częstochowa": "Częstochowa",
    "czestochowa": "Częstochowa",
    "radom": "Radom",
    "toruń": "Toruń",
    "torun": "Toruń",
    "kielce": "Kielce",
    "rzeszów": "Rzeszów",
    "rzeszow": "Rzeszów",
    "olsztyn": "Olsztyn",
    "opole": "Opole",
    "gliwice": "Gliwice",
    "zielona góra": "Zielona Góra",
    "zielona gora": "Zielona Góra",
    "bielsko-biała": "Bielsko-Biała",
    "bielsko-biala": "Bielsko-Biała",
    "sosnowiec": "Sosnowiec",
    "pruszków": "Pruszków",
    "pruszkow": "Pruszków",
    "nowy sącz": "Nowy Sącz",
    "nowy sacz": "Nowy Sącz",
    "tychy": "Tychy",
    "jelenia góra": "Jelenia Góra",
    "jelenia gora": "Jelenia Góra",
    "jasło": "Jasło",
    "jaslo": "Jasło",
    "ruda śląska": "Ruda Śląska",
    "ruda slaska": "Ruda Śląska",
    "tarnów": "Tarnów",
    "tarnow": "Tarnów",
    "płock": "Płock",
    "plock": "Płock",
    "elbląg": "Elbląg",
    "elblag": "Elbląg",
    "remote": "Remote",
    "zdalna": "Remote",
    "praca zdalna": "Remote",
}

CITY_TO_REGION: dict[str, str] = {
    "Warszawa": "mazowieckie",
    "Kraków": "małopolskie",
    "Wrocław": "dolnośląskie",
    "Gdańsk": "pomorskie",
    "Poznań": "wielkopolskie",
    "Łódź": "łódzkie",
    "Katowice": "śląskie",
    "Szczecin": "zachodniopomorskie",
    "Lublin": "lubelskie",
    "Bydgoszcz": "kujawsko-pomorskie",
    "Białystok": "podlaskie",
    "Gdynia": "pomorskie",
    "Częstochowa": "śląskie",
    "Radom": "mazowieckie",
    "Toruń": "kujawsko-pomorskie",
    "Kielce": "świętokrzyskie",
    "Rzeszów": "podkarpackie",
    "Olsztyn": "warmińsko-mazurskie",
    "Opole": "opolskie",
    "Gliwice": "śląskie",
    "Zielona Góra": "lubuskie",
    "Bielsko-Biała": "śląskie",
    "Sosnowiec": "śląskie",
    "Nowy Sącz": "małopolskie",
}


def normalize_city(raw_location: str | None) -> tuple[str | None, str | None]:
    """Return (canonical_city, region) from raw location string."""
    if not raw_location:
        return None, None

    # Clean the string
    loc = raw_location.strip()
    # Fix concatenated 'pracamobilna'/'pracazdalna' etc.
    loc = re.sub(r"praca(mobilna|stacjonarna|zdalna|hybrydowa)", "", loc).strip()

    # Try extracting city from comma-separated or slash-separated location
    # "Warszawa, Mokotów" → "Warszawa"
    # "Nowy Sącz" → "Nowy Sącz"
    parts = re.split(r"[,/;|+]", loc)
    candidate = parts[0].strip()

    # Strip common prefixes
    candidate = re.sub(r"^(ul\.|ul |al\.|al )", "", candidate).strip()

    # Look up in aliases
    city = CITY_ALIASES.get(candidate.lower())

    if not city:
        # Try each known city as substring
        loc_lower = loc.lower()
        for alias, canonical in sorted(CITY_ALIASES.items(), key=lambda x: -len(x[0])):
            if alias in loc_lower:
                city = canonical
                break

    region = CITY_TO_REGION.get(city) if city else None
    return city, region


def normalize_work_mode(offer: JobOffer) -> WorkMode:
    """Re-detect work mode from all available text."""
    if offer.work_mode != WorkMode.UNKNOWN:
        return offer.work_mode

    text = " ".join(filter(None, [offer.title, offer.location_raw, offer.description_text])).lower()

    if "remote" in text or "zdalna" in text or "zdalnie" in text:
        return WorkMode.REMOTE
    if "hybrid" in text or "hybrydow" in text:
        return WorkMode.HYBRID
    if "stacjonarn" in text or "on-site" in text or "onsite" in text or "w biurze" in text:
        return WorkMode.ONSITE

    return WorkMode.UNKNOWN


def normalize_offer(offer: JobOffer) -> JobOffer:
    """Apply all normalizations to a single offer."""
    # Normalize city and region
    if offer.location_raw:
        city, region = normalize_city(offer.location_raw)
        if city:
            offer.location_city = city
        if region:
            offer.location_region = region

    # Normalize work mode
    offer.work_mode = normalize_work_mode(offer)

    # Clean title whitespace
    if offer.title:
        offer.title = re.sub(r"\s+", " ", offer.title).strip()

    # Clean company name
    if offer.company_name:
        offer.company_name = re.sub(r"\s+", " ", offer.company_name).strip()

    # Default currency to PLN
    if offer.salary_min and not offer.salary_currency:
        offer.salary_currency = "PLN"

    # Default salary type to brutto (most common in Polish listings)
    if offer.salary_min and not offer.salary_type:
        offer.salary_type = "brutto"

    return offer


def normalize_offers(offers: list[JobOffer]) -> list[JobOffer]:
    """Normalize a batch of offers."""
    return [normalize_offer(o) for o in offers]
