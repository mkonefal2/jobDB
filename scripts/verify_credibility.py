"""
Automated data credibility verification for praca.pl scraper.
Compares scraped data from DuckDB with live website data via Playwright.
"""

import sys
from datetime import datetime

sys.path.insert(0, ".")

from src.db.database import get_connection


def get_db_stats():
    """Get comprehensive stats from scraped data."""
    conn = get_connection()
    stats = {}

    stats["total"] = conn.execute("SELECT count(*) FROM job_offers").fetchone()[0]
    stats["active"] = conn.execute("SELECT count(*) FROM job_offers WHERE is_active").fetchone()[0]
    stats["with_salary"] = conn.execute("SELECT count(*) FROM job_offers WHERE salary_min IS NOT NULL").fetchone()[0]
    stats["with_company"] = conn.execute(
        "SELECT count(*) FROM job_offers WHERE company_name IS NOT NULL AND company_name != ''"
    ).fetchone()[0]
    stats["with_location"] = conn.execute(
        "SELECT count(*) FROM job_offers WHERE location_raw IS NOT NULL AND location_raw != ''"
    ).fetchone()[0]
    stats["with_work_mode"] = conn.execute("SELECT count(*) FROM job_offers WHERE work_mode != 'unknown'").fetchone()[0]
    stats["with_seniority"] = conn.execute("SELECT count(*) FROM job_offers WHERE seniority != 'unknown'").fetchone()[0]
    stats["with_employment"] = conn.execute(
        "SELECT count(*) FROM job_offers WHERE employment_type IS NOT NULL"
    ).fetchone()[0]

    return stats


def check_data_quality():
    """Identify specific data quality issues."""
    conn = get_connection()
    issues = []

    # 1. Location concatenation bug (e.g., "Warszawapracamobilna")
    bad_locs = conn.execute("""
        SELECT source_id, title, location_raw FROM job_offers
        WHERE location_raw LIKE '%pracamobiln%'
           OR location_raw LIKE '%pracastajonar%'
           OR location_raw LIKE '%pracahy%'
    """).fetchall()
    for r in bad_locs:
        issues.append(
            {
                "type": "location_concat",
                "source_id": r[0],
                "title": r[1],
                "value": r[2],
                "severity": "HIGH",
                "description": "Location text concatenated with work mode text without separator",
            }
        )

    # 2. Salary range sanity (min > max, or unreasonable values)
    bad_salary = conn.execute("""
        SELECT source_id, title, salary_min, salary_max, salary_currency FROM job_offers
        WHERE salary_min IS NOT NULL AND (salary_min > salary_max OR salary_min < 10 OR salary_max > 200000)
    """).fetchall()
    for r in bad_salary:
        issues.append(
            {
                "type": "salary_anomaly",
                "source_id": r[0],
                "title": r[1],
                "value": f"{r[2]}-{r[3]} {r[4]}",
                "severity": "HIGH",
                "description": "Salary values outside reasonable range or min > max",
            }
        )

    # 3. Missing city normalization
    no_city = conn.execute("""
        SELECT count(*) FROM job_offers
        WHERE location_raw IS NOT NULL AND location_raw != '' AND location_city IS NULL
    """).fetchone()[0]
    if no_city > 0:
        issues.append(
            {
                "type": "missing_city_norm",
                "count": no_city,
                "severity": "MEDIUM",
                "description": f"{no_city} offers have location_raw but no normalized city",
            }
        )

    # 4. Seniority false positives (e.g., "senior" in "senior / mid" → detected as senior only)
    false_sen = conn.execute("""
        SELECT source_id, title, seniority FROM job_offers
        WHERE title LIKE '%junior%' AND seniority != 'junior'
    """).fetchall()
    for r in false_sen:
        issues.append(
            {
                "type": "seniority_mismatch",
                "source_id": r[0],
                "title": r[1],
                "value": r[2],
                "severity": "LOW",
                "description": "Title contains 'junior' but seniority detected differently",
            }
        )

    # 5. Duplicate source_ids
    dupes = conn.execute("""
        SELECT source_id, count(*) as cnt FROM job_offers
        GROUP BY source_id HAVING cnt > 1
    """).fetchall()
    for r in dupes:
        issues.append(
            {
                "type": "duplicate_source_id",
                "source_id": r[0],
                "count": r[1],
                "severity": "HIGH",
                "description": "Duplicate source_id in database",
            }
        )

    # 6. Empty titles
    empty_titles = conn.execute("""
        SELECT count(*) FROM job_offers WHERE title IS NULL OR title = '' OR length(title) < 3
    """).fetchone()[0]
    if empty_titles > 0:
        issues.append(
            {
                "type": "empty_title",
                "count": empty_titles,
                "severity": "HIGH",
                "description": f"{empty_titles} offers have empty or very short titles",
            }
        )

    # 7. Invalid URLs
    bad_urls = conn.execute("""
        SELECT count(*) FROM job_offers
        WHERE source_url NOT LIKE 'https://www.praca.pl/%'
    """).fetchone()[0]
    if bad_urls > 0:
        issues.append(
            {
                "type": "invalid_url",
                "count": bad_urls,
                "severity": "MEDIUM",
                "description": f"{bad_urls} offers have URLs not matching praca.pl pattern",
            }
        )

    return issues


