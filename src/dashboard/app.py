import sys
from pathlib import Path

import streamlit as st

# Ensure project root on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

st.set_page_config(
    page_title="JobDB — Polski rynek pracy",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

import mysql.connector
import plotly.express as px
import polars as pl

from config.settings import MYSQL_CONFIG


def query(sql: str) -> pl.DataFrame:
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        if not rows:
            cursor.close()
            conn.close()
            return pl.DataFrame()
        columns = [desc[0] for desc in cursor.description]
        cursor.close()
        conn.close()
        return pl.DataFrame(rows, schema=columns, orient="row")
    except mysql.connector.Error as e:
        st.error(f"Błąd bazy danych: {e}")
        return pl.DataFrame()


# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🔍 JobDB")
    st.caption("Polski rynek pracy — dane z portali")

    # Filters
    _src_df = query("SELECT DISTINCT source FROM job_offers ORDER BY 1")
    sources = _src_df["source"].to_list() if _src_df.height > 0 else []
    selected_sources = st.multiselect("Źródło", sources, default=sources)

    _city_df = query("SELECT DISTINCT location_city FROM job_offers WHERE location_city IS NOT NULL ORDER BY 1")
    cities = _city_df["location_city"].to_list() if _city_df.height > 0 else []
    selected_cities = st.multiselect("Miasto", cities, default=[])

    _mode_df = query("SELECT DISTINCT work_mode FROM job_offers ORDER BY 1")
    work_modes = _mode_df["work_mode"].to_list() if _mode_df.height > 0 else []
    selected_modes = st.multiselect("Tryb pracy", work_modes, default=[])

    _sen_df = query("SELECT DISTINCT seniority FROM job_offers WHERE seniority != 'unknown' ORDER BY 1")
    seniority_opts = _sen_df["seniority"].to_list() if _sen_df.height > 0 else []
    selected_seniority = st.multiselect("Poziom", seniority_opts, default=[])

    st.divider()
    st.caption("Ostatnia aktualizacja danych")
    last_scrape = query("SELECT max(scraped_at) as ts FROM job_offers")
    if last_scrape.height > 0 and last_scrape["ts"][0] is not None:
        st.write(f"🕒 {last_scrape['ts'][0]}")


# ── Build WHERE clause ───────────────────────────────────────────────────────
def build_where() -> str:
    clauses = ["is_active = true"]
    if selected_sources:
        src_list = ", ".join(f"'{s}'" for s in selected_sources)
        clauses.append(f"source IN ({src_list})")
    if selected_cities:
        city_list = ", ".join(f"'{c}'" for c in selected_cities)
        clauses.append(f"location_city IN ({city_list})")
    if selected_modes:
        mode_list = ", ".join(f"'{m}'" for m in selected_modes)
        clauses.append(f"work_mode IN ({mode_list})")
    if selected_seniority:
        sen_list = ", ".join(f"'{s}'" for s in selected_seniority)
        clauses.append(f"seniority IN ({sen_list})")
    return " AND ".join(clauses)


WHERE = build_where()

# ── Page: Przegląd ───────────────────────────────────────────────────────────
st.title("📊 Przegląd rynku pracy")

# KPI row
kpi = query(f"""
    SELECT
        count(*) as total,
        SUM(CASE WHEN salary_min IS NOT NULL THEN 1 ELSE 0 END) as with_salary,
        count(DISTINCT CASE WHEN company_name IS NOT NULL THEN company_name END) as companies,
        count(DISTINCT CASE WHEN location_city IS NOT NULL THEN location_city END) as cities
    FROM job_offers
    WHERE {WHERE}
""")

c1, c2, c3, c4 = st.columns(4)
if kpi.height > 0:
    c1.metric("Aktywne oferty", f"{kpi['total'][0]:,}")
    c2.metric("Z wynagrodzeniem", f"{kpi['with_salary'][0]:,}")
    c3.metric("Firmy", f"{kpi['companies'][0]:,}")
    c4.metric("Miasta", f"{kpi['cities'][0]:,}")
else:
    c1.metric("Aktywne oferty", 0)
    c2.metric("Z wynagrodzeniem", 0)
    c3.metric("Firmy", 0)
    c4.metric("Miasta", 0)

st.divider()

# ── Charts row 1 ─────────────────────────────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("🏙️ Top miasta")
    cities_df = query(f"""
        SELECT location_city as miasto, count(*) as oferty
        FROM job_offers
        WHERE {WHERE} AND location_city IS NOT NULL
        GROUP BY 1 ORDER BY 2 DESC LIMIT 15
    """)
    if cities_df.height > 0:
        fig = px.bar(
            cities_df.to_pandas(),
            x="oferty",
            y="miasto",
            orientation="h",
            color="oferty",
            color_continuous_scale="Blues",
        )
        fig.update_layout(yaxis=dict(autorange="reversed"), height=450, showlegend=False, coloraxis_showscale=False)
        st.plotly_chart(fig, width="stretch", key="cities")
    else:
        st.info("Brak danych o miastach")

with col_right:
    st.subheader("💼 Tryb pracy")
    modes_df = query(f"""
        SELECT work_mode as tryb, count(*) as oferty
        FROM job_offers
        WHERE {WHERE}
        GROUP BY 1 ORDER BY 2 DESC
    """)
    if modes_df.height > 0:
        fig = px.pie(
            modes_df.to_pandas(),
            names="tryb",
            values="oferty",
            color_discrete_sequence=px.colors.qualitative.Set2,
            hole=0.4,
        )
        fig.update_layout(height=450)
        st.plotly_chart(fig, width="stretch", key="work_mode")

# ── Charts row 2 ─────────────────────────────────────────────────────────────
col2_left, col2_right = st.columns(2)

with col2_left:
    st.subheader("📈 Poziom stanowiska")
    sen_df = query(f"""
        SELECT seniority as poziom, count(*) as oferty
        FROM job_offers
        WHERE {WHERE} AND seniority != 'unknown'
        GROUP BY 1 ORDER BY 2 DESC
    """)
    if sen_df.height > 0:
        fig = px.bar(
            sen_df.to_pandas(),
            x="poziom",
            y="oferty",
            color="oferty",
            color_continuous_scale="Greens",
        )
        fig.update_layout(height=380, showlegend=False, coloraxis_showscale=False)
        st.plotly_chart(fig, width="stretch", key="seniority")

with col2_right:
    st.subheader("📝 Typ umowy")
    emp_df = query(f"""
        SELECT COALESCE(employment_type, 'Nieokreślony') as typ, count(*) as oferty
        FROM job_offers
        WHERE {WHERE}
        GROUP BY 1 ORDER BY 2 DESC
    """)
    if emp_df.height > 0:
        fig = px.pie(
            emp_df.to_pandas(),
            names="typ",
            values="oferty",
            color_discrete_sequence=px.colors.qualitative.Pastel,
            hole=0.4,
        )
        fig.update_layout(height=380)
        st.plotly_chart(fig, width="stretch", key="emp_type")

# ── Charts row 3: Źródła ─────────────────────────────────────────────────────
st.subheader("🌐 Oferty wg źródła")
src_df = query(f"""
    SELECT source as zrodlo, count(*) as oferty,
           SUM(CASE WHEN salary_min IS NOT NULL THEN 1 ELSE 0 END) as z_wynagrodzeniem,
           SUM(CASE WHEN company_name IS NOT NULL THEN 1 ELSE 0 END) as z_firma
    FROM job_offers
    WHERE {WHERE}
    GROUP BY 1 ORDER BY 2 DESC
""")
if src_df.height > 0:
    st.dataframe(
        src_df.to_pandas().rename(
            columns={
                "zrodlo": "Źródło",
                "oferty": "Oferty",
                "z_wynagrodzeniem": "Z wynagrodzeniem",
                "z_firma": "Z firmą",
            }
        ),
        width="stretch",
        hide_index=True,
    )

# ── Top firmy ────────────────────────────────────────────────────────────────
st.subheader("🏢 Top pracodawcy")
top_companies = query(f"""
    SELECT company_name as firma, count(*) as oferty,
           count(DISTINCT location_city) as miasta,
           (SELECT wm.work_mode FROM job_offers wm WHERE wm.company_name = job_offers.company_name GROUP BY wm.work_mode ORDER BY count(*) DESC LIMIT 1) as tryb,
           (SELECT wm2.company_logo_url FROM job_offers wm2 WHERE wm2.company_name = job_offers.company_name AND wm2.company_logo_url IS NOT NULL LIMIT 1) as logo
    FROM job_offers
    WHERE {WHERE} AND company_name IS NOT NULL AND company_name NOT LIKE 'Klient portalu%'
    GROUP BY 1 ORDER BY 2 DESC LIMIT 20
""")
if top_companies.height > 0:
    st.dataframe(
        top_companies.to_pandas().rename(
            columns={"firma": "Firma", "oferty": "Oferty", "miasta": "Miasta", "tryb": "Dominujący tryb", "logo": "Logo"}
        ),
        width="stretch",
        hide_index=True,
        column_config={
            "Logo": st.column_config.ImageColumn("Logo", width="small"),
        },
    )

# ── Tabela ofert ──────────────────────────────────────────────────────────────
st.divider()
st.subheader("📋 Lista ofert")

search = st.text_input("🔎 Szukaj w tytułach", "")
search_safe = search.replace("'", "''").replace("%", "\\%").replace("_", "\\_") if search else ""
search_clause = f"AND LOWER(title) LIKE LOWER('%{search_safe}%')" if search else ""

offers_df = query(f"""
    SELECT company_logo_url as logo, title as tytul, company_name as firma, location_city as miasto,
           work_mode as tryb, seniority as poziom, employment_type as umowa,
           CASE WHEN salary_min IS NOT NULL
                THEN CONCAT(salary_min, ' - ', salary_max, ' ', COALESCE(salary_currency, ''))
                ELSE '' END as wynagrodzenie,
           source as zrodlo, source_url as link
    FROM job_offers
    WHERE {WHERE} {search_clause}
    ORDER BY scraped_at DESC
    LIMIT 200
""")

if offers_df.height > 0:
    st.dataframe(
        offers_df.to_pandas(),
        width="stretch",
        hide_index=True,
        column_config={
            "logo": st.column_config.ImageColumn("Logo", width="small"),
            "link": st.column_config.LinkColumn("Link", display_text="Otwórz"),
            "tytul": st.column_config.TextColumn("Tytuł", width="large"),
            "firma": st.column_config.TextColumn("Firma", width="medium"),
        },
    )
    st.caption(f"Pokazano {offers_df.height} ofert (max 200)")
else:
    st.info("Brak ofert pasujących do filtrów")

# ── Scrape log ────────────────────────────────────────────────────────────────
with st.expander("🔧 Log scrapingu"):
    log_df = query("""
        SELECT run_id, source as zrodlo, started_at, finished_at,
               offers_scraped as pobrane, offers_new as nowe,
               offers_updated as zaktualizowane, errors as bledy, status
        FROM scrape_log
        ORDER BY started_at DESC
        LIMIT 20
    """)
    if log_df.height > 0:
        st.dataframe(log_df.to_pandas(), width="stretch", hide_index=True)
