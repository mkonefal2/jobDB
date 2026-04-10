"""Extract scraped data from DB for verification against website."""

import sys

sys.path.insert(0, ".")

from src.db.database import get_connection

conn = get_connection()

print("=== SCRAPED DATA SUMMARY ===")
total = conn.execute("SELECT count(*) FROM job_offers").fetchone()[0]
active = conn.execute("SELECT count(*) FROM job_offers WHERE is_active").fetchone()[0]
with_salary = conn.execute("SELECT count(*) FROM job_offers WHERE salary_min IS NOT NULL").fetchone()[0]
with_company = conn.execute(
    "SELECT count(*) FROM job_offers WHERE company_name IS NOT NULL AND company_name != ''"
).fetchone()[0]
with_location = conn.execute(
    "SELECT count(*) FROM job_offers WHERE location_raw IS NOT NULL AND location_raw != ''"
).fetchone()[0]
with_wm = conn.execute("SELECT count(*) FROM job_offers WHERE work_mode != 'unknown'").fetchone()[0]

print(f"Total offers: {total}")
print(f"Active: {active}")
print(f"With salary: {with_salary} ({100 * with_salary / total:.0f}%)")
print(f"With company: {with_company} ({100 * with_company / total:.0f}%)")
print(f"With location: {with_location} ({100 * with_location / total:.0f}%)")
print(f"With work_mode: {with_wm} ({100 * with_wm / total:.0f}%)")

print("\n=== FIRST 15 OFFERS ===")
rows = conn.execute("""
    SELECT source_id, title, company_name, location_raw, location_city,
           salary_min, salary_max, salary_currency, work_mode, seniority,
           employment_type, source_url
    FROM job_offers
    ORDER BY scraped_at DESC
    LIMIT 15
""").fetchall()

for i, r in enumerate(rows, 1):
    sid, title, company, loc_raw, city = r[0], r[1], r[2], r[3], r[4]
    sal_min, sal_max, sal_cur = r[5], r[6], r[7]
    wm, sen, emp, url = r[8], r[9], r[10], r[11]

    sal = f"{sal_min}-{sal_max} {sal_cur}" if sal_min else "brak"
    print(f"{i:2d}. [{sid}] {title[:55]}")
    print(f"    Company: {company or '-'}")
    print(f"    Location: {loc_raw or '-'} | City: {city or '-'}")
    print(f"    Salary: {sal} | Mode: {wm} | Seniority: {sen} | Type: {emp or '-'}")
    print(f"    URL: {url[:90]}")
    print()

print("=== WORK MODES ===")
for r in conn.execute("SELECT work_mode, count(*) FROM job_offers GROUP BY 1 ORDER BY 2 DESC").fetchall():
    print(f"  {r[0]:10s} {r[1]}")

print("\n=== SENIORITY ===")
for r in conn.execute("SELECT seniority, count(*) FROM job_offers GROUP BY 1 ORDER BY 2 DESC").fetchall():
    print(f"  {r[0]:10s} {r[1]}")

print("\n=== TOP CITIES ===")
for r in conn.execute("""
    SELECT location_city, count(*) FROM job_offers
    WHERE location_city IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 10
""").fetchall():
    print(f"  {r[0]:20s} {r[1]}")

print("\n=== SALARY STATS ===")
row = conn.execute("""
    SELECT count(*), avg(salary_min), avg(salary_max), min(salary_min), max(salary_max)
    FROM job_offers WHERE salary_min IS NOT NULL
""").fetchone()
print(f"  Offers with salary: {row[0]}")
print(f"  Avg min salary: {row[1]:.0f}" if row[1] else "  Avg min salary: -")
print(f"  Avg max salary: {row[2]:.0f}" if row[2] else "  Avg max salary: -")
print(f"  Range: {row[3]:.0f} - {row[4]:.0f}" if row[3] else "  Range: -")
