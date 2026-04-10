"""Quick verification of scraped data."""

import sys

sys.path.insert(0, ".")

from src.db.database import get_connection

conn = get_connection()

print("=== COUNTS ===")
print("Total:", conn.execute("SELECT count(*) FROM job_offers").fetchone()[0])
print("With salary:", conn.execute("SELECT count(*) FROM job_offers WHERE salary_min IS NOT NULL").fetchone()[0])
print("With city:", conn.execute("SELECT count(*) FROM job_offers WHERE location_city IS NOT NULL").fetchone()[0])
print("With company:", conn.execute("SELECT count(*) FROM job_offers WHERE company_name IS NOT NULL").fetchone()[0])
print("With work_mode:", conn.execute("SELECT count(*) FROM job_offers WHERE work_mode != 'unknown'").fetchone()[0])

print("\n=== SAMPLE OFFERS ===")
rows = conn.execute("""
    SELECT title, company_name, location_city, salary_min, salary_max, salary_currency,
           work_mode, seniority, employment_type
    FROM job_offers LIMIT 10
""").fetchall()
for r in rows:
    title = (r[0] or "")[:45]
    company = (r[1] or "")[:20]
    city = r[2] or ""
    salary = f"{r[3]}-{r[4]} {r[5] or ''}" if r[3] else "no salary"
    print(f"  {title:45s} | {company:20s} | {city:12s} | {salary:20s} | {r[6]:7s} | {r[7]:7s} | {r[8] or ''}")

print("\n=== TOP CITIES ===")
rows = conn.execute("""
    SELECT location_city, count(*) as cnt
    FROM job_offers WHERE location_city IS NOT NULL
    GROUP BY 1 ORDER BY 2 DESC LIMIT 8
""").fetchall()
for r in rows:
    print(f"  {r[0]:20s} {r[1]}")

print("\n=== WORK MODES ===")
rows = conn.execute("SELECT work_mode, count(*) FROM job_offers GROUP BY 1 ORDER BY 2 DESC").fetchall()
for r in rows:
    print(f"  {r[0]:10s} {r[1]}")

print("\n=== SENIORITY ===")
rows = conn.execute("SELECT seniority, count(*) FROM job_offers GROUP BY 1 ORDER BY 2 DESC").fetchall()
for r in rows:
    print(f"  {r[0]:10s} {r[1]}")
