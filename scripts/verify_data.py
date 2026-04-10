"""Quick verification of scraped data."""

import sys

sys.path.insert(0, ".")

from src.db.database import get_connection

conn = get_connection()
cur = conn.cursor()

print("=== COUNTS ===")
cur.execute("SELECT count(*) FROM job_offers")
print("Total:", cur.fetchone()[0])
cur.execute("SELECT count(*) FROM job_offers WHERE salary_min IS NOT NULL")
print("With salary:", cur.fetchone()[0])
cur.execute("SELECT count(*) FROM job_offers WHERE location_city IS NOT NULL")
print("With city:", cur.fetchone()[0])
cur.execute("SELECT count(*) FROM job_offers WHERE company_name IS NOT NULL")
print("With company:", cur.fetchone()[0])
cur.execute("SELECT count(*) FROM job_offers WHERE work_mode != 'unknown'")
print("With work_mode:", cur.fetchone()[0])

print("\n=== SAMPLE OFFERS ===")
cur.execute("""
    SELECT title, company_name, location_city, salary_min, salary_max, salary_currency,
           work_mode, seniority, employment_type
    FROM job_offers LIMIT 10
""")
rows = cur.fetchall()
for r in rows:
    title = (r[0] or "")[:45]
    company = (r[1] or "")[:20]
    city = r[2] or ""
    salary = f"{r[3]}-{r[4]} {r[5] or ''}" if r[3] else "no salary"
    print(f"  {title:45s} | {company:20s} | {city:12s} | {salary:20s} | {r[6]:7s} | {r[7]:7s} | {r[8] or ''}")

print("\n=== TOP CITIES ===")
cur.execute("""
    SELECT location_city, count(*) as cnt
    FROM job_offers WHERE location_city IS NOT NULL
    GROUP BY 1 ORDER BY 2 DESC LIMIT 8
""")
rows = cur.fetchall()
for r in rows:
    print(f"  {r[0]:20s} {r[1]}")

print("\n=== WORK MODES ===")
cur.execute("SELECT work_mode, count(*) FROM job_offers GROUP BY 1 ORDER BY 2 DESC")
rows = cur.fetchall()
for r in rows:
    print(f"  {r[0]:10s} {r[1]}")

print("\n=== SENIORITY ===")
cur.execute("SELECT seniority, count(*) FROM job_offers GROUP BY 1 ORDER BY 2 DESC")
rows = cur.fetchall()
for r in rows:
    print(f"  {r[0]:10s} {r[1]}")

cur.close()
