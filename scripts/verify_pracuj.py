"""
Automated data credibility verification for pracuj.pl scraper.
Compares scraped data from MySQL with live website data.
"""

import json
import sys
from datetime import datetime

sys.path.insert(0, ".")

from src.db.database import get_connection


def get_db_stats():
    """Get comprehensive stats from scraped pracuj.pl data."""
    conn = get_connection()
    cur = conn.cursor()
    stats = {}

    base_filter = "WHERE source = 'pracuj'"

    cur.execute(f"SELECT count(*) FROM job_offers {base_filter}")
    stats["total"] = cur.fetchone()[0]
    cur.execute(f"SELECT count(*) FROM job_offers {base_filter} AND is_active")
    stats["active"] = cur.fetchone()[0]
    cur.execute(f"SELECT count(*) FROM job_offers {base_filter} AND salary_min IS NOT NULL")
    stats["with_salary"] = cur.fetchone()[0]
    cur.execute(f"SELECT count(*) FROM job_offers {base_filter} AND company_name IS NOT NULL AND company_name != ''")
    stats["with_company"] = cur.fetchone()[0]
    cur.execute(f"SELECT count(*) FROM job_offers {base_filter} AND location_raw IS NOT NULL AND location_raw != ''")
    stats["with_location"] = cur.fetchone()[0]
    cur.execute(f"SELECT count(*) FROM job_offers {base_filter} AND location_city IS NOT NULL AND location_city != ''")
    stats["with_city"] = cur.fetchone()[0]
    cur.execute(f"SELECT count(*) FROM job_offers {base_filter} AND work_mode != 'unknown'")
    stats["with_work_mode"] = cur.fetchone()[0]
    cur.execute(f"SELECT count(*) FROM job_offers {base_filter} AND seniority != 'unknown'")
    stats["with_seniority"] = cur.fetchone()[0]
    cur.execute(f"SELECT count(*) FROM job_offers {base_filter} AND employment_type IS NOT NULL")
    stats["with_employment"] = cur.fetchone()[0]

    cur.close()
    return stats


def check_data_quality():
    """Identify specific data quality issues for pracuj.pl data."""
    conn = get_connection()
    cur = conn.cursor()
    issues = []

    base_filter = "source = 'pracuj'"

    # 1. Salary range sanity
    cur.execute(f"""
        SELECT source_id, title, salary_min, salary_max, salary_currency, salary_period
        FROM job_offers
        WHERE {base_filter}
          AND salary_min IS NOT NULL
          AND (salary_min > salary_max OR salary_min < 10 OR salary_max > 500000)
    """)
    bad_salary = cur.fetchall()
    for r in bad_salary:
        issues.append({
            "type": "salary_anomaly",
            "source_id": r[0],
            "title": r[1],
            "value": f"{r[2]}-{r[3]} {r[4]} /{r[5]}",
            "severity": "HIGH",
            "description": "Salary values outside reasonable range or min > max",
        })

    # 2. Missing city normalization
    cur.execute(f"""
        SELECT count(*) FROM job_offers
        WHERE {base_filter}
          AND location_raw IS NOT NULL AND location_raw != ''
          AND location_city IS NULL
    """)
    no_city = cur.fetchone()[0]
    if no_city > 0:
        cur.execute(f"""
            SELECT count(*) FROM job_offers
            WHERE {base_filter} AND location_raw IS NOT NULL AND location_raw != ''
        """)
        total_with_loc = cur.fetchone()[0]
        pct = 100 * no_city / total_with_loc if total_with_loc else 0
        issues.append({
            "type": "missing_city_norm",
            "count": no_city,
            "severity": "MEDIUM" if pct < 30 else "HIGH",
            "description": f"{no_city} offers ({pct:.0f}%) have location_raw but no normalized city",
        })

    # 3. Duplicate source_ids
    cur.execute(f"""
        SELECT source_id, count(*) as cnt FROM job_offers
        WHERE {base_filter}
        GROUP BY source_id HAVING cnt > 1
    """)
    dupes = cur.fetchall()
    for r in dupes:
        issues.append({
            "type": "duplicate_source_id",
            "source_id": r[0],
            "count": r[1],
            "severity": "HIGH",
            "description": "Duplicate source_id in database",
        })

    # 4. Empty titles
    cur.execute(f"""
        SELECT count(*) FROM job_offers
        WHERE {base_filter} AND (title IS NULL OR title = '' OR CHAR_LENGTH(title) < 3)
    """)
    empty_titles = cur.fetchone()[0]
    if empty_titles > 0:
        issues.append({
            "type": "empty_title",
            "count": empty_titles,
            "severity": "HIGH",
            "description": f"{empty_titles} offers have empty or very short titles",
        })

    # 5. Invalid URLs
    cur.execute(f"""
        SELECT count(*) FROM job_offers
        WHERE {base_filter} AND source_url NOT LIKE 'https://www.pracuj.pl/%%'
    """)
    bad_urls = cur.fetchone()[0]
    if bad_urls > 0:
        issues.append({
            "type": "invalid_url",
            "count": bad_urls,
            "severity": "MEDIUM",
            "description": f"{bad_urls} offers have URLs not matching pracuj.pl pattern",
        })

    # 6. Work mode all unknown
    cur.execute(f"""
        SELECT count(*) FROM job_offers
        WHERE {base_filter} AND work_mode = 'unknown'
    """)
    unknown_wm = cur.fetchone()[0]
    cur.execute(f"SELECT count(*) FROM job_offers WHERE {base_filter}")
    total = cur.fetchone()[0]
    if total > 0 and unknown_wm / total > 0.5:
        issues.append({
            "type": "mostly_unknown_work_mode",
            "count": unknown_wm,
            "severity": "HIGH",
            "description": f"{unknown_wm}/{total} offers have unknown work mode",
        })

    # 7. Salary type missing when salary present
    cur.execute(f"""
        SELECT count(*) FROM job_offers
        WHERE {base_filter} AND salary_min IS NOT NULL AND salary_type IS NULL
    """)
    no_type = cur.fetchone()[0]
    if no_type > 0:
        issues.append({
            "type": "salary_missing_type",
            "count": no_type,
            "severity": "LOW",
            "description": f"{no_type} offers have salary but no brutto/netto type",
        })

    cur.close()
    return issues


