"""FastAPI backend for the HTML dashboard.

Exposes REST endpoints that mirror all 69 DAX measures from the Power BI model.
Each endpoint computes equivalent logic in SQL against the MySQL jobdb database.
"""

from __future__ import annotations

import statistics
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import mysql.connector
from config.settings import MYSQL_CONFIG

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

HTML_DIR = Path(__file__).resolve().parent


def _conn():
    """Create a fresh MySQL connection (thread-safe for concurrent requests)."""
    return mysql.connector.connect(**MYSQL_CONFIG)


def _where(
    *,
    source: list[str] | None = None,
    city: list[str] | None = None,
    work_mode: list[str] | None = None,
    seniority: list[str] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    active_only: bool = False,
    alias: str = "",
) -> tuple[str, list]:
    """Build a WHERE clause + params from filter arguments."""
    prefix = f"{alias}." if alias else ""
    clauses: list[str] = []
    params: list[Any] = []
    if active_only:
        clauses.append(f"{prefix}is_active = 1")
    if source:
        clauses.append(f"{prefix}source IN ({','.join(['%s'] * len(source))})")
        params.extend(source)
    if city:
        clauses.append(f"{prefix}location_city IN ({','.join(['%s'] * len(city))})")
        params.extend(city)
    if work_mode:
        clauses.append(f"{prefix}work_mode IN ({','.join(['%s'] * len(work_mode))})")
        params.extend(work_mode)
    if seniority:
        clauses.append(f"{prefix}seniority IN ({','.join(['%s'] * len(seniority))})")
        params.extend(seniority)
    if date_from:
        clauses.append(f"{prefix}scraped_at >= %s")
        params.append(datetime.combine(date_from, datetime.min.time()))
    if date_to:
        clauses.append(f"{prefix}scraped_at <= %s")
        params.append(datetime.combine(date_to, datetime.max.time()))
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    return where, params


def _query(sql: str, params: list | None = None) -> list[dict]:
    conn = _conn()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, params or [])
        rows = cur.fetchall()
        cur.close()
        return rows
    finally:
        conn.close()


def _query_one(sql: str, params: list | None = None) -> dict:
    rows = _query(sql, params)
    return rows[0] if rows else {}


def _safe_div(a, b, default=0):
    if b is None or b == 0:
        return default
    return a / b


# Common filter dependency
def _filters(
    source: list[str] | None = Query(None),
    city: list[str] | None = Query(None),
    work_mode: list[str] | None = Query(None),
    seniority: list[str] | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    active_only: bool = Query(False),
):
    return dict(
        source=source,
        city=city,
        work_mode=work_mode,
        seniority=seniority,
        date_from=date_from,
        date_to=date_to,
        active_only=active_only,
    )


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    # warm up connection
    _conn()
    yield