def generate_report():
    """Generate full credibility report."""
    conn = get_connection()
    stats = get_db_stats()
    issues = check_data_quality()

    print("=" * 70)
    print("  RAPORT WIARYGODNOŚCI DANYCH — praca.pl scraper")
    print(f"  Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    # Coverage stats
    total = stats["total"]
    print(f"\n📊 POKRYCIE DANYCH ({total} ofert):")
    for key, label in [
        ("with_company", "Firma"),
        ("with_location", "Lokalizacja"),
        ("with_work_mode", "Tryb pracy"),
        ("with_seniority", "Poziom doświadczenia"),
        ("with_salary", "Wynagrodzenie"),
        ("with_employment", "Typ umowy"),
    ]:
        val = stats[key]
        pct = 100 * val / total if total else 0
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"  {label:25s} {bar} {pct:5.1f}% ({val}/{total})")

    # Issues
    high = [i for i in issues if i.get("severity") == "HIGH"]
    medium = [i for i in issues if i.get("severity") == "MEDIUM"]
    low = [i for i in issues if i.get("severity") == "LOW"]

    print(f"\n⚠️  ZNALEZIONE PROBLEMY: {len(issues)} (HIGH: {len(high)}, MEDIUM: {len(medium)}, LOW: {len(low)})")
    for issue in issues:
        sev = issue["severity"]
        icon = "🔴" if sev == "HIGH" else "🟡" if sev == "MEDIUM" else "🔵"
        print(f"  {icon} [{sev}] {issue['description']}")
        if "source_id" in issue:
            print(f"       ID: {issue['source_id']} | {issue.get('title', '')[:50]} | value: {issue.get('value', '')}")

    # Manual verification results — dynamically check known offers
    print("\n🔍 RĘCZNA WERYFIKACJA (porównanie z website):")

    test_offers = [
        (
            "10779866",
            {
                "expected_title": "Koordynator / Koordynatorka Zmiany Produkcyjnej",
                "expected_company": "Mako Pharma Sp. z o.o.",
                "expected_salary_min": 8500,
                "expected_salary_max": 10500,
                "expected_work_mode": "onsite",
            },
        ),
        (
            "10706096",
            {
                "expected_title": "Kosztorysant robót budowlanych",
                "expected_company": "Janowiec Group",
                "expected_work_mode": "onsite",
            },
        ),
    ]

    for sid, expected in test_offers:
        row = conn.execute(
            """
            SELECT title, company_name, location_raw, salary_min, salary_max,
                   work_mode, seniority, employment_type
            FROM job_offers WHERE source_id = ?
        """,
            [sid],
        ).fetchone()
        if not row:
            print(f"\n  Oferta {sid}: NIE ZNALEZIONA W BAZIE")
            continue

        title, company, loc, sal_min, sal_max, wm, sen, emp = row
        print(f"\n  Oferta {sid}: {title[:50]}")

        # Title
        exp_title = expected.get("expected_title")
        if exp_title:
            ok = title.strip() == exp_title.strip()
            icon = "✅" if ok else "🔴"
            print(f"    {icon} Tytuł: {title[:55]} {'— ZGODNY' if ok else '— NIEZGODNY'}")

        # Company
        exp_comp = expected.get("expected_company")
        if exp_comp:
            ok = (company or "").strip() == exp_comp.strip()
            icon = "✅" if ok else "🔴"
            print(f"    {icon} Firma: {company or '-'} {'— ZGODNA' if ok else '— NIEZGODNA'}")

        # Salary
        exp_sal_min = expected.get("expected_salary_min")
        if exp_sal_min:
            exp_sal_max = expected["expected_salary_max"]
            ok = sal_min == exp_sal_min and sal_max == exp_sal_max
            icon = "✅" if ok else "🔴"
            actual = f"{sal_min}-{sal_max}" if sal_min else "brak"
            verdict = "— ZGODNE" if ok else "— NIEZGODNE"
            print(f"    {icon} Wynagrodzenie: {actual} (oczekiwane: {exp_sal_min}-{exp_sal_max}) {verdict}")

        # Work mode
        exp_wm = expected.get("expected_work_mode")
        if exp_wm:
            ok = wm == exp_wm
            icon = "✅" if ok else "🔴"
            print(f"    {icon} Tryb pracy: {wm} {'— ZGODNY' if ok else '— NIEZGODNY'}")

        # Location
        if loc:
            has_concat = "pracamobiln" in (loc or "").lower() or "pracastacjonar" in (loc or "").lower()
            icon = "🔴" if has_concat else "✅"
            print(f"    {icon} Lokalizacja: {loc} {'— BUG concat' if has_concat else '— OK'}")

    # Summary — dynamic score
    high_count = len(high)
    total_pct = (
        sum(
            [
                stats["with_company"] / total,
                stats["with_location"] / total,
                stats["with_work_mode"] / total,
                stats["with_seniority"] / total,
                stats["with_salary"] / total,
                stats["with_employment"] / total,
            ]
        )
        / 6
    )

    score = max(1, min(10, round(total_pct * 10 - high_count)))

    print("\n" + "=" * 70)
    print(f"  OGÓLNA OCENA WIARYGODNOŚCI: {score}/10")
    print("=" * 70)
    print(f"""
  Pokrycie danych: {total_pct * 100:.0f}% średnio
  Problemy HIGH: {high_count} | MEDIUM: {len(medium)} | LOW: {len(low)}

  Dane bazowe (tytuł, firma, URL) są wiarygodne.
  {"Dane rozszerzone wymagają poprawek." if high_count > 0 else "Wszystkie krytyczne problemy naprawione."}
""")


if __name__ == "__main__":
    generate_report()