def verify_sample_offers():
    """Verify a few sample offers against live data using Playwright."""
    conn = get_connection()
    cur = conn.cursor()

    # Get a sample of offers with salary to verify
    cur.execute("""
        SELECT source_id, title, company_name, location_raw, salary_min, salary_max,
               salary_currency, salary_period, work_mode, seniority, employment_type,
               source_url
        FROM job_offers
        WHERE source = 'pracuj' AND salary_min IS NOT NULL
        ORDER BY scraped_at DESC
        LIMIT 5
    """)
    samples = cur.fetchall()
    cur.close()

    if not samples:
        print("  No offers with salary found for verification")
        return 0, 0

    correct = 0
    total_checks = 0

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            for row in samples[:3]:  # Verify 3 offers
                sid, title, company, loc, sal_min, sal_max, cur, period, wm, sen, emp, url = row
                print(f"\n  Oferta {sid}: {title[:55]}")

                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/131.0.0.0 Safari/537.36"
                    ),
                    locale="pl-PL",
                )
                page = context.new_page()
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_selector("#__NEXT_DATA__", state="attached", timeout=10000)
                    raw = page.evaluate(
                        "() => { const el = document.getElementById('__NEXT_DATA__'); "
                        "return el ? el.textContent : null; }"
                    )

                    if raw:
                        detail = json.loads(raw)
                        pp = detail.get("props", {}).get("pageProps", {})
                        ds = pp.get("dehydratedState", {})
                        queries = ds.get("queries", [])

                        # Find the jobOffer query
                        offer_data = None
                        for q in queries:
                            d = q.get("state", {}).get("data", {})
                            if isinstance(d, dict) and "attributes" in d:
                                offer_data = d
                                break

                        if offer_data:
                            attrs = offer_data.get("attributes", {})

                            # Title check
                            live_title = attrs.get("jobTitle", "")
                            total_checks += 1
                            if live_title.strip() == title.strip():
                                print(f"    ✅ Tytuł: ZGODNY")
                                correct += 1
                            else:
                                print(f"    🔴 Tytuł: DB='{title[:40]}' vs LIVE='{live_title[:40]}'")

                            # Company check
                            live_company = attrs.get("displayEmployerName", "")
                            if live_company:
                                total_checks += 1
                                if (company or "").strip() == live_company.strip():
                                    print(f"    ✅ Firma: ZGODNA")
                                    correct += 1
                                else:
                                    print(f"    🔴 Firma: DB='{company}' vs LIVE='{live_company}'")

                            # URL check
                            live_url = attrs.get("offerAbsoluteUrl", "")
                            if live_url:
                                total_checks += 1
                                if url.rstrip("/") == live_url.rstrip("/"):
                                    print(f"    ✅ URL: ZGODNY")
                                    correct += 1
                                else:
                                    print(f"    🔴 URL: niezgodny")
                        else:
                            print(f"    ⚠️  Brak danych oferty w __NEXT_DATA__")
                    else:
                        print(f"    ⚠️  Nie udało się pobrać danych ze strony")

                except Exception as e:
                    print(f"    ⚠️  Błąd weryfikacji: {e}")
                finally:
                    page.close()
                    context.close()

            browser.close()
    except ImportError:
        print("  ⚠️  Playwright nie zainstalowany, pomijam weryfikację live")

    return correct, total_checks


