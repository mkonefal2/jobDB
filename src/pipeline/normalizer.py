from __future__ import annotations

import re

from src.models.schema import JobOffer, SalaryPeriod, WorkMode
from src.pipeline.polish_cities import build_city_aliases, build_city_to_region

# Auto-generated from comprehensive Polish cities database (~1000 cities + localities)
CITY_ALIASES: dict[str, str] = build_city_aliases()
CITY_TO_REGION: dict[str, str] = build_city_to_region()


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

    # Strip parenthetical suffixes: "Hipolitów (pow. miński)" → "Hipolitów"
    candidate = re.sub(r"\s*\(.*\)\s*$", "", candidate).strip()

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
        # Nullify anonymous/placeholder company names (e.g. praca.pl anonymous employers)
        if re.match(r"^Klient portalu", offer.company_name, re.IGNORECASE):
            offer.company_name = None

    # Default currency to PLN
    if offer.salary_min and not offer.salary_currency:
        offer.salary_currency = "PLN"

    # Default salary type to brutto (most common in Polish listings)
    if offer.salary_min and not offer.salary_type:
        offer.salary_type = "brutto"

    # Validate salary range: swap if min > max
    if offer.salary_min and offer.salary_max and offer.salary_min > offer.salary_max:
        offer.salary_min, offer.salary_max = offer.salary_max, offer.salary_min

    # Reject outlier salaries (likely parsing errors)
    if offer.salary_max:
        period = offer.salary_period or SalaryPeriod.MONTH
        upper_bounds = {
            SalaryPeriod.HOUR: 2_000,
            SalaryPeriod.DAY: 15_000,
            SalaryPeriod.MONTH: 200_000,
            SalaryPeriod.YEAR: 2_500_000,
        }
        if offer.salary_max > upper_bounds.get(period, 200_000):
            offer.salary_min = None
            offer.salary_max = None
            offer.salary_currency = None
            offer.salary_period = None
            offer.salary_type = None

    return offer


def normalize_offers(offers: list[JobOffer]) -> list[JobOffer]:
    """Normalize a batch of offers."""
    return [normalize_offer(o) for o in offers]
