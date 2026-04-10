"""Debug salary parsing - find correct HTML selectors."""

import sys

sys.path.insert(0, ".")
from selectolax.parser import HTMLParser

from src.scrapers.pracapl import PracaPLScraper

scraper = PracaPLScraper(max_pages=1)
r = scraper.fetch("https://www.praca.pl/oferty-pracy.html")
tree = HTMLParser(r.text)
cards = tree.css("ul.listing:not(.listing--week-offer) li.listing__item")

for card in cards:
    text = card.text()
    if "brutto" in text.lower() or "netto" in text.lower():
        print("=== CARD WITH SALARY ===")
        # List all child elements and their classes
        for child in card.css("*"):
            cls = child.attributes.get("class", "")
            if cls:
                txt = child.text(strip=True)[:80]
                print(f"  <{child.tag} class='{cls}'> {txt}")
        print()
        print("=== RAW HTML ===")
        print(card.html[:3000])
        break

scraper.close()
