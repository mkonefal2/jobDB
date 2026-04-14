from __future__ import annotations

import json
import re
import time
from datetime import datetime
from html import unescape

from playwright.sync_api import Browser, sync_playwright
from rich.console import Console

from config.settings import SOURCES
from src.models.schema import JobOffer, SalaryPeriod, Seniority, Source, WorkMode
from src.scrapers.base import BaseScraper

console = Console()


class JoobleScraper(BaseScraper):
    """Scraper for pl.jooble.org using Playwright + __INITIAL_STATE__ extraction.

    Jooble uses Cloudflare protection, so plain HTTP requests are blocked.
    We use a headless browser to load pages and extract job data from the
    window.__INITIAL_STATE__ JavaScript object.
    """

    source = Source.JOOBLE
    base_url = SOURCES["jooble"]["base_url"]
    delay = SOURCES["jooble"]["delay"]

    LISTING_URL = "https://pl.jooble.org/SearchResult"
    RESULTS_PER_PAGE = 20

    def __init__(self, max_pages: int | None = None):
        super().__init__(max_pages=max_pages)
        self._playwright = None
        self._browser: Browser | None = None

    # -- lifecycle --------------------------------------------------------

    def _ensure_browser(self) -> Browser:
        if self._browser is not None:
            return self._browser

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
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
        return f"{self.LISTING_URL}?p={page_num}"

    def _fetch_initial_state(self, url: str) -> dict | None:
        """Load a page in a browser context and extract __INITIAL_STATE__."""
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
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)

            # Wait for Cloudflare challenge to resolve and page to render
            # Try waiting for a job card to appear
            try:
                page.wait_for_selector(
                    '[data-test-name="_jobCard"]', state="attached", timeout=30_000
                )
            except Exception:
                # Fallback: wait fixed time for Cloudflare to resolve
                time.sleep(15)

            raw = page.evaluate("() => JSON.stringify(window.__INITIAL_STATE__)")
            if raw:
                return json.loads(raw)
            return None
        finally:
            page.close()
            context.close()

    # -- parsing ----------------------------------------------------------

    def scrape_listings(self, page: int) -> list[JobOffer]:
        url = self._listing_url(page)
        state = self._fetch_initial_state(url)
        if not state:
            return []

        try:
            serp_jobs = state["serpJobs"]
            pages_data = serp_jobs.get("jobs", [])
            if not pages_data:
                return []

            items = pages_data[0].get("items", [])
        except (KeyError, IndexError):
            return []

        # Filter for actual job items (componentName is None)
        job_items = [item for item in items if not item.get("componentName")]

        offers: list[JobOffer] = []
        seen_ids: set[str] = set()

        for item in job_items:
            try:
                offer = self._parse_item(item)
                if offer and offer.source_id not in seen_ids:
                    seen_ids.add(offer.source_id)
                    offers.append(offer)
            except Exception:
                continue

        return offers

    def _parse_item(self, item: dict) -> JobOffer | None:
        uid = str(item.get("uid", ""))
        if not uid:
            return None

        # Title — prefer <h2> from fullContent, fallback to first content line
        title = ""
        full_html = item.get("fullContent") or ""
        if full_html:
            h2_match = re.search(r"<h2[^>]*>\s*(.+?)\s*</h2>", full_html, re.IGNORECASE | re.DOTALL)
            if h2_match:
                title = unescape(re.sub(r"<[^>]+>", "", h2_match.group(1))).strip()

        if not title:
            content = (item.get("content") or "").strip()
            title = content.split("\r\n")[0].strip() if content else ""
            # Strip any remaining HTML tags
            title = re.sub(r"<[^>]+>", "", title).strip()

        if not title or len(title) < 3:
            return None

        # If extracted "title" is suspiciously long, it's likely description text
        if len(title) > 120:
            # Try to get just the first sentence
            short = re.split(r"[.!?]", title)[0].strip()
            if 3 < len(short) < 120:
                title = short
            else:
                title = title[:120].rsplit(" ", 1)[0] + "…"

        # URL — the away redirect URL
        source_url = item.get("url") or ""

        # Company
        company_data = item.get("company") or {}
        company_name = company_data.get("name") or None
        company_logo_url = company_data.get("logo_url") or company_data.get("logoUrl") or None

        # Location
        location_data = item.get("location") or {}
        location_raw = location_data.get("name") or None

        # Work mode
        work_mode = _detect_work_mode(item)

        # Salary
        salary_min, salary_max, currency, period = _parse_salary(
            item.get("salary") or ""
        )

        # Employment type from tags
        employment_type = _detect_employment_type(item.get("tags") or [])

        # Published date
        published_at = None
        date_str = item.get("dateUpdated")
        if date_str:
            try:
                published_at = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        # Description text (strip HTML from fullContent)
        description_text = None
        full_content = item.get("fullContent") or ""
        if full_content:
            description_text = unescape(re.sub(r"<[^>]+>", " ", full_content))
            description_text = re.sub(r"\s+", " ", description_text).strip()

        return JobOffer(
            source=self.source,
            source_id=uid,
            source_url=source_url,
            title=title,
            company_name=company_name,
            company_logo_url=company_logo_url,
            location_raw=location_raw,
            work_mode=work_mode,
            employment_type=employment_type,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=currency,
            salary_period=period,
            published_at=published_at,
            description_text=description_text,
        )


