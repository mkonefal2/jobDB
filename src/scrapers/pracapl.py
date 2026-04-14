from __future__ import annotations

import re
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from config.settings import SOURCES
from src.models.schema import JobOffer, SalaryPeriod, Seniority, Source, WorkMode
from src.scrapers.base import BaseScraper


class PracaPLScraper(BaseScraper):
    source = Source.PRACAPL
    base_url = SOURCES["pracapl"]["base_url"]
    delay = SOURCES["pracapl"]["delay"]

    LISTING_URL = "https://www.praca.pl/oferty-pracy.html"

    def _listing_url(self, page: int) -> str:
        if page <= 1:
            return self.LISTING_URL
        return f"https://www.praca.pl/oferty-pracy_{page}.html"

    def scrape_listings(self, page: int) -> list[JobOffer]:
        url = self._listing_url(page)
        response = self.fetch(url)
        tree = HTMLParser(response.text)

        offers = []
        seen_ids: set[str] = set()

        # praca.pl uses <li class="listing__item"> — skip weekly featured section
        cards = tree.css("ul.listing:not(.listing--week-offer) li.listing__item")

        if not cards:
            # Fallback: find all links matching offer URL pattern
            return self._parse_from_links(tree)

        for card in cards:
            try:
                parsed = self._parse_card(card)
                for offer in parsed:
                    if offer.source_id not in seen_ids:
                        seen_ids.add(offer.source_id)
                        offers.append(offer)
            except Exception:
                continue

        return offers

    def _parse_from_links(self, tree: HTMLParser) -> list[JobOffer]:
        """Fallback parser: extract offers from links matching URL pattern."""
        offers = []
        seen_ids = set()

        for link in tree.css("a[href]"):
            href = link.attributes.get("href", "")
            # praca.pl offer URLs: /title_12345678.html
            match = re.search(r"_(\d{7,10})\.html", href)
            if not match:
                continue

            source_id = match.group(1)
            if source_id in seen_ids:
                continue
            seen_ids.add(source_id)

            title_text = link.text(strip=True)
            if not title_text or len(title_text) < 3:
                continue

            url = urljoin(self.base_url, href)
            offer = JobOffer(
                source=self.source,
                source_id=source_id,
                source_url=url,
                title=title_text.strip(),
            )
            offers.append(offer)

        return offers

    def _parse_card(self, card) -> list[JobOffer]:
        # Check if this is a multi-location card (title is a <button>, not <a>)
        button_title = card.css_first("button.listing__title")
        if button_title:
            return self._parse_multi_location_card(card, button_title)

        # Single-location card
        link = card.css_first("a.listing__title")
        if not link:
            link = card.css_first("a[href]")
        if not link:
            return []

        href = link.attributes.get("href", "")
        source_id = link.attributes.get("data-id", "")
        if not source_id:
            match = re.search(r"_(\d{7,10})\.html", href)
            if not match:
                return []
            source_id = match.group(1)

        url = urljoin(self.base_url, href)
        title = link.attributes.get("title", "") or link.text(strip=True)
        if not title:
            return []

        company, work_mode, location_raw, seniority, employment_type, salary_min, salary_max, currency, period = (
            self._extract_card_fields(card)
        )

        # Company logo
        logo_el = card.css_first("img.listing__logo")
        company_logo_url = logo_el.attributes.get("src", "").strip() if logo_el else None
        company_logo_url = company_logo_url or None

        return [JobOffer(
            source=self.source,
            source_id=source_id,
            source_url=url,
            title=title,
            company_name=company,
            company_logo_url=company_logo_url,
            location_raw=location_raw if location_raw else None,
            work_mode=work_mode,
            seniority=seniority,
            employment_type=employment_type,
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=currency,
            salary_period=period,
        )]

    def _parse_multi_location_card(self, card, button_title) -> list[JobOffer]:
        """Parse a multi-location card with nested location items."""
        title = button_title.attributes.get("title", "") or button_title.text(strip=True)
        if not title:
            return []

        company, work_mode, _, seniority, employment_type, salary_min, salary_max, currency, period = (
            self._extract_card_fields(card)
        )

        # Company logo
        logo_el = card.css_first("img.listing__logo")
        company_logo_url = logo_el.attributes.get("src", "").strip() if logo_el else None
        company_logo_url = company_logo_url or None

        offers = []
        for loc_item in card.css("ul.listing__locations li.listing__location-item"):
            loc_link = loc_item.css_first("a[href]")
            if not loc_link:
                continue
            href = loc_link.attributes.get("href", "")
            source_id = ""
            observe_btn = loc_item.css_first("button[data-id]")
            if observe_btn:
                source_id = observe_btn.attributes.get("data-id", "")
            if not source_id:
                match = re.search(r"_(\d{7,10})\.html", href)
                if not match:
                    continue
                source_id = match.group(1)

            location_raw = loc_link.text(strip=True)
            url = urljoin(self.base_url, href.split("#")[0])

            offers.append(JobOffer(
                source=self.source,
                source_id=source_id,
                source_url=url,
                title=title,
                company_name=company,
                company_logo_url=company_logo_url,
                location_raw=location_raw if location_raw else None,
                work_mode=work_mode,
                seniority=seniority,
                employment_type=employment_type,
                salary_min=salary_min,
                salary_max=salary_max,
                salary_currency=currency,
                salary_period=period,
            ))

        return offers

    def _extract_card_fields(self, card):
        """Extract shared fields from a card."""
        company = None
        company_el = card.css_first("a.listing__employer-name, .listing__employer-name")
        if company_el:
            company = company_el.text(strip=True)
        if not company:
            origin_el = card.css_first(".listing__origin")
            if origin_el:
                # Company may be plain text (anonymous employer) — first text node
                node = origin_el.child
                while node:
                    if node.tag == "-text":
                        txt = node.text(strip=True)
                        if txt and len(txt) > 2:
                            company = txt
                            break
                    node = node.next

        work_mode = WorkMode.UNKNOWN
        work_mode_el = card.css_first("span.listing__work-model")
        wm_text = work_mode_el.text().lower() if work_mode_el else ""
        if not wm_text:
            wm_text = card.text().lower()
        if "zdalna" in wm_text or "remote" in wm_text:
            work_mode = WorkMode.REMOTE
        elif "hybrydow" in wm_text:
            work_mode = WorkMode.HYBRID
        elif "mobilna" in wm_text or "mobiln" in wm_text:
            work_mode = WorkMode.ONSITE
        elif "stacjonarn" in wm_text:
            work_mode = WorkMode.ONSITE

        location_raw = None
        location_el = card.css_first("span.listing__location-name, span.listing__location")
        if location_el:
            for wm_child in location_el.css("span.listing__work-model"):
                wm_child.decompose()
            location_raw = location_el.text(strip=True)
            location_raw = re.sub(
                r"\s*praca\s*(stacjonarna|zdalna|hybrydowa|mobilna)", "", location_raw, flags=re.IGNORECASE
            ).strip()
            location_raw = location_raw.strip(" \t\n\xa0")

        card_text = card.text().lower()
        seniority = _detect_seniority(card_text)

        emp_types = []
        if "umowa o pracę" in card_text and "tymczasow" not in card_text:
            emp_types.append("UoP")
        if "umowa o pracę tymczasow" in card_text:
            emp_types.append("UoP tymczasowa")
        if "b2b" in card_text or "kontrakt b2b" in card_text:
            emp_types.append("B2B")
        if "umowa zleceni" in card_text:
            emp_types.append("UZ")
        if "umowa o dzieło" in card_text:
            emp_types.append("UoD")
        employment_type = " / ".join(emp_types) if emp_types else None

        salary_min, salary_max, currency, period = None, None, None, None
        main_details_el = card.css_first(".listing__main-details")
        if main_details_el:
            details_text = main_details_el.text(strip=True)
            salary_match = re.search(
                r"([\d\s,]+(?:\s*-\s*[\d\s,]+)?)\s*(?:zł|PLN|EUR|€|\$|USD|GBP|£|CHF)"
                r"\s*(?:brutto|netto|na rękę)?/?(?:mies|godz|h|dzień|day|rok|year)?\.?",
                details_text,
                re.IGNORECASE,
            )
            if salary_match:
                salary_min, salary_max, currency, period, _ = _parse_salary(salary_match.group(0))

        return company, work_mode, location_raw, seniority, employment_type, salary_min, salary_max, currency, period

    def scrape_detail(self, offer: JobOffer) -> JobOffer:
        """Enrich offer with data from its detail page."""
        try:
            response = self.fetch(offer.source_url)
            tree = HTMLParser(response.text)

            # Description
            desc_el = tree.css_first(".offer__description, .description, article")
            if desc_el:
                offer.description_text = desc_el.text(strip=True)[:5000]

            # Company (if missing)
            if not offer.company_name:
                comp_el = tree.css_first(".offer__company, .company-name, .employer-name")
                if comp_el:
                    offer.company_name = comp_el.text(strip=True)

            # Location (if missing)
            if not offer.location_raw:
                loc_el = tree.css_first(".offer__location, .location")
                if loc_el:
                    offer.location_raw = loc_el.text(strip=True)

        except Exception:
            pass

        return offer