def generate_report():
    """Generate full credibility report for pracuj.pl scraper."""
    stats = get_db_stats()
    issues = check_data_quality()

    total = stats["total"]
    if total == 0:
        print("❌ Brak danych pracuj.pl w bazie. Uruchom scraper najpierw.")
        return

    print("=" * 70)
    print("  RAPORT WIARYGODNOŚCI DANYCH — pracuj.pl scraper")
    print(f"  Data: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    # Coverage stats
    print(f"\n📊 POKRYCIE DANYCH ({total} ofert):")
    coverage_fields = [
        ("with_company", "Firma"),
        ("with_location", "Lokalizacja (raw)"),
        ("with_city", "Miasto (znormalizowane)"),
        ("with_work_mode", "Tryb pracy"),
        ("with_seniority", "Poziom doświadczenia"),
        ("with_salary", "Wynagrodzenie"),
        ("with_employment", "Typ umowy"),
    ]

    coverage_pcts = []
    for key, label in coverage_fields:
        val = stats[key]
        pct = 100 * val / total if total else 0
        coverage_pcts.append(pct)
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"  {label:30s} {bar} {pct:5.1f}% ({val}/{total})")

    avg_coverage = sum(coverage_pcts) / len(coverage_pcts)

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
            title_str = issue.get("title", "")[:50]
            print(f"       ID: {issue['source_id']} | {title_str} | value: {issue.get('value', '')}")

    # Sample data preview
    conn = get_connection()
    cur = conn.cursor()
    print("\n📋 PRÓBKA DANYCH:")
    cur.execute("""
        SELECT source_id, title, company_name, location_raw, location_city,
               salary_min, salary_max, salary_currency, work_mode, seniority, employment_type
        FROM job_offers WHERE source = 'pracuj'
        ORDER BY RAND() LIMIT 5
    """)
    samples = cur.fetchall()
    for s in samples:
        sid, title, comp, loc_r, loc_c, smin, smax, scur, wm, sen, emp = s
        sal_str = f"{smin}-{smax} {scur}" if smin else "brak"
        print(f"  [{sid}] {title[:45]}")
        print(f"    Firma: {comp or '-'} | Lok: {loc_r or '-'} → {loc_c or '-'}")
        print(f"    Salary: {sal_str} | Mode: {wm} | Sen: {sen} | Emp: {emp or '-'}")
    # Live verification
    print("\n🔍 WERYFIKACJA LIVE (porównanie z website):")
    correct, total_checks = verify_sample_offers()

    # Calculate final score
    # Coverage score: 40% weight
    # Issue severity score: 30% weight (each HIGH issue -10%, MEDIUM -3%, LOW -1%)
    # Live verification score: 30% weight
    coverage_score = avg_coverage
    issue_penalty = min(100, len(high) * 10 + len(medium) * 3 + len(low) * 1)
    issue_score = max(0, 100 - issue_penalty)
    live_score = (correct / total_checks * 100) if total_checks > 0 else 50  # assume 50% if no checks

    final_score = (coverage_score * 0.4 + issue_score * 0.3 + live_score * 0.3)

    print("\n" + "=" * 70)
    print(f"  OGÓLNA OCENA WIARYGODNOŚCI: {final_score:.0f}%")
    print("=" * 70)
    print(f"""
  Pokrycie danych:       {coverage_score:.0f}% (średnia z {len(coverage_fields)} pól)
  Jakość danych:         {issue_score:.0f}% (kary: {len(high)}×HIGH, {len(medium)}×MEDIUM, {len(low)}×LOW)
  Weryfikacja live:      {live_score:.0f}% ({correct}/{total_checks} sprawdzeń)
  
  Wynik końcowy:         {final_score:.0f}%
  Cel:                   80%
  Status:                {"✅ OSIĄGNIĘTO CEL" if final_score >= 80 else "❌ CEL NIE OSIĄGNIĘTY"}
""")

    return final_score


if __name__ == "__main__":
    score = generate_report()
