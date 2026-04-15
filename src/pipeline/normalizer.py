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

    # Fix misclassified salary_period (hourly ↔ monthly confusion)
    if offer.salary_min and offer.salary_period:
        offer.salary_period = _fix_salary_period(
            offer.salary_min, offer.salary_max, offer.salary_period, offer.salary_currency
        )

    # Reject outlier salaries (likely parsing errors)
    if offer.salary_min and offer.salary_max:
        ratio = offer.salary_max / offer.salary_min if offer.salary_min > 0 else 0
        if ratio > 10:
            offer.salary_min = None
            offer.salary_max = None
            offer.salary_currency = None
            offer.salary_period = None
            offer.salary_type = None

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

    # Normalize employment_type
    if offer.employment_type:
        offer.employment_type = normalize_employment_type(offer.employment_type)

    return offer


# -- salary period heuristic -----------------------------------------------

# Thresholds for PLN; other currencies are converted with approximate multipliers
_CURRENCY_TO_PLN = {"PLN": 1.0, "EUR": 4.3, "USD": 4.0, "GBP": 5.0, "CHF": 4.5}


def _fix_salary_period(
    salary_min: float,
    salary_max: float | None,
    period: SalaryPeriod,
    currency: str | None,
) -> SalaryPeriod:
    """Detect and fix misclassified salary_period.

    Common scraper errors:
    - hourly rate (e.g. 30 PLN/h) stored as monthly
    - monthly rate (e.g. 25 000 PLN/month) stored as hourly
    """
    ref = salary_max or salary_min
    multiplier = _CURRENCY_TO_PLN.get(currency or "PLN", 1.0)
    ref_pln = ref * multiplier

    if period == SalaryPeriod.MONTH and ref_pln < 300:
        # Values like 30-150 PLN/month are obviously hourly rates
        return SalaryPeriod.HOUR
    if period == SalaryPeriod.HOUR and ref_pln > 1_000:
        # Values like 26000 PLN/hour are obviously monthly
        return SalaryPeriod.MONTH

    return period


# -- employment type normalization -----------------------------------------

_EMPLOYMENT_CANONICAL = {
    "uop": "UoP",
    "umowa o pracę": "UoP",
    "umowa o prace": "UoP",
    "uop tymczasowa": "UoP tymczasowa",
    "umowa o pracę tymczasowa": "UoP tymczasowa",
    "uop zastępstwo": "UoP zastępstwo",
    "umowa na zastępstwo": "UoP zastępstwo",
    "b2b": "B2B",
    "kontrakt b2b": "B2B",
    "uz": "UZ",
    "umowa zlecenie": "UZ",
    "umowa zleceni": "UZ",
    "uod": "UoD",
    "umowa o dzieło": "UoD",
    "umowa o dzielo": "UoD",
    "staż": "staż",
    "staz": "staż",
    "umowa o staż": "staż",
    "dowolna": "dowolna",
    "agencyjna": "agencyjna",
    "umowa agencyjna": "agencyjna",
}

# Canonical order for consistent output
_EMPLOYMENT_ORDER = {
    "UoP": 0,
    "UoP tymczasowa": 1,
    "UoP zastępstwo": 2,
    "B2B": 3,
    "UZ": 4,
    "UoD": 5,
    "agencyjna": 6,
    "staż": 7,
    "dowolna": 8,
}


def normalize_employment_type(raw: str) -> str:
    """Normalize employment_type to canonical abbreviations with ' / ' separator."""
    # Split on common separators: ' / ', ', ', ' | '
    parts = re.split(r"\s*/\s*|\s*,\s*|\s*\|\s*", raw.strip())

    canonical: list[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        mapped = _EMPLOYMENT_CANONICAL.get(part.lower(), part)
        if mapped not in canonical:
            canonical.append(mapped)

    canonical.sort(key=lambda x: _EMPLOYMENT_ORDER.get(x, 99))
    return " / ".join(canonical) if canonical else raw


def normalize_offers(offers: list[JobOffer]) -> list[JobOffer]:
    """Normalize a batch of offers."""
    return [normalize_offer(o) for o in offers]
