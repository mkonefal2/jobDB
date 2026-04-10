from __future__ import annotations

import json
import re

from playwright.sync_api import sync_playwright, Browser
from rich.console import Console

from config.settings import SOURCES
from src.models.schema import JobOffer, SalaryPeriod, Seniority, Source, WorkMode
from src.scrapers.base import BaseScraper

console = Console()


class PracujPLScraper(BaseScraper):
    """Scraper for pracuj.pl using Playwright + __NEXT_DATA__ extraction.

    pracuj.pl is a Next.js SSR app that embeds offer data in a
    <script id="__NEXT_DATA__"> tag.  Plain HTTP requests are blocked (403),
    so we use a headless browser to load pages.
    """

    source = Source.PRACUJ
    base_url = SOURCES["pracuj"]["base_url"]
    delay = SOURCES["pracuj"]["delay"]

    LISTING_URL = "https://www.pracuj.pl/praca"
    RESULTS_PER_PAGE = 50

    def __init__(self, max_pages: int | None = None):
        super().__init__(max_pages=max_pages)
        self._playwright = None
        self._browser: Browser | None = None

    # -- lifecycle --------------------------------------------------------

    def _ensure_browser(self) -> Browser:
        if self._browser is not None:
            return self._browser

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)
        return self._browser

    def close(self) -> None:
        super().close()
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None

    # -- page fetching ----------------------------------------------------

    def _listing_url(self, page_num: int) -> str:
        if page_num <= 1:
            return self.LISTING_URL
        return f"{self.LISTING_URL}?pn={page_num}"

    def _fetch_next_data(self, url: str) -> dict | None:
        """Load a page in a fresh browser context and extract __NEXT_DATA__."""
        browser = self._ensure_browser()
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            locale="pl-PL",
        )
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            # Wait for __NEXT_DATA__ script tag (hidden by nature, use 'attached')
            page.wait_for_selector("#__NEXT_DATA__", state="attached", timeout=15_000)
            raw = page.evaluate(
                "() => {"
                "  const el = document.getElementById('__NEXT_DATA__');"
                "  return el ? el.textContent : null;"
                "}"
            )
            if raw:
                return json.loads(raw)
            return None
        finally:
            page.close()
            context.close()

    # -- parsing ----------------------------------------------------------

    def scrape_listings(self, page: int) -> list[JobOffer]:
        url = self._listing_url(page)
        data = self._fetch_next_data(url)
        if not data:
            return []

        try:
            page_props = data["props"]["pageProps"]
            dehydrated = page_props["dehydratedState"]
            queries = dehydrated["queries"]
            # First query contains the offer listing
            offers_state = queries[0]["state"]["data"]
            grouped = offers_state.get("groupedOffers", [])
        except (KeyError, IndexError):
            return []

        offers: list[JobOffer] = []
        seen_ids: set[str] = set()

        for group in grouped:
            try:
                parsed = self._parse_group(group)
                for offer in parsed:
                    if offer.source_id not in seen_ids:
                        seen_ids.add(offer.source_id)
                        offers.append(offer)
            except Exception:
                continue

        return offers

    def _parse_group(self, group: dict) -> list[JobOffer]:
        """Parse a grouped offer into one or more JobOffer objects.

        A group may contain multiple sub-offers for different locations.
        """
        title = group.get("jobTitle", "").strip()
        company = group.get("companyName", "").strip() or None
        if not title:
            return []

        # Salary
        salary_min, salary_max, currency, period, salary_type = _parse_salary(
            group.get("salaryDisplayText", "")
        )

        # Seniority from positionLevels
        seniority = _detect_seniority(group.get("positionLevels", []))

        # Employment type
        employment_type = _detect_employment(group.get("typesOfContract", []))

        # Work mode
        work_mode = _detect_work_mode(group.get("workModes", []))

        # Sub-offers (one per location)
        sub_offers = group.get("offers", [])
        if not sub_offers:
            return []

        results: list[JobOffer] = []
        for sub in sub_offers:
            partition_id = str(sub.get("partitionId", ""))
            if not partition_id:
                continue

            source_url = sub.get("offerAbsoluteUri", "")
            location_raw = sub.get("displayWorkplace", "")

            offer = JobOffer(
                source=self.source,
                source_id=partition_id,
                source_url=source_url,
                title=title,
                company_name=company,
                location_raw=location_raw if location_raw else None,
                work_mode=work_mode,
                seniority=seniority,
                employment_type=employment_type,
                salary_min=salary_min,
                salary_max=salary_max,
                salary_currency=currency,
                salary_period=period,
                salary_type=salary_type,
            )
            results.append(offer)

        return results


# -- helpers ---------------------------------------------------------------


