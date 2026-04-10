"""Compare specific offers scraped vs website."""

import sys

sys.path.insert(0, ".")
from src.db.database import get_connection

conn = get_connection()
cur = conn.cursor()

# Check offers we can verify against the website
test_ids = ["10779866", "10706096", "10877479", "10877557"]

for sid in test_ids:
    cur.execute(
        """
        SELECT source_id, title, company_name, location_raw, location_city,
               salary_min, salary_max, salary_currency, work_mode, seniority, employment_type
        FROM job_offers WHERE source_id = %s
    """,
        (sid,),
    )
    r = cur.fetchone()
    if r:
        print(f"ID: {r[0]}")
        print(f"  Title:    {r[1]}")
        print(f"  Company:  {r[2]}")
        print(f"  Location: {r[3]} | City: {r[4]}")
        sal = f"{r[5]}-{r[6]} {r[7]}" if r[5] else "brak"
        print(f"  Salary:   {sal}")
        print(f"  Mode:     {r[8]} | Seniority: {r[9]} | Type: {r[10]}")
        print()
    else:
        print(f"ID {sid}: NOT FOUND in database")
        print()

cur.close()
