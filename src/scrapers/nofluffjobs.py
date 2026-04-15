"""NoFluffJobs.com scraper.

Uses the public listing API which returns all postings in a single response.
Each location variant is a separate entry, so we treat them as individual offers
(consistent with how JustJoin.it multilocations are handled).
"""
from __future__ import annotations

from datetime import datetime, timezone

from config.settings import SOURCES
from src.models.schema import JobOffer, SalaryPeriod, Seniority, Source, WorkMode
from src.scrapers.base import BaseScraper

API_URL = "https://nofluffjobs.com/api/posting"
OFFER_URL_PREFIX = "https://nofluffjobs.com/pl/job/"

SENIORITY_MAP: dict[str, Seniority] = {
    "Junior": Seniority.JUNIOR,
    "Mid": Seniority.MID,
    "Senior": Seniority.SENIOR,
    "Expert": Seniority.SENIOR,
}

CATEGORY_MAP: dict[str, str] = {
    "frontend": "JavaScript",
    "backend": "Java",
    "fullstack": "JavaScript",
    "devops": "DevOps",
    "testing": "Testing",
    "data": "Data",
    "artificialIntelligence": "AI",
    "businessIntelligence": "Analytics",
    "businessAnalyst": "Analytics",
    "ux": "UX/UI",
    "projectManager": "PM",
    "productManagement": "PM",
    "security": "Security",
    "support": "Support",
    "electronics": "Other",
    "mechanics": "Other",
    "marketing": "Other",
    "sales": "Other",
    "consulting": "Other",
    "customerService": "Other",
    "erp": "ERP",
    "mobile": "Mobile",
    "other": "Other",
}

SALARY_TYPE_MAP: dict[str, str] = {
    "b2b": "B2B",
    "permanent": "UoP",
    "zlecenie": "umowa zlecenie",
    "uod": "umowa o dzieło",
    "intern": "staż",
}


class NoFluffJobsScraper(BaseScraper):
    source = Source.NOFLUFFJOBS
    base_url = SOURCES["nofluffjobs"]["base_url"]
    delay = SOURCES["nofluffjobs"]["delay"]

    def scrape_listings(self, page: int) -> list[JobOffer]:
        # API returns all postings at once — only fetch on page 1
        if page > 1:
            return []

        data = self.fetch_json(API_URL)
        items = data.get("postings", [])
        if not items:
            return []

        offers: list[JobOffer] = []
        for item in items:
            try:
                offer = self._parse_offer(item)
                if offer is not None:
                    offers.append(offer)
            except Exception:
                continue

        return offers

    def _parse_offer(self, item: dict) -> JobOffer | None:
        posting_id: str = item.get("id", "")
        title: str = item.get("title", "").strip()
        if not posting_id or not title:
            return None

        company = item.get("name", "").strip() or None
        url_slug = item.get("url", posting_id).lower()
        source_url = f"{OFFER_URL_PREFIX}{url_slug}"

        # Logo
        logo = item.get("logo") or {}
        logo_path = logo.get("jobs_listing") or logo.get("original")
        company_logo_url = f"https://nofluffjobs.com/{logo_path}" if logo_path else None

        # Location & work mode
        location = item.get("location", {})
        fully_remote = location.get("fullyRemote", False)
        hybrid_desc = location.get("hybridDesc")
        places = location.get("places", [])

        if fully_remote:
            work_mode = WorkMode.REMOTE
        elif hybrid_desc:
            work_mode = WorkMode.HYBRID
        else:
            work_mode = WorkMode.ONSITE

        # City from the first place matching the URL, or first available
        location_city = None
        for place in places:
            city = place.get("city", "").strip()
            if city and place.get("url") == url_slug:
                location_city = city
                break
        if not location_city and places:
            location_city = places[0].get("city", "").strip() or None

        # Seniority
        seniority_list = item.get("seniority", [])
        seniority = Seniority.UNKNOWN
        for s in seniority_list:
            mapped = SENIORITY_MAP.get(s)
            if mapped is not None:
                seniority = mapped
                break

        # Category
        raw_category = item.get("category", "")
        category = CATEGORY_MAP.get(raw_category, raw_category or None)

        # Technologies from tiles
        tiles = item.get("tiles", {}).get("values", [])
        technologies = [
            t["value"] for t in tiles if t.get("type") == "requirement" and t.get("value")
        ]

        # Salary (always present on NfJ)
        salary_data = item.get("salary") or {}
        salary_min = salary_data.get("from")
        salary_max = salary_data.get("to")
        salary_currency = (salary_data.get("currency") or "PLN").upper()
        salary_raw_type = salary_data.get("type", "")
        employment_type = SALARY_TYPE_MAP.get(salary_raw_type, salary_raw_type)
        # B2B is netto, UoP/zlecenie/uod is brutto
        salary_type = "netto" if salary_raw_type == "b2b" else "brutto"

        if salary_min is not None:
            salary_min = float(salary_min)
        if salary_max is not None:
            salary_max = float(salary_max)

        # Published date (epoch ms)
        posted_ms = item.get("posted")
        published_at = (
            datetime.fromtimestamp(posted_ms / 1000, tz=timezone.utc) if posted_ms else None
        )

        return JobOffer(
            source=self.source,
            source_id=posting_id,
            source_url=source_url,
            title=title,
            company_name=company,
            company_logo_url=company_logo_url,
            location_raw=location_city,
            location_city=location_city,
            work_mode=work_mode,
            seniority=seniority,
            employment_type=employment_type,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=salary_currency,
            salary_period=SalaryPeriod.MONTH,
            salary_type=salary_type,
            category=category,
            technologies=technologies,
            published_at=published_at,
        )