app = FastAPI(title="jobDB Dashboard API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Salary helpers
# ---------------------------------------------------------------------------

_MONTHLY_FACTOR = {
    "month": 1,
    "hour": 168,
    "day": 21,
    "year": 1 / 12,
}


def _normalize_monthly(salary_min, salary_max, period):
    factor = _MONTHLY_FACTOR.get(period)
    if factor is None or salary_min is None or salary_max is None:
        return None
    mid = (salary_min + salary_max) / 2
    return mid * factor


def _salary_band(monthly):
    if monthly is None:
        return "Brak danych"
    if monthly < 5000:
        return "< 5 000 PLN"
    if monthly < 8000:
        return "5 000 – 7 999"
    if monthly < 12000:
        return "8 000 – 11 999"
    if monthly < 16000:
        return "12 000 – 15 999"
    if monthly < 22000:
        return "16 000 – 21 999"
    if monthly < 30000:
        return "22 000 – 29 999"
    return "30 000+ PLN"


_SALARY_BAND_ORDER = {
    "Brak danych": 99,
    "< 5 000 PLN": 1,
    "5 000 – 7 999": 2,
    "8 000 – 11 999": 3,
    "12 000 – 15 999": 4,
    "16 000 – 21 999": 5,
    "22 000 – 29 999": 6,
    "30 000+ PLN": 7,
}


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * p
    f = int(k)
    c = f + 1
    if c >= len(s):
        return s[f]
    return s[f] + (k - f) * (s[c] - s[f])


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/api/filters")
def get_filters():
    """Return distinct values for all filter controls."""
    sources = _query("SELECT DISTINCT source FROM job_offers ORDER BY source")
    cities = _query(
        "SELECT location_city, COUNT(*) as cnt FROM job_offers "
        "WHERE location_city IS NOT NULL GROUP BY location_city ORDER BY cnt DESC LIMIT 50"
    )
    work_modes = _query(
        "SELECT DISTINCT work_mode FROM job_offers ORDER BY work_mode"
    )
    seniorities = _query(
        "SELECT DISTINCT seniority FROM job_offers ORDER BY seniority"
    )
    return {
        "sources": [r["source"] for r in sources],
        "cities": [r["location_city"] for r in cities],
        "work_modes": [r["work_mode"] for r in work_modes],
        "seniorities": [r["seniority"] for r in seniorities],
    }


@app.get("/api/kpi")
def get_kpi(
    source: list[str] | None = Query(None),
    city: list[str] | None = Query(None),
    work_mode: list[str] | None = Query(None),
    seniority: list[str] | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    active_only: bool = Query(False),
):
    """📊 KPI folder — 8 core measures."""
    w, p = _where(
        source=source, city=city, work_mode=work_mode,
        seniority=seniority, date_from=date_from, date_to=date_to,
        active_only=active_only,
    )
    r = _query_one(
        f"""
        SELECT
            COUNT(*) AS total_offers,
            SUM(is_active = 1) AS active_offers,
            SUM(is_active = 0) AS inactive_offers,
            SUM(salary_min IS NOT NULL AND salary_min > 0) AS offers_with_salary,
            COUNT(DISTINCT company_name) AS unique_companies,
            COUNT(DISTINCT location_city) AS unique_cities,
            COUNT(DISTINCT source) AS unique_sources,
            AVG(CASE WHEN salary_min > 0 AND salary_max > 0
                THEN (salary_min + salary_max) / 2 END) AS avg_salary_midpoint,
            MAX(scraped_at) AS last_scrape_time
        FROM job_offers
        {w}
        """,
        p,
    )
    total = r.get("total_offers") or 0
    with_salary = r.get("offers_with_salary") or 0
    transparency = _safe_div(with_salary, total) * 100 if total else 0

    last_scrape = r.get("last_scrape_time")
    freshness_hours = None
    freshness_status = "Brak danych"
    if last_scrape:
        if isinstance(last_scrape, str):
            last_scrape = datetime.fromisoformat(last_scrape)
        freshness_hours = int((datetime.now() - last_scrape).total_seconds() / 3600)
        if freshness_hours <= 6:
            freshness_status = "Świeże"
        elif freshness_hours <= 24:
            freshness_status = "Do odświeżenia"
        else:
            freshness_status = "Nieaktualne"

    return {
        "total_offers": total,
        "active_offers": r.get("active_offers") or 0,
        "inactive_offers": r.get("inactive_offers") or 0,
        "offers_with_salary": with_salary,
        "salary_transparency_pct": round(transparency, 1),
        "unique_companies": r.get("unique_companies") or 0,
        "unique_cities": r.get("unique_cities") or 0,
        "unique_sources": r.get("unique_sources") or 0,
        "avg_salary_midpoint": round(r.get("avg_salary_midpoint") or 0),
        "last_scrape_time": str(last_scrape) if last_scrape else None,
        "data_freshness_hours": freshness_hours,
        "data_freshness_status": freshness_status,
    }


@app.get("/api/salary")
def get_salary(
    source: list[str] | None = Query(None),
    city: list[str] | None = Query(None),
    work_mode: list[str] | None = Query(None),
    seniority: list[str] | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    active_only: bool = Query(False),
):
    """💰 Wynagrodzenia folder — 12 salary measures."""
    w, p = _where(
        source=source, city=city, work_mode=work_mode,
        seniority=seniority, date_from=date_from, date_to=date_to,
        active_only=active_only,
    )

    # Core averages
    r = _query_one(
        f"""
        SELECT
            AVG(CASE WHEN salary_min > 0 THEN salary_min END) AS avg_salary_min,
            AVG(CASE WHEN salary_max > 0 THEN salary_max END) AS avg_salary_max,
            AVG(CASE WHEN salary_min > 0 AND salary_max > 0
                THEN (salary_min + salary_max) / 2 END) AS avg_salary_midpoint,
            AVG(CASE WHEN salary_min > 0 AND salary_max > 0
                THEN salary_max - salary_min END) AS avg_salary_spread
        FROM job_offers
        {w}
        """,
        p,
    )

    # Fetch midpoints for percentile calculations
    rows = _query(
        f"""
        SELECT (salary_min + salary_max) / 2 AS mid,
               salary_period, salary_min, salary_max, salary_currency
        FROM job_offers
        {w} {"AND" if w else "WHERE"} salary_min > 0 AND salary_max > 0
        """,
        p,
    )
    midpoints = [float(row["mid"]) for row in rows]

    # Monthly normalized (PLN only)
    monthly_vals = []
    for row in rows:
        if row.get("salary_currency") == "PLN":
            m = _normalize_monthly(
                float(row["salary_min"]), float(row["salary_max"]),
                row.get("salary_period"),
            )
            if m is not None:
                monthly_vals.append(m)

    return {
        "avg_salary_min": round(r.get("avg_salary_min") or 0),
        "avg_salary_max": round(r.get("avg_salary_max") or 0),
        "avg_salary_midpoint": round(r.get("avg_salary_midpoint") or 0),
        "median_salary_midpoint": round(statistics.median(midpoints)) if midpoints else 0,
        "salary_p10": round(_percentile(midpoints, 0.10) or 0),
        "salary_p25": round(_percentile(midpoints, 0.25) or 0),
        "salary_p75": round(_percentile(midpoints, 0.75) or 0),
        "salary_p90": round(_percentile(midpoints, 0.90) or 0),
        "avg_salary_spread": round(r.get("avg_salary_spread") or 0),
        "avg_monthly_salary_pln": round(statistics.mean(monthly_vals)) if monthly_vals else 0,
        "median_monthly_salary_pln": round(statistics.median(monthly_vals)) if monthly_vals else 0,
    }


@app.get("/api/salary/by-seniority")
def get_salary_by_seniority(
    source: list[str] | None = Query(None),
    city: list[str] | None = Query(None),
    work_mode: list[str] | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    active_only: bool = Query(False),
):
    """Salary statistics grouped by seniority level."""
    w, p = _where(
        source=source, city=city, work_mode=work_mode,
        date_from=date_from, date_to=date_to, active_only=active_only,
    )
    extra = f"{'AND' if w else 'WHERE'} salary_min > 0 AND salary_max > 0"
    rows = _query(
        f"""
        SELECT seniority,
               (salary_min + salary_max) / 2 AS mid
        FROM job_offers
        {w} {extra}
        """,
        p,
    )
    # Group by seniority
    grouped: dict[str, list[float]] = {}
    order = {"intern": 1, "junior": 2, "mid": 3, "senior": 4, "lead": 5, "manager": 6, "unknown": 7}
    for row in rows:
        s = row["seniority"]
        grouped.setdefault(s, []).append(float(row["mid"]))

    result = []
    for s in sorted(grouped.keys(), key=lambda x: order.get(x, 99)):
        vals = grouped[s]
        result.append({
            "seniority": s,
            "count": len(vals),
            "avg": round(statistics.mean(vals)),
            "median": round(statistics.median(vals)),
            "p10": round(_percentile(vals, 0.10) or 0),
            "p25": round(_percentile(vals, 0.25) or 0),
            "p75": round(_percentile(vals, 0.75) or 0),
            "p90": round(_percentile(vals, 0.90) or 0),
        })
    return result


@app.get("/api/salary/by-city")
def get_salary_by_city(
    source: list[str] | None = Query(None),
    work_mode: list[str] | None = Query(None),
    seniority: list[str] | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    active_only: bool = Query(False),
    limit: int = Query(15),
):
    """Salary statistics grouped by city (top N)."""
    w, p = _where(
        source=source, work_mode=work_mode, seniority=seniority,
        date_from=date_from, date_to=date_to, active_only=active_only,
    )
    extra = f"{'AND' if w else 'WHERE'} salary_min > 0 AND salary_max > 0 AND location_city IS NOT NULL"
    rows = _query(
        f"""
        SELECT location_city,
               AVG((salary_min + salary_max) / 2) AS avg_mid,
               AVG(salary_min) AS avg_min,
               AVG(salary_max) AS avg_max,
               COUNT(*) AS cnt
        FROM job_offers
        {w} {extra}
        GROUP BY location_city
        HAVING cnt >= 3
        ORDER BY cnt DESC
        LIMIT %s
        """,
        p + [limit],
    )
    return [
        {
            "city": r["location_city"],
            "avg_midpoint": round(float(r["avg_mid"])),
            "avg_min": round(float(r["avg_min"])),
            "avg_max": round(float(r["avg_max"])),
            "count": r["cnt"],
        }
        for r in rows
    ]


@app.get("/api/salary/by-workmode")
def get_salary_by_workmode(
    source: list[str] | None = Query(None),
    city: list[str] | None = Query(None),
    seniority: list[str] | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    active_only: bool = Query(False),
):
    """Salary statistics grouped by work mode."""
    w, p = _where(
        source=source, city=city, seniority=seniority,
        date_from=date_from, date_to=date_to, active_only=active_only,
    )
    extra = f"{'AND' if w else 'WHERE'} salary_min > 0 AND salary_max > 0"
    rows = _query(
        f"""
        SELECT work_mode,
               AVG((salary_min + salary_max) / 2) AS avg_mid,
               COUNT(*) AS cnt
        FROM job_offers
        {w} {extra}
        GROUP BY work_mode
        ORDER BY cnt DESC
        """,
        p,
    )
    return [
        {
            "work_mode": r["work_mode"],
            "avg_midpoint": round(float(r["avg_mid"])),
            "count": r["cnt"],
        }
        for r in rows
    ]


@app.get("/api/salary/bands")
def get_salary_bands(
    source: list[str] | None = Query(None),
    city: list[str] | None = Query(None),
    work_mode: list[str] | None = Query(None),
    seniority: list[str] | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    active_only: bool = Query(False),
):
    """Salary band distribution."""
    w, p = _where(
        source=source, city=city, work_mode=work_mode,
        seniority=seniority, date_from=date_from, date_to=date_to,
        active_only=active_only,
    )
    rows = _query(
        f"""
        SELECT salary_min, salary_max, salary_period
        FROM job_offers
        {w} {"AND" if w else "WHERE"} salary_min > 0 AND salary_max > 0
        """,
        p,
    )
    band_counts: dict[str, int] = {}
    for row in rows:
        m = _normalize_monthly(
            float(row["salary_min"]), float(row["salary_max"]),
            row.get("salary_period"),
        )
        band = _salary_band(m)
        band_counts[band] = band_counts.get(band, 0) + 1

    result = [
        {"band": band, "count": cnt, "order": _SALARY_BAND_ORDER.get(band, 99)}
        for band, cnt in band_counts.items()
    ]
    result.sort(key=lambda x: x["order"])
    return result


@app.get("/api/salary/heatmap")
def get_salary_heatmap(
    source: list[str] | None = Query(None),
    work_mode: list[str] | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    active_only: bool = Query(False),
):
    """City × Seniority salary heatmap matrix."""
    w, p = _where(
        source=source, work_mode=work_mode,
        date_from=date_from, date_to=date_to, active_only=active_only,
    )
    extra = f"{'AND' if w else 'WHERE'} salary_min > 0 AND salary_max > 0 AND location_city IS NOT NULL"
    rows = _query(
        f"""
        SELECT location_city, seniority,
               AVG((salary_min + salary_max) / 2) AS avg_mid,
               COUNT(*) AS cnt
        FROM job_offers
        {w} {extra}
        GROUP BY location_city, seniority
        HAVING cnt >= 2
        """,
        p,
    )
    # Get top 10 cities by total offers
    city_counts: dict[str, int] = {}
    for r in rows:
        city_counts[r["location_city"]] = city_counts.get(r["location_city"], 0) + r["cnt"]
    top_cities = sorted(city_counts, key=city_counts.get, reverse=True)[:10]

    seniority_order = ["intern", "junior", "mid", "senior", "lead", "manager"]
    matrix: dict[str, dict[str, int]] = {}
    for r in rows:
        if r["location_city"] in top_cities and r["seniority"] in seniority_order:
            matrix.setdefault(r["location_city"], {})[r["seniority"]] = round(float(r["avg_mid"]))

    return {
        "cities": top_cities,
        "seniorities": seniority_order,
        "matrix": matrix,
    }


@app.get("/api/trends")
def get_trends(
    source: list[str] | None = Query(None),
    city: list[str] | None = Query(None),
    work_mode: list[str] | None = Query(None),
    seniority: list[str] | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    active_only: bool = Query(False),
):
    """📈 Trendy folder — trend measures + daily time series."""
    w, p = _where(
        source=source, city=city, work_mode=work_mode,
        seniority=seniority, date_from=date_from, date_to=date_to,
        active_only=active_only,
    )

    # Today / This week counts
    today_str = date.today().isoformat()
    week_ago = (date.today() - timedelta(days=7)).isoformat()
    month_ago_start = (date.today().replace(day=1) - timedelta(days=1)).replace(day=1)
    month_ago_end = date.today().replace(day=1) - timedelta(days=1)
    current_month_start = date.today().replace(day=1)

    extra_and = "AND" if w else "WHERE"
    new_today = _query_one(
        f"SELECT COUNT(*) AS cnt FROM job_offers {w} {extra_and} DATE(scraped_at) = %s",
        p + [today_str],
    ).get("cnt", 0)

    new_week = _query_one(
        f"SELECT COUNT(*) AS cnt FROM job_offers {w} {extra_and} DATE(scraped_at) >= %s",
        p + [week_ago],
    ).get("cnt", 0)

    # Current month offers
    current_month = _query_one(
        f"SELECT COUNT(*) AS cnt FROM job_offers {w} {extra_and} scraped_at >= %s",
        p + [datetime.combine(current_month_start, datetime.min.time())],
    ).get("cnt", 0)

    # Previous month offers
    prev_month = _query_one(
        f"SELECT COUNT(*) AS cnt FROM job_offers {w} {extra_and} scraped_at >= %s AND scraped_at <= %s",
        p + [
            datetime.combine(month_ago_start, datetime.min.time()),
            datetime.combine(month_ago_end, datetime.max.time()),
        ],
    ).get("cnt", 0)

    mom_change = _safe_div(current_month - prev_month, prev_month) * 100 if prev_month else None
    trend_icon = "➡️"
    if mom_change is not None:
        if mom_change > 5:
            trend_icon = "📈"
        elif mom_change < -5:
            trend_icon = "📉"

    # Total & inactive for churn
    totals = _query_one(
        f"SELECT COUNT(*) AS total, SUM(is_active = 0) AS inactive FROM job_offers {w}", p,
    )
    total_all = totals.get("total") or 0
    inactive = totals.get("inactive") or 0
    churn_rate = _safe_div(inactive, total_all) * 100

    # Daily time series (last 90 days)
    ninety_days_ago = date.today() - timedelta(days=90)
    daily = _query(
        f"""
        SELECT DATE(scraped_at) AS day, COUNT(*) AS cnt
        FROM job_offers
        {w} {extra_and} scraped_at >= %s
        GROUP BY DATE(scraped_at)
        ORDER BY day
        """,
        p + [datetime.combine(ninety_days_ago, datetime.min.time())],
    )
    daily_series = [
        {"date": str(r["day"]), "count": r["cnt"]} for r in daily
    ]

    # Offer velocity
    if daily_series and len(daily_series) >= 2:
        d0 = datetime.fromisoformat(daily_series[0]["date"])
        d1 = datetime.fromisoformat(daily_series[-1]["date"])
        period_days = max((d1 - d0).days, 1)
        velocity = round(total_all / period_days, 1)
    else:
        velocity = 0

    # YTD
    ytd_start = date(date.today().year, 1, 1)
    ytd = _query_one(
        f"SELECT COUNT(*) AS cnt FROM job_offers {w} {extra_and} scraped_at >= %s",
        p + [datetime.combine(ytd_start, datetime.min.time())],
    ).get("cnt", 0)

    # Day-of-week seasonality
    seasonality = _query(
        f"""
        SELECT DAYOFWEEK(scraped_at) AS dow, COUNT(*) AS cnt
        FROM job_offers
        {w} {extra_and} scraped_at >= %s
        GROUP BY DAYOFWEEK(scraped_at)
        ORDER BY dow
        """,
        p + [datetime.combine(ninety_days_ago, datetime.min.time())],
    )
    dow_names = ["", "Nie", "Pon", "Wt", "Śr", "Czw", "Pt", "Sob"]
    seasonality_data = [
        {"day": dow_names[r["dow"]] if r["dow"] < len(dow_names) else str(r["dow"]), "count": r["cnt"]}
        for r in seasonality
    ]

    return {
        "new_today": new_today,
        "new_this_week": new_week,
        "offers_mom_change": round(mom_change, 1) if mom_change is not None else None,
        "offers_mom_trend_icon": trend_icon,
        "offer_velocity": velocity,
        "offer_churn_rate": round(churn_rate, 1),
        "offers_ytd": ytd,
        "daily_series": daily_series,
        "seasonality": seasonality_data,
    }


@app.get("/api/sources")
def get_sources(
    city: list[str] | None = Query(None),
    work_mode: list[str] | None = Query(None),
    seniority: list[str] | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    active_only: bool = Query(False),
):
    """🌐 Źródła folder — source analysis."""
    w, p = _where(
        city=city, work_mode=work_mode, seniority=seniority,
        date_from=date_from, date_to=date_to, active_only=active_only,
    )
    rows = _query(
        f"""
        SELECT source,
               COUNT(*) AS total,
               SUM(salary_min IS NOT NULL AND salary_min > 0) AS with_salary,
               COUNT(DISTINCT company_name) AS companies,
               AVG(
                   (CASE WHEN company_name IS NOT NULL THEN 1 ELSE 0 END +
                    CASE WHEN location_city IS NOT NULL THEN 1 ELSE 0 END +
                    CASE WHEN work_mode != 'unknown' THEN 1 ELSE 0 END +
                    CASE WHEN seniority != 'unknown' THEN 1 ELSE 0 END +
                    CASE WHEN employment_type IS NOT NULL THEN 1 ELSE 0 END +
                    CASE WHEN salary_min IS NOT NULL THEN 1 ELSE 0 END +
                    CASE WHEN category IS NOT NULL THEN 1 ELSE 0 END) / 7.0
               ) AS avg_quality
        FROM job_offers
        {w}
        GROUP BY source
        ORDER BY total DESC
        """,
        p,
    )
    grand_total = sum(r["total"] for r in rows) or 1
    source_names = {
        "pracapl": "Praca.pl", "justjoinit": "JustJoin.it",
        "pracuj": "Pracuj.pl", "rocketjobs": "RocketJobs.pl", "jooble": "Jooble",
    }
    return [
        {
            "source": r["source"],
            "source_name": source_names.get(r["source"], r["source"]),
            "total": r["total"],
            "with_salary": r["with_salary"] or 0,
            "salary_transparency_pct": round(_safe_div(r["with_salary"] or 0, r["total"]) * 100, 1),
            "source_share_pct": round(r["total"] / grand_total * 100, 1),
            "companies": r["companies"],
            "avg_data_quality": round(float(r["avg_quality"] or 0) * 100, 1),
        }
        for r in rows
    ]


@app.get("/api/location")
def get_location(
    source: list[str] | None = Query(None),
    city: list[str] | None = Query(None),
    work_mode: list[str] | None = Query(None),
    seniority: list[str] | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    active_only: bool = Query(False),
):
    """🗺️ Lokalizacja folder — location measures."""
    w, p = _where(
        source=source, city=city, work_mode=work_mode,
        seniority=seniority, date_from=date_from, date_to=date_to,
        active_only=active_only,
    )
    r = _query_one(
        f"""
        SELECT
            COUNT(*) AS total,
            SUM(work_mode = 'remote') AS remote_cnt
        FROM job_offers {w}
        """,
        p,
    )
    total = r.get("total") or 0
    remote_cnt = r.get("remote_cnt") or 0
    remote_share = _safe_div(remote_cnt, total) * 100

    # Remote salary premium
    r2 = _query_one(
        f"""
        SELECT
            AVG(CASE WHEN work_mode = 'remote' AND salary_min > 0
                THEN (salary_min+salary_max)/2 END) AS remote_avg,
            AVG(CASE WHEN work_mode = 'onsite' AND salary_min > 0
                THEN (salary_min+salary_max)/2 END) AS onsite_avg
        FROM job_offers {w}
        """,
        p,
    )
    remote_avg = r2.get("remote_avg")
    onsite_avg = r2.get("onsite_avg")
    premium = None
    if remote_avg and onsite_avg and onsite_avg > 0:
        premium = round((float(remote_avg) - float(onsite_avg)) / float(onsite_avg) * 100, 1)

    # Top city
    top = _query_one(
        f"""
        SELECT location_city, COUNT(*) AS cnt
        FROM job_offers {w} {"AND" if w else "WHERE"} location_city IS NOT NULL
        GROUP BY location_city ORDER BY cnt DESC LIMIT 1
        """,
        p,
    )

    # Warsaw share
    w_cnt = _query_one(
        f"SELECT COUNT(*) AS cnt FROM job_offers {w} {'AND' if w else 'WHERE'} location_city = 'Warszawa'",
        p,
    ).get("cnt", 0)

    # HHI
    city_shares = _query(
        f"""
        SELECT location_city, COUNT(*) AS cnt
        FROM job_offers {w} {"AND" if w else "WHERE"} location_city IS NOT NULL
        GROUP BY location_city
        """,
        p,
    )
    hhi = 0.0
    city_total = sum(c["cnt"] for c in city_shares)
    if city_total > 0:
        for c in city_shares:
            share = c["cnt"] / city_total
            hhi += share * share

    return {
        "remote_share_pct": round(remote_share, 1),
        "remote_salary_premium_pct": premium,
        "top_city": top.get("location_city", "—") if top else "—",
        "top_city_count": top.get("cnt", 0) if top else 0,
        "warsaw_share_pct": round(_safe_div(w_cnt, total) * 100, 1),
        "city_concentration_hhi": round(hhi, 4),
    }


@app.get("/api/location/cities")
def get_location_cities(
    source: list[str] | None = Query(None),
    work_mode: list[str] | None = Query(None),
    seniority: list[str] | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    active_only: bool = Query(False),
    limit: int = Query(20),
):
    """City detail table."""
    w, p = _where(
        source=source, work_mode=work_mode, seniority=seniority,
        date_from=date_from, date_to=date_to, active_only=active_only,
    )
    extra = f"{'AND' if w else 'WHERE'} location_city IS NOT NULL"
    rows = _query(
        f"""
        SELECT
            location_city,
            location_region,
            COUNT(*) AS total,
            SUM(salary_min > 0) AS with_salary,
            AVG(CASE WHEN salary_min > 0 THEN (salary_min+salary_max)/2 END) AS avg_mid,
            SUM(work_mode = 'remote') AS remote_cnt
        FROM job_offers
        {w} {extra}
        GROUP BY location_city, location_region
        ORDER BY total DESC
        LIMIT %s
        """,
        p + [limit],
    )
    return [
        {
            "city": r["location_city"],
            "region": r["location_region"],
            "total": r["total"],
            "with_salary": r["with_salary"] or 0,
            "salary_transparency_pct": round(_safe_div(r["with_salary"] or 0, r["total"]) * 100, 1),
            "avg_salary_midpoint": round(float(r["avg_mid"])) if r["avg_mid"] else None,
            "remote_share_pct": round(_safe_div(r["remote_cnt"] or 0, r["total"]) * 100, 1),
        }
        for r in rows
    ]


@app.get("/api/location/workmode-by-city")
def get_workmode_by_city(
    source: list[str] | None = Query(None),
    seniority: list[str] | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    active_only: bool = Query(False),
    limit: int = Query(10),
):
    """100% stacked: work mode distribution per city (top N)."""
    w, p = _where(
        source=source, seniority=seniority,
        date_from=date_from, date_to=date_to, active_only=active_only,
    )
    extra = f"{'AND' if w else 'WHERE'} location_city IS NOT NULL"
    # Top N cities first
    top_cities_rows = _query(
        f"SELECT location_city, COUNT(*) AS cnt FROM job_offers {w} {extra} GROUP BY location_city ORDER BY cnt DESC LIMIT %s",
        p + [limit],
    )
    if not top_cities_rows:
        return {"cities": [], "modes": [], "data": {}}
    top_cities = [r["location_city"] for r in top_cities_rows]
    placeholders = ",".join(["%s"] * len(top_cities))
    rows = _query(
        f"""
        SELECT location_city, work_mode, COUNT(*) AS cnt
        FROM job_offers
        {w} {extra} AND location_city IN ({placeholders})
        GROUP BY location_city, work_mode
        """,
        p + top_cities,
    )
    modes = sorted({r["work_mode"] for r in rows})
    data: dict[str, dict[str, int]] = {c: {} for c in top_cities}
    for r in rows:
        data[r["location_city"]][r["work_mode"]] = r["cnt"]
    return {"cities": top_cities, "modes": modes, "data": data}


@app.get("/api/location/by-region")
def get_by_region(
    source: list[str] | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    active_only: bool = Query(False),
):
    """Offers per region (województwo)."""
    w, p = _where(
        source=source, date_from=date_from, date_to=date_to,
        active_only=active_only,
    )
    extra = f"{'AND' if w else 'WHERE'} location_region IS NOT NULL AND location_region != ''"
    rows = _query(
        f"""
        SELECT location_region, COUNT(*) AS cnt
        FROM job_offers {w} {extra}
        GROUP BY location_region
        ORDER BY cnt DESC
        """,
        p,
    )
    return [{"region": r["location_region"], "count": r["cnt"]} for r in rows]


@app.get("/api/employers")
def get_employers(
    source: list[str] | None = Query(None),
    city: list[str] | None = Query(None),
    work_mode: list[str] | None = Query(None),
    seniority: list[str] | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    active_only: bool = Query(False),
    limit: int = Query(20),
):
    """🏢 Firmy folder — employer analysis."""
    w, p = _where(
        source=source, city=city, work_mode=work_mode,
        seniority=seniority, date_from=date_from, date_to=date_to,
        active_only=active_only,
    )
    extra = f"{'AND' if w else 'WHERE'} company_name IS NOT NULL AND company_name != ''"

    # Summary KPIs
    summary = _query_one(
        f"""
        SELECT
            COUNT(DISTINCT company_name) AS unique_companies,
            COUNT(*) AS total
        FROM job_offers {w}
        """,
        p,
    )
    unique = summary.get("unique_companies") or 0
    total = summary.get("total") or 1
    avg_per = round(_safe_div(total, unique), 1) if unique else 0

    # Large employers (5+ offers)
    large = _query_one(
        f"""
        SELECT COUNT(*) AS cnt FROM (
            SELECT company_name FROM job_offers {w} {extra}
            GROUP BY company_name HAVING COUNT(*) >= 5
        ) t
        """,
        p,
    ).get("cnt", 0)

    # Top 10 share
    top10_rows = _query(
        f"""
        SELECT company_name, COUNT(*) AS cnt
        FROM job_offers {w} {extra}
        GROUP BY company_name ORDER BY cnt DESC LIMIT 10
        """,
        p,
    )
    top10_total = sum(r["cnt"] for r in top10_rows)
    # All company total (with non-null names)
    all_total = _query_one(
        f"SELECT COUNT(*) AS cnt FROM job_offers {w} {extra}", p,
    ).get("cnt", 1)
    top10_share = round(top10_total / all_total * 100, 1) if all_total else 0

    # Top N employers table
    # Market avg salary for competitiveness index
    market_avg = _query_one(
        f"SELECT AVG((salary_min+salary_max)/2) AS avg_mid FROM job_offers {w} {'AND' if w else 'WHERE'} salary_min > 0",
        p,
    ).get("avg_mid")
    market_avg = float(market_avg) if market_avg else None

    employers = _query(
        f"""
        SELECT company_name,
               COUNT(*) AS offers,
               AVG(CASE WHEN salary_min > 0 THEN (salary_min+salary_max)/2 END) AS avg_salary,
               GROUP_CONCAT(DISTINCT location_city ORDER BY location_city SEPARATOR ', ') AS cities,
               SUM(work_mode = 'remote') AS remote_cnt
        FROM job_offers {w} {extra}
        GROUP BY company_name
        ORDER BY offers DESC
        LIMIT %s
        """,
        p + [limit],
    )

    employer_list = []
    for e in employers:
        avg_sal = float(e["avg_salary"]) if e["avg_salary"] else None
        comp_idx = round(avg_sal / market_avg * 100, 1) if (avg_sal and market_avg) else None
        employer_list.append({
            "company": e["company_name"],
            "offers": e["offers"],
            "avg_salary": round(avg_sal) if avg_sal else None,
            "competitiveness_index": comp_idx,
            "cities": e["cities"],
            "has_remote": (e["remote_cnt"] or 0) > 0,
        })

    return {
        "unique_companies": unique,
        "avg_offers_per_company": avg_per,
        "large_employers_count": large,
        "top10_share_pct": top10_share,
        "employers": employer_list,
    }


@app.get("/api/seniority")
def get_seniority(
    source: list[str] | None = Query(None),
    city: list[str] | None = Query(None),
    work_mode: list[str] | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    active_only: bool = Query(False),
):
    """🎯 Seniority folder — seniority analysis measures."""
    w, p = _where(
        source=source, city=city, work_mode=work_mode,
        date_from=date_from, date_to=date_to, active_only=active_only,
    )
    # Salary by seniority
    r = _query_one(
        f"""
        SELECT
            AVG(CASE WHEN seniority='junior' AND salary_min>0
                THEN (salary_min+salary_max)/2 END) AS junior_avg,
            AVG(CASE WHEN seniority='senior' AND salary_min>0
                THEN (salary_min+salary_max)/2 END) AS senior_avg
        FROM job_offers {w}
        """,
        p,
    )
    junior = float(r["junior_avg"]) if r.get("junior_avg") else None
    senior = float(r["senior_avg"]) if r.get("senior_avg") else None
    gap = round(senior - junior) if (junior and senior) else None
    multiplier = round(senior / junior, 1) if (junior and senior and junior > 0) else None

    # Shares
    rows = _query(
        f"""
        SELECT seniority, COUNT(*) AS cnt
        FROM job_offers {w}
        GROUP BY seniority
        """,
        p,
    )
    total = sum(r["cnt"] for r in rows) or 1
    shares = [
        {"seniority": r["seniority"], "count": r["cnt"],
         "share_pct": round(r["cnt"] / total * 100, 1)}
        for r in rows
    ]
    order = {"intern": 1, "junior": 2, "mid": 3, "senior": 4, "lead": 5, "manager": 6, "unknown": 7}
    shares.sort(key=lambda x: order.get(x["seniority"], 99))

    # Demand index
    junior_cnt = next((s["count"] for s in shares if s["seniority"] == "junior"), 0)
    senior_cnt = next((s["count"] for s in shares if s["seniority"] == "senior"), 0)
    demand_idx = round(junior_cnt / senior_cnt, 2) if senior_cnt else None

    return {
        "junior_senior_salary_gap": gap,
        "senior_junior_multiplier": multiplier,
        "market_demand_index": demand_idx,
        "shares": shares,
    }


@app.get("/api/quality")
def get_quality(
    source: list[str] | None = Query(None),
    city: list[str] | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    active_only: bool = Query(False),
):
    """🔧 Data Quality folder — completeness + pipeline monitoring."""
    w, p = _where(
        source=source, city=city,
        date_from=date_from, date_to=date_to, active_only=active_only,
    )
    r = _query_one(
        f"""
        SELECT
            COUNT(*) AS total,
            SUM(company_name IS NOT NULL AND company_name != '') AS has_company,
            SUM(location_city IS NOT NULL AND location_city != '') AS has_city,
            SUM(salary_min IS NOT NULL AND salary_min > 0) AS has_salary,
            SUM(seniority != 'unknown') AS has_seniority,
            SUM(work_mode != 'unknown') AS has_workmode,
            AVG(
                (CASE WHEN company_name IS NOT NULL THEN 1 ELSE 0 END +
                 CASE WHEN location_city IS NOT NULL THEN 1 ELSE 0 END +
                 CASE WHEN work_mode != 'unknown' THEN 1 ELSE 0 END +
                 CASE WHEN seniority != 'unknown' THEN 1 ELSE 0 END +
                 CASE WHEN employment_type IS NOT NULL THEN 1 ELSE 0 END +
                 CASE WHEN salary_min IS NOT NULL THEN 1 ELSE 0 END +
                 CASE WHEN category IS NOT NULL THEN 1 ELSE 0 END) / 7.0
            ) AS avg_completeness,
            MAX(scraped_at) AS last_scrape
        FROM job_offers {w}
        """,
        p,
    )
    total = r.get("total") or 1
    last_scrape = r.get("last_scrape")
    freshness_hours = None
    freshness_status = "Brak danych"
    if last_scrape:
        if isinstance(last_scrape, str):
            last_scrape = datetime.fromisoformat(last_scrape)
        freshness_hours = int((datetime.now() - last_scrape).total_seconds() / 3600)
        if freshness_hours <= 6:
            freshness_status = "Świeże"
        elif freshness_hours <= 24:
            freshness_status = "Do odświeżenia"
        else:
            freshness_status = "Nieaktualne"

    # Scrape log stats
    sl = _query_one(
        """
        SELECT
            COUNT(*) AS total_runs,
            SUM(status = 'success') AS success_runs,
            AVG(TIMESTAMPDIFF(SECOND, started_at, finished_at)) AS avg_duration,
            SUM(errors) AS total_errors
        FROM scrape_log
        """
    )
    success_rate = round(_safe_div(sl.get("success_runs") or 0, sl.get("total_runs") or 1) * 100, 1)

    # Completeness per source
    per_source = _query(
        f"""
        SELECT source,
            COUNT(*) AS total,
            AVG(
                (CASE WHEN company_name IS NOT NULL THEN 1 ELSE 0 END +
                 CASE WHEN location_city IS NOT NULL THEN 1 ELSE 0 END +
                 CASE WHEN work_mode != 'unknown' THEN 1 ELSE 0 END +
                 CASE WHEN seniority != 'unknown' THEN 1 ELSE 0 END +
                 CASE WHEN employment_type IS NOT NULL THEN 1 ELSE 0 END +
                 CASE WHEN salary_min IS NOT NULL THEN 1 ELSE 0 END +
                 CASE WHEN category IS NOT NULL THEN 1 ELSE 0 END) / 7.0
            ) AS avg_quality
        FROM job_offers {w}
        GROUP BY source
        ORDER BY total DESC
        """,
        p,
    )

    return {
        "completeness_company_pct": round(_safe_div(r.get("has_company") or 0, total) * 100, 1),
        "completeness_city_pct": round(_safe_div(r.get("has_city") or 0, total) * 100, 1),
        "completeness_salary_pct": round(_safe_div(r.get("has_salary") or 0, total) * 100, 1),
        "completeness_seniority_pct": round(_safe_div(r.get("has_seniority") or 0, total) * 100, 1),
        "completeness_workmode_pct": round(_safe_div(r.get("has_workmode") or 0, total) * 100, 1),
        "avg_data_completeness_pct": round(float(r.get("avg_completeness") or 0) * 100, 1),
        "last_scrape_time": str(last_scrape) if last_scrape else None,
        "data_freshness_hours": freshness_hours,
        "data_freshness_status": freshness_status,
        "scrape_success_rate_pct": success_rate,
        "avg_scrape_duration_sec": round(float(sl.get("avg_duration") or 0), 1),
        "total_scrape_errors": sl.get("total_errors") or 0,
        "quality_per_source": [
            {
                "source": ps["source"],
                "avg_quality_pct": round(float(ps["avg_quality"] or 0) * 100, 1),
            }
            for ps in per_source
        ],
    }


@app.get("/api/quality/scrape-log")
def get_scrape_log(limit: int = Query(20)):
    """Last N scrape log entries."""
    rows = _query(
        """
        SELECT run_id, source, started_at, finished_at,
               offers_scraped, offers_new, offers_updated, errors, status,
               TIMESTAMPDIFF(SECOND, started_at, finished_at) AS duration_sec
        FROM scrape_log
        ORDER BY started_at DESC
        LIMIT %s
        """,
        [limit],
    )
    return [
        {
            "run_id": r["run_id"],
            "source": r["source"],
            "started_at": str(r["started_at"]),
            "finished_at": str(r["finished_at"]) if r["finished_at"] else None,
            "offers_scraped": r["offers_scraped"],
            "offers_new": r["offers_new"],
            "offers_updated": r["offers_updated"],
            "errors": r["errors"],
            "status": r["status"],
            "duration_sec": r["duration_sec"],
        }
        for r in rows
    ]


@app.get("/api/charts/source-distribution")
def get_source_distribution(
    city: list[str] | None = Query(None),
    work_mode: list[str] | None = Query(None),
    seniority: list[str] | None = Query(None),
    active_only: bool = Query(False),
):
    """Donut chart: offers by source."""
    w, p = _where(city=city, work_mode=work_mode, seniority=seniority, active_only=active_only)
    rows = _query(f"SELECT source, COUNT(*) AS cnt FROM job_offers {w} GROUP BY source ORDER BY cnt DESC", p)
    names = {"pracapl": "Praca.pl", "justjoinit": "JustJoin.it", "pracuj": "Pracuj.pl",
             "rocketjobs": "RocketJobs.pl", "jooble": "Jooble"}
    return [{"label": names.get(r["source"], r["source"]), "value": r["cnt"]} for r in rows]


@app.get("/api/charts/workmode-distribution")
def get_workmode_distribution(
    source: list[str] | None = Query(None),
    city: list[str] | None = Query(None),
    seniority: list[str] | None = Query(None),
    active_only: bool = Query(False),
):
    """Donut chart: offers by work mode."""
    w, p = _where(source=source, city=city, seniority=seniority, active_only=active_only)
    rows = _query(f"SELECT work_mode, COUNT(*) AS cnt FROM job_offers {w} GROUP BY work_mode ORDER BY cnt DESC", p)
    names = {"remote": "Zdalna", "hybrid": "Hybrydowa", "onsite": "Stacjonarna", "unknown": "Nieokreślony"}
    return [{"label": names.get(r["work_mode"], r["work_mode"]), "value": r["cnt"]} for r in rows]


@app.get("/api/charts/top-cities")
def get_top_cities(
    source: list[str] | None = Query(None),
    work_mode: list[str] | None = Query(None),
    seniority: list[str] | None = Query(None),
    active_only: bool = Query(False),
    limit: int = Query(15),
):
    """Bar chart: top N cities by offer count."""
    w, p = _where(source=source, work_mode=work_mode, seniority=seniority, active_only=active_only)
    extra = f"{'AND' if w else 'WHERE'} location_city IS NOT NULL"
    rows = _query(
        f"SELECT location_city AS city, COUNT(*) AS cnt FROM job_offers {w} {extra} GROUP BY location_city ORDER BY cnt DESC LIMIT %s",
        p + [limit],
    )
    return [{"label": r["city"], "value": r["cnt"]} for r in rows]


@app.get("/api/charts/seniority-distribution")
def get_seniority_distribution(
    source: list[str] | None = Query(None),
    city: list[str] | None = Query(None),
    work_mode: list[str] | None = Query(None),
    active_only: bool = Query(False),
):
    """Bar chart: offers by seniority."""
    w, p = _where(source=source, city=city, work_mode=work_mode, active_only=active_only)
    rows = _query(
        f"SELECT seniority, COUNT(*) AS cnt FROM job_offers {w} GROUP BY seniority ORDER BY cnt DESC",
        p,
    )
    names = {"intern": "Stażysta", "junior": "Junior", "mid": "Mid", "senior": "Senior",
             "lead": "Lead", "manager": "Manager", "unknown": "Nieokreślony"}
    order = {"intern": 1, "junior": 2, "mid": 3, "senior": 4, "lead": 5, "manager": 6, "unknown": 7}
    result = [{"label": names.get(r["seniority"], r["seniority"]), "value": r["cnt"],
               "order": order.get(r["seniority"], 99)} for r in rows]
    result.sort(key=lambda x: x["order"])
    return result


# ---------------------------------------------------------------------------
# Static files — serve the HTML frontend
# ---------------------------------------------------------------------------

app.mount("/static", StaticFiles(directory=str(HTML_DIR)), name="static")


@app.get("/")
def serve_index():
    return FileResponse(str(HTML_DIR / "index.html"))