def _parse_salary(text: str) -> tuple[float | None, float | None, str | None, SalaryPeriod | None, str | None]:
    """Parse salary string from listing card.

    Handles formats like:
    - "12 500 - 14 500 zł brutto/mies."
    - "5 100 zł brutto/mies."
    - "od 4 500 zł netto/mies."
    - "30-45 €/godz."
    - "11 000 EUR brutto/mies."

    Returns: (salary_min, salary_max, currency, period, salary_type)
    """
    if not text:
        return None, None, None, None, None

    text = text.replace("\xa0", " ").replace("\u00a0", " ").strip()
    text_lower = text.lower()

    # Detect currency
    currency = "PLN"
    if "€" in text or "eur" in text_lower:
        currency = "EUR"
    elif "$" in text or "usd" in text_lower:
        currency = "USD"
    elif "gbp" in text_lower or "£" in text:
        currency = "GBP"
    elif "chf" in text_lower:
        currency = "CHF"

    # Detect period
    period = SalaryPeriod.MONTH
    if "/godz" in text_lower or "/h" in text_lower or "godz" in text_lower:
        period = SalaryPeriod.HOUR
    elif "/dzień" in text_lower or "/day" in text_lower or "/dniówka" in text_lower:
        period = SalaryPeriod.DAY
    elif "/rok" in text_lower or "/year" in text_lower or "rocznie" in text_lower:
        period = SalaryPeriod.YEAR

    # Detect brutto / netto
    salary_type = None
    if "brutto" in text_lower:
        salary_type = "brutto"
    elif "netto" in text_lower or "na rękę" in text_lower:
        salary_type = "netto"

    # Extract numbers — handle "12 500" (space-separated thousands) and "12,5" decimals
    # First, normalize separators: replace commas used as decimal separators
    normalized = text.replace(",", ".")

    # Find all number-like sequences (digits possibly separated by spaces, with optional decimal part)
    # Use word boundary to avoid matching digits inside words like "B2B"
    numbers = re.findall(r"(?<![A-Za-z])(\d[\d\s]*\d(?:\.\d+)?|\d+(?:\.\d+)?)(?![A-Za-z])", normalized)
    cleaned: list[float] = []
    for n in numbers:
        n = n.replace(" ", "").strip()
        if not n:
            continue
        try:
            val = float(n)
            # Filter out non-salary numbers based on period
            # Monthly: min 100 PLN, Hourly: min 5, Daily: min 20
            min_threshold = 5 if period == SalaryPeriod.HOUR else 20 if period == SalaryPeriod.DAY else 100
            if val < min_threshold:
                continue
            cleaned.append(val)
        except ValueError:
            continue

    if len(cleaned) >= 2:
        return min(cleaned[:2]), max(cleaned[:2]), currency, period, salary_type
    elif len(cleaned) == 1:
        return cleaned[0], cleaned[0], currency, period, salary_type

    return None, None, None, None, None


