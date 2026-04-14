from __future__ import annotations

import random
import time
from abc import ABC, abstractmethod
from datetime import datetime

import httpx
from rich.console import Console
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from config.settings import DEFAULT_DELAY_SECONDS, MAX_RETRIES, REQUEST_TIMEOUT, USER_AGENTS
from src.models.schema import JobOffer, ScrapedResult, ScrapeStatus, Source

console = Console()


class BaseScraper(ABC):
    source: Source
    base_url: str
    delay: float = DEFAULT_DELAY_SECONDS

    def __init__(self, max_pages: int | None = None):
        self.max_pages = max_pages
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                timeout=REQUEST_TIMEOUT,
                follow_redirects=True,
                headers=self._default_headers(),
            )
        return self._client

    def _default_headers(self) -> dict[str, str]:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
        }

    def _wait(self) -> None:
        jitter = random.uniform(0.5, 1.5)
        time.sleep(self.delay * jitter)

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout)),
    )
    def fetch(self, url: str, **kwargs) -> httpx.Response:
        response = self.client.get(url, **kwargs)
        response.raise_for_status()
        return response

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout)),
    )
    def fetch_json(self, url: str, **kwargs) -> dict | list:
        headers = {**self._default_headers(), "Accept": "application/json"}
        response = self.client.get(url, headers=headers, **kwargs)
        response.raise_for_status()
        return response.json()

    @abstractmethod
    def scrape_listings(self, page: int) -> list[JobOffer]:
        """Scrape a single listing page and return parsed offers."""
        ...

    def scrape_detail(self, offer: JobOffer) -> JobOffer:
        """Optionally enrich an offer with detail page data. Default: no-op."""
        return offer

    def scrape(self) -> ScrapedResult:
        result = ScrapedResult(source=self.source, started_at=datetime.utcnow())
        page = 1

        console.print(f"[bold cyan]Starting scrape: {self.source.value}[/]")

        try:
            while True:
                if self.max_pages and page > self.max_pages:
                    break

                console.print(f"  Page {page}...", end=" ")
                try:
                    offers = self.scrape_listings(page)
                except Exception as e:
                    # Retry page 1 once before giving up entirely
                    if page == 1 and not result.errors:
                        console.print(f"[yellow]RETRY page 1: {e}[/]")
                        result.errors += 1
                        self._wait()
                        try:
                            offers = self.scrape_listings(page)
                        except Exception as e2:
                            console.print(f"[red]FAILED after retry: {e2}[/]")
                            result.errors += 1
                            result.status = ScrapeStatus.FAILED
                            break
                    else:
                        console.print(f"[red]ERROR: {e}[/]")
                        result.errors += 1
                        result.status = ScrapeStatus.PARTIAL if page > 1 else ScrapeStatus.FAILED
                        break

                if not offers:
                    console.print("[dim]no more results[/]")
                    break

                console.print(f"[green]{len(offers)} offers[/]")
                result.offers.extend(offers)
                result.pages_scraped = page
                page += 1
                self._wait()

        finally:
            self.close()
            result.finished_at = datetime.utcnow()
            console.print(
                f"[bold]Finished {self.source.value}: "
                f"{len(result.offers)} offers, {result.pages_scraped} pages, "
                f"{result.errors} errors, status={result.status.value}[/]"
            )

        return result

    def close(self) -> None:
        if self._client and not self._client.is_closed:
            self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