# -- helpers ---------------------------------------------------------------


def _detect_work_mode(item: dict) -> WorkMode:
    """Detect work mode from isRemoteJob flag and tags."""
    if item.get("isRemoteJob"):
        return WorkMode.REMOTE

    tags = item.get("tags") or []
    for tag in tags:
        name = (tag.get("name") or "").lower()
        if "zdalna" in name or "z_domu" in name:
            return WorkMode.REMOTE
        if "hybrydow" in name:
            return WorkMode.HYBRID
        if "stacjonarn" in name:
            return WorkMode.ONSITE

    return WorkMode.UNKNOWN


def _detect_employment_type(tags: list[dict]) -> str | None:
    """Extract employment type from Jooble tags."""
    emp_types = []
    for tag in tags:
        name = (tag.get("name") or "").lower()
        category = (tag.get("categoryName") or "").lower()
        if "employment" not in category:
            continue

        if "umowa_o_prace" in name:
            emp_types.append("UoP")
        elif "b2b" in name or "kontrakt" in name:
            emp_types.append("B2B")
        elif "zleceni" in name:
            emp_types.append("UZ")
        elif "dzielo" in name:
            emp_types.append("UoD")
        elif "praktyka" in name or "staz" in name:
            emp_types.append("Praktyki")

    return " / ".join(emp_types) if emp_types else None


def _parse_salary(
    text: str,
) -> tuple[float | None, float | None, str | None, SalaryPeriod | None]:
    """Parse Jooble salary text.

    Examples:
      "8500 - 9500 zł"
      "10500 - 16200 zł"
      "120 zł/godz."
      "8 000 - 10 000 EUR"
    """
    if not text or not text.strip():
        return None, None, None, None

    text = text.replace("\xa0", " ").strip()

    # Detect currency
    currency = None
    for cur, pattern in [
        ("PLN", r"zł|pln"),
        ("EUR", r"eur|€"),
        ("USD", r"usd|\$"),
        ("GBP", r"gbp|£"),
        ("CHF", r"chf"),
    ]:
        if re.search(pattern, text, re.IGNORECASE):
            currency = cur
            break
    if not currency:
        currency = "PLN"  # Default for pl.jooble.org

    # Detect period
    period = SalaryPeriod.MONTH  # Default
    text_lower = text.lower()
    if any(p in text_lower for p in ["godz", "/h", "hourly"]):
        period = SalaryPeriod.HOUR
    elif any(p in text_lower for p in ["dzień", "day", "/d"]):
        period = SalaryPeriod.DAY
    elif any(p in text_lower for p in ["rok", "year", "annual"]):
        period = SalaryPeriod.YEAR

    # Extract numbers
    numbers = re.findall(r"[\d\s]+", text)
    parsed = []
    for n in numbers:
        n = n.strip().replace(" ", "")
        if n and n.isdigit():
            parsed.append(float(n))

    if len(parsed) >= 2:
        return parsed[0], parsed[1], currency, period
    elif len(parsed) == 1:
        return parsed[0], parsed[0], currency, period

    return None, None, None, None