def _detect_seniority(text: str) -> Seniority:
    """Detect seniority level from text.

    For multi-level listings (e.g. "Junior/Mid/Senior"), returns the middle
    level as a reasonable default — avoids bias toward the lowest or highest.
    """
    text = text.lower()
    # Collect all detected levels with priority (higher = more senior)
    found: list[tuple[int, Seniority]] = []
    if "intern" in text or "staż" in text or "stażyst" in text or "praktyk" in text:
        found.append((0, Seniority.INTERN))
    if "junior" in text:
        found.append((1, Seniority.JUNIOR))
    if "mid" in text or "regular" in text or "specjalist" in text:
        found.append((2, Seniority.MID))
    if "senior" in text or "ekspert" in text:
        found.append((3, Seniority.SENIOR))
    if "lead" in text or "principal" in text:
        found.append((4, Seniority.LEAD))
    if "kierowni" in text or "manager" in text or "menedżer" in text or "dyrektor" in text:
        found.append((5, Seniority.MANAGER))

    if not found:
        return Seniority.UNKNOWN
    # For multi-level listings like "junior / mid / senior", return the middle level
    # For single match, return that level
    if len(found) == 1:
        return found[0][1]
    found.sort(key=lambda x: x[0])
    mid_idx = len(found) // 2
    return found[mid_idx][1]