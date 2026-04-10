"""Shared base for JustJoin.it-family scrapers (justjoin.it & rocketjobs.pl).

Both sites use the same API structure under different domains.
"""
from __future__ import annotations

from datetime import datetime

from src.models.schema import JobOffer, SalaryPeriod, Seniority, Source, WorkMode
from src.scrapers.base import BaseScraper

PER_PAGE = 100

EXPERIENCE_MAP = {
    "junior": Seniority.JUNIOR,
    "mid": Seniority.MID,
    "senior": Seniority.SENIOR,
    "c_level": Seniority.LEAD,
}

WORKPLACE_MAP = {
    "remote": WorkMode.REMOTE,
    "hybrid": WorkMode.HYBRID,
    "office": WorkMode.ONSITE,
    "mobile": WorkMode.ONSITE,  # field work → closest to onsite
}

EMPLOYMENT_TYPE_MAP = {
    "b2b": "B2B",
    "permanent": "UoP",
    "mandate_contract": "umowa zlecenie",
    "contract": "umowa o dzieło",
    "internship": "staż",
    "any": "dowolna",
}

PERIOD_MAP = {
    "month": SalaryPeriod.MONTH,
    "hour": SalaryPeriod.HOUR,
    "day": SalaryPeriod.DAY,
    "year": SalaryPeriod.YEAR,
}


class JustJoinBaseScraper(BaseScraper):
    """Base scraper for JustJoin.it-family APIs.

    Subclasses must set:
      - source: Source enum
      - base_url / delay (from settings)
      - api_url: full API endpoint URL
      - offer_url_prefix: e.g. "https://justjoin.it/job-offer/"
      - category_map: dict[int, str] mapping categoryId → name
    """

    api_url: str
    offer_url_prefix: str
    category_map: dict[int, str] = {}

    def _api_headers(self) -> dict[str, str]:
        headers = self._default_headers()
        headers["Accept"] = "application/json"
        headers["Version"] = "2"
        return headers

    def scrape_listings(self, page: int) -> list[JobOffer]:
        response = self.fetch(
            self.api_url,
            params={"page": page, "perPage": PER_PAGE},
            headers=self._api_headers(),
        )
        data = response.json()

        items = data.get("data", [])
        if not items:
            return []

        offers: list[JobOffer] = []
        seen: set[str] = set()

        for item in items:
            try:
                parsed = self._parse_offer(item)
                for offer in parsed:
                    if offer.source_id not in seen:
                        seen.add(offer.source_id)
                        offers.append(offer)
            except Exception:
                continue

        return offers

    def _parse_offer(self, item: dict) -> list[JobOffer]:
        guid = item.get("guid", "")
        slug = item.get("slug", "")
        title = item.get("title", "").strip()
        if not title or not guid:
            return []

        company = item.get("companyName", "").strip() or None
        work_mode = WORKPLACE_MAP.get(item.get("workplaceType", ""), WorkMode.UNKNOWN)
        seniority = EXPERIENCE_MAP.get(item.get("experienceLevel", ""), Seniority.UNKNOWN)
        category = self.category_map.get(item.get("categoryId"))

        skills = item.get("requiredSkills") or []
        nice = item.get("niceToHaveSkills") or []
        technologies = list(dict.fromkeys(skills + nice))

        published_at = _parse_datetime(item.get("publishedAt"))

        salary_min, salary_max, currency, period, salary_type, employment_type = _pick_best_salary(
            item.get("employmentTypes", [])
        )

        multilocations = item.get("multilocation") or []
        if not multilocations:
            city = item.get("city", "")
            multilocations = [{"city": city, "slug": slug}]

        results: list[JobOffer] = []
        for loc in multilocations:
            loc_city = loc.get("city", "").strip()
            loc_slug = loc.get("slug", slug)
            source_url = f"{self.offer_url_prefix}{loc_slug}"
            source_id = guid if len(multilocations) == 1 else f"{guid}:{loc_city}"

            offer = JobOffer(
                source=self.source,
                source_id=source_id,
                source_url=source_url,
                title=title,
                company_name=company,
                location_raw=loc_city if loc_city else None,
                location_city=loc_city if loc_city else None,
                work_mode=work_mode,
                seniority=seniority,
                employment_type=employment_type,
                salary_min=salary_min,
                salary_max=salary_max,
                salary_currency=currency,
                salary_period=period,
                salary_type=salary_type,
                category=category,
                technologies=technologies,
                published_at=published_at,
            )
            results.append(offer)

        return results


# -- helpers ---------------------------------------------------------------


def _pick_best_salary(
    employment_types: list[dict],
) -> tuple[float | None, float | None, str | None, SalaryPeriod | None, str | None, str | None]:
    if not employment_types:
        return None, None, None, None, None, None

    preferred_order = {"b2b": 0, "permanent": 1, "mandate_contract": 2, "contract": 3, "internship": 4, "any": 5}
    sorted_types = sorted(
        employment_types,
        key=lambda e: (
            0 if e.get("from") else 1,
            preferred_order.get(e.get("type", ""), 99),
        ),
    )

    best = sorted_types[0]

    salary_min = best.get("from")
    salary_max = best.get("to")
    currency = (best.get("currency") or "pln").upper()
    period = PERIOD_MAP.get(best.get("unit", ""), SalaryPeriod.MONTH)
    salary_type = "netto" if best.get("gross") is False else "brutto" if best.get("gross") is True else None

    all_types = [EMPLOYMENT_TYPE_MAP.get(e.get("type", ""), e.get("type", "")) for e in employment_types]
    employment_str = ", ".join(dict.fromkeys(all_types))

    if salary_min is not None:
        salary_min = float(salary_min)
    if salary_max is not None:
        salary_max = float(salary_max)

    return salary_min, salary_max, currency, period, salary_type, employment_str


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        clean = value.replace("Z", "+00:00")
        return datetime.fromisoformat(clean)
    except (ValueError, TypeError):
        return None