def _parse_salary(
    text: str,
) -> tuple[float | None, float | None, str | None, SalaryPeriod | None, str | None]:
    """Parse pracuj.pl salary display text.

    Examples:
      "11 500–15 000 zł brutto / mies."
      "38 zł brutto / godz."
      "8 000–10 000 EUR netto / mies."
    """
    if not text or not text.strip():
        return None, None, None, None, None

    text = text.replace("\xa0", " ").strip()
    text_lower = text.lower()

    # Currency
    currency = "PLN"
    if "eur" in text_lower or "€" in text_lower:
        currency = "EUR"
    elif "usd" in text_lower or "$" in text_lower:
        currency = "USD"
    elif "gbp" in text_lower or "£" in text_lower:
        currency = "GBP"
    elif "chf" in text_lower:
        currency = "CHF"

    # Period
    period = SalaryPeriod.MONTH
    if "godz" in text_lower or "/h" in text_lower:
        period = SalaryPeriod.HOUR
    elif "dzień" in text_lower or "dniów" in text_lower:
        period = SalaryPeriod.DAY
    elif "rok" in text_lower or "rocznie" in text_lower:
        period = SalaryPeriod.YEAR

    # Brutto / netto
    salary_type = None
    if "brutto" in text_lower:
        salary_type = "brutto"
    elif "netto" in text_lower or "na rękę" in text_lower:
        salary_type = "netto"

    # Split on range separator (en-dash or hyphen between numbers)
    # "11 500–15 000 zł" → ["11 500", "15 000 zł"]
    parts = re.split(r"[–\u2013]", text)

    cleaned: list[float] = []
    for part in parts:
        # Extract number groups: "11 500" or "38" (digits with optional space separators)
        nums = re.findall(r"\d[\d\s]*\d|\d+", part)
        for n in nums:
            n = n.replace(" ", "").strip()
            if not n:
                continue
            try:
                val = float(n)
                min_threshold = 5 if period == SalaryPeriod.HOUR else 20 if period == SalaryPeriod.DAY else 100
                if val >= min_threshold:
                    cleaned.append(val)
                    break  # Take first valid number per range part
            except ValueError:
                continue

    if len(cleaned) >= 2:
        return min(cleaned[:2]), max(cleaned[:2]), currency, period, salary_type
    elif len(cleaned) == 1:
        return cleaned[0], cleaned[0], currency, period, salary_type
    return None, None, None, None, None


_SENIORITY_MAP = {
    "praktykant": Seniority.INTERN,
    "stażysta": Seniority.INTERN,
    "stażystka": Seniority.INTERN,
    "asystent": Seniority.JUNIOR,
    "asystentka": Seniority.JUNIOR,
    "młodszy specjalista": Seniority.JUNIOR,
    "młodsza specjalistka": Seniority.JUNIOR,
    "junior": Seniority.JUNIOR,
    "specjalista": Seniority.MID,
    "specjalistka": Seniority.MID,
    "mid": Seniority.MID,
    "regular": Seniority.MID,
    "pracownik fizyczny": Seniority.MID,
    "pracowniczka fizyczna": Seniority.MID,
    "starszy specjalista": Seniority.SENIOR,
    "starsza specjalistka": Seniority.SENIOR,
    "senior": Seniority.SENIOR,
    "ekspert": Seniority.SENIOR,
    "ekspertka": Seniority.SENIOR,
    "kierownik": Seniority.MANAGER,
    "kierowniczka": Seniority.MANAGER,
    "koordynator": Seniority.MANAGER,
    "koordynatorka": Seniority.MANAGER,
    "menedżer": Seniority.MANAGER,
    "menedżerka": Seniority.MANAGER,
    "manager": Seniority.MANAGER,
    "dyrektor": Seniority.LEAD,
    "dyrektorka": Seniority.LEAD,
}


def _detect_seniority(levels: list[str]) -> Seniority:
    """Map pracuj.pl positionLevels to our Seniority enum."""
    if not levels:
        return Seniority.UNKNOWN

    combined = " ".join(levels).lower()

    # Check most specific first (longer matches)
    for keyword, sen in sorted(_SENIORITY_MAP.items(), key=lambda x: -len(x[0])):
        if keyword in combined:
            return sen

    return Seniority.UNKNOWN


def _detect_employment(contracts: list[str]) -> str | None:
    """Map pracuj.pl typesOfContract to employment type string."""
    if not contracts:
        return None

    mapping = {
        "umowa o pracę": "UoP",
        "kontrakt b2b": "B2B",
        "umowa zlecenie": "UZ",
        "umowa o dzieło": "UoD",
        "umowa o staż": "staż",
        "umowa na zastępstwo": "UoP zastępstwo",
        "umowa agencyjna": "agencyjna",
    }

    types = []
    for contract in contracts:
        cl = contract.lower().strip()
        for key, abbr in mapping.items():
            if key in cl and abbr not in types:
                types.append(abbr)
                break

    return " / ".join(types) if types else None


_WORK_MODE_MAP = {
    "stacjonarna": WorkMode.ONSITE,
    "full-office": WorkMode.ONSITE,
    "hybrydowa": WorkMode.HYBRID,
    "hybrid": WorkMode.HYBRID,
    "zdalna": WorkMode.REMOTE,
    "home-office": WorkMode.REMOTE,
    "mobilna": WorkMode.ONSITE,
    "mobile": WorkMode.ONSITE,
}


def _detect_work_mode(modes: list[str]) -> WorkMode:
    """Map pracuj.pl workModes to our WorkMode enum."""
    if not modes:
        return WorkMode.UNKNOWN

    combined = " ".join(modes).lower()
    for keyword, wm in _WORK_MODE_MAP.items():
        if keyword in combined:
            return wm

    return WorkMode.UNKNOWN
