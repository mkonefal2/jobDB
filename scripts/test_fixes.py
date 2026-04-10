"""Quick test of fixed scraper."""

import sys

sys.path.insert(0, ".")
from src.scrapers.pracapl import PracaPLScraper

scraper = PracaPLScraper(max_pages=1)
offers = scraper.scrape_listings(1)
print(f"Total: {len(offers)}")
with_sal = [o for o in offers if o.salary_min]
print(f"With salary: {len(with_sal)}")
print()

for o in offers[:10]:
    sal = f"{o.salary_min}-{o.salary_max} {o.salary_currency}" if o.salary_min else "brak"
    loc = (o.location_raw or "-")[:30]
    title = o.title[:45]
    print(f"  {title}")
    print(
        f"    loc={loc} | wm={o.work_mode.value} | sen={o.seniority.value} | emp={o.employment_type or '-'} | sal={sal}"
    )

print("\n=== Offers with salary ===")
for o in with_sal:
    print(f"  {o.title[:45]} | {o.salary_min}-{o.salary_max} {o.salary_currency} {o.salary_type or ''}")

scraper.close()
