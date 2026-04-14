"""Zakładka Postęp prac — paski postępu i dokumentacja projektu."""

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

st.set_page_config(
    page_title="JobDB — Postęp prac",
    page_icon="📋",
    layout="wide",
)

# ── Progress data ────────────────────────────────────────────────────────────
# Status: 1.0 = done, 0.5 = partial, 0.0 = not started
PRIORITIES = {
    "🔴 P1 — Rdzeń systemu": {
        "tasks": [
            ("Scraper praca.pl", 1.0),
            ("Scraper justjoin.it", 0.0),
            ("Scraper pracuj.pl", 0.0),
            ("Scraper rocketjobs.pl", 0.0),
            ("Scraper jooble.org", 0.0),
            ("Integracja deduplicatora w pipeline", 0.0),
            ("Śledzenie cyklu życia ofert (mark_inactive)", 0.0),
        ],
    },
    "🟡 P2 — Analityka i dane historyczne": {
        "tasks": [
            ("Populowanie daily_stats", 0.0),
            ("Populowanie job_snapshots", 0.0),
            ("Moduł analizy (src/analysis/)", 0.0),
            ("Dashboard — podstrony trendów", 0.0),
            ("Dashboard — zakładka postępu prac", 1.0),
        ],
    },
    "🟢 P3 — Infrastruktura": {
        "tasks": [
            ("Scheduler (automatyczne scrapowanie)", 0.0),
            ("System logowania (logging)", 0.0),
            ("Eksport danych (CSV/Parquet)", 0.0),
            ("Alerting / Monitoring", 0.0),
        ],
    },
    "⚪ P4 — Migracja DWH (PostgreSQL + Power BI)": {
        "tasks": [
            ("Schemat star schema PostgreSQL", 0.0),
            ("Abstrakcja bazy danych (MySQL ↔ PostgreSQL)", 0.0),
            ("Skrypt migracji danych", 0.0),
            ("Połączenie Power BI + raporty", 0.0),
        ],
    },
    "🔵 P5 — Ulepszenia": {
        "tasks": [
            ("Playwright (headless browser)", 0.0),
            ("Walidacja jakości danych", 0.0),
            ("Rozszerzenie modelu (benefits, requirements)", 0.0),
            ("Testy normalizer + deduplicator", 0.0),
            ("Testy integracyjne pipeline", 0.0),
            ("CI/CD (GitHub Actions)", 0.0),
        ],
    },
}

# Also define component-level status for the summary table
COMPONENTS = [
    ("Scraper praca.pl", "✅ Gotowy", "src/scrapers/pracapl.py"),
    ("Scraper justjoin.it", "❌ Brak", "src/scrapers/justjoinit.py"),
    ("Scraper pracuj.pl", "❌ Brak", "src/scrapers/pracuj.py"),
    ("Scraper rocketjobs.pl", "❌ Brak", "src/scrapers/rocketjobs.py"),
    ("Scraper jooble.org", "❌ Brak", "src/scrapers/jooble.py"),
    ("Normalizer", "✅ Gotowy", "src/pipeline/normalizer.py"),
    ("Deduplicator", "⚠️ Niezintegrowany", "src/pipeline/deduplicator.py"),
    ("Pipeline orchestrator", "✅ Gotowy", "src/pipeline/orchestrator.py"),
    ("Baza danych (DDL)", "✅ Gotowa", "src/db/migrations.py"),
    ("Upsert + Log", "✅ Gotowe", "src/db/queries.py"),
    ("mark_inactive", "⚠️ Niewywoływany", "src/db/queries.py"),
    ("daily_stats", "⚠️ Tabela pusta", "src/db/queries.py"),
    ("job_snapshots", "⚠️ Tabela pusta", "src/db/queries.py"),
    ("Dashboard (główny)", "✅ Gotowy", "src/dashboard/app.py"),
    ("Dashboard (podstrony)", "❌ W trakcie", "src/dashboard/pages/"),
    ("Moduł analizy", "❌ Brak", "src/analysis/"),
    ("Scheduler", "❌ Brak", "—"),
    ("System logowania", "❌ Brak", "—"),
    ("Eksport danych", "❌ Brak", "—"),
    ("Schemat PostgreSQL", "❌ Brak", "—"),
    ("Power BI", "❌ Brak", "—"),
    ("Testy salary parsing", "✅ 26 testów", "tests/test_scrapers/test_salary_parsing.py"),
    ("Testy normalizer", "❌ Brak", "—"),
    ("Testy integracyjne", "❌ Brak", "—"),
    ("CI/CD", "❌ Brak", "—"),
]


def calc_priority_progress(tasks: list[tuple[str, float]]) -> float:
    if not tasks:
        return 0.0
    return sum(s for _, s in tasks) / len(tasks)


def calc_overall_progress() -> float:
    all_tasks = []
    for p in PRIORITIES.values():
        all_tasks.extend(p["tasks"])
    if not all_tasks:
        return 0.0
    return sum(s for _, s in all_tasks) / len(all_tasks)


# ── Page ─────────────────────────────────────────────────────────────────────
st.title("📋 Postęp prac — jobDB")
st.caption("Status implementacji projektu i dokumentacja")

# ── Overall progress ─────────────────────────────────────────────────────────
overall = calc_overall_progress()
st.markdown("### Postęp ogólny")

col_bar, col_pct = st.columns([5, 1])
with col_bar:
    st.progress(overall)
with col_pct:
    st.metric("Ukończono", f"{overall:.0%}")

st.divider()

# ── Priority breakdown ───────────────────────────────────────────────────────
st.markdown("### Postęp wg priorytetów")

for pname, pdata in PRIORITIES.items():
    tasks = pdata["tasks"]
    progress = calc_priority_progress(tasks)
    done = sum(1 for _, s in tasks if s >= 1.0)
    partial = sum(1 for _, s in tasks if 0.0 < s < 1.0)
    total = len(tasks)

    with st.expander(f"{pname}  —  {progress:.0%}  ({done}/{total} gotowych)", expanded=(progress < 1.0)):
        col_b, col_p = st.columns([5, 1])
        with col_b:
            st.progress(progress)
        with col_p:
            st.write(f"**{progress:.0%}**")

        for tname, tstatus in tasks:
            if tstatus >= 1.0:
                st.markdown(f"- ✅ ~~{tname}~~")
            elif tstatus > 0.0:
                st.markdown(f"- ⚠️ {tname} *(częściowo)*")
            else:
                st.markdown(f"- ⬜ {tname}")

st.divider()

# ── Component status table ───────────────────────────────────────────────────
st.markdown("### Status komponentów")

import pandas as pd

comp_df = pd.DataFrame(COMPONENTS, columns=["Komponent", "Status", "Lokalizacja"])
st.dataframe(
    comp_df,
    width="stretch",
    hide_index=True,
    column_config={
        "Komponent": st.column_config.TextColumn("Komponent", width="medium"),
        "Status": st.column_config.TextColumn("Status", width="small"),
        "Lokalizacja": st.column_config.TextColumn("Plik/Katalog", width="medium"),
    },
)

st.divider()

# ── Roadmap ──────────────────────────────────────────────────────────────────
st.markdown("### 🗺️ Roadmapa")

st.markdown("""
```mermaid
gantt
    title Roadmapa jobDB
    dateFormat YYYY-MM
    axisFormat %b %Y

    section P1 Rdzeń
    Scraper praca.pl           :done, s1, 2025-01, 2025-03
    Scraper justjoin.it        :active, s2, 2026-04, 2026-06
    Scraper pracuj.pl          :s3, 2026-05, 2026-07
    Scraper rocketjobs.pl      :s4, 2026-06, 2026-08
    Scraper jooble.org         :s5, 2026-07, 2026-08
    Integracja deduplicatora   :s6, 2026-05, 2026-06
    mark_inactive w pipeline   :s7, 2026-05, 2026-05

    section P2 Analityka
    daily_stats + snapshots    :a1, 2026-06, 2026-07
    Moduł analizy              :a2, 2026-07, 2026-09
    Dashboard podstrony        :a3, 2026-07, 2026-09

    section P3 Infra
    Scheduler                  :i1, 2026-06, 2026-07
    System logowania           :i2, 2026-06, 2026-06
    Eksport danych             :i3, 2026-08, 2026-09

    section P4 Migracja DWH
    Star schema PostgreSQL     :d1, 2026-08, 2026-09
    Abstrakcja DB              :d2, 2026-09, 2026-10
    Migracja danych            :d3, 2026-10, 2026-11
    Power BI raporty           :d4, 2026-11, 2026-12

    section P5 Ulepszenia
    Playwright                 :u1, 2026-06, 2026-07
    Testy                      :u2, 2026-07, 2026-09
    CI/CD                      :u3, 2026-09, 2026-10
```
""")

# Note: Mermaid rendering depends on streamlit version — show as code block
# For interactive Gantt, we can use plotly:
st.markdown("#### Gantt interaktywny")


import plotly.figure_factory as ff

gantt_data = [
    dict(Task="Scraper praca.pl", Start="2025-01-01", Finish="2025-03-01", Resource="P1 Rdzeń"),
    dict(Task="Scraper justjoin.it", Start="2026-04-01", Finish="2026-06-30", Resource="P1 Rdzeń"),
    dict(Task="Scraper pracuj.pl", Start="2026-05-01", Finish="2026-07-31", Resource="P1 Rdzeń"),
    dict(Task="Scraper rocketjobs.pl", Start="2026-06-01", Finish="2026-08-31", Resource="P1 Rdzeń"),
    dict(Task="Scraper jooble.org", Start="2026-07-01", Finish="2026-08-31", Resource="P1 Rdzeń"),
    dict(Task="Integracja dedup", Start="2026-05-01", Finish="2026-06-30", Resource="P1 Rdzeń"),
    dict(Task="daily_stats + snapshots", Start="2026-06-01", Finish="2026-07-31", Resource="P2 Analityka"),
    dict(Task="Moduł analizy", Start="2026-07-01", Finish="2026-09-30", Resource="P2 Analityka"),
    dict(Task="Dashboard podstrony", Start="2026-07-01", Finish="2026-09-30", Resource="P2 Analityka"),
    dict(Task="Scheduler", Start="2026-06-01", Finish="2026-07-31", Resource="P3 Infra"),
    dict(Task="System logowania", Start="2026-06-01", Finish="2026-06-30", Resource="P3 Infra"),
    dict(Task="Eksport danych", Start="2026-08-01", Finish="2026-09-30", Resource="P3 Infra"),
    dict(Task="Star schema PostgreSQL", Start="2026-08-01", Finish="2026-09-30", Resource="P4 DWH"),
    dict(Task="Abstrakcja DB", Start="2026-09-01", Finish="2026-10-31", Resource="P4 DWH"),
    dict(Task="Migracja danych", Start="2026-10-01", Finish="2026-11-30", Resource="P4 DWH"),
    dict(Task="Power BI raporty", Start="2026-11-01", Finish="2026-12-31", Resource="P4 DWH"),
    dict(Task="Playwright", Start="2026-06-01", Finish="2026-07-31", Resource="P5 Ulepszenia"),
    dict(Task="Testy", Start="2026-07-01", Finish="2026-09-30", Resource="P5 Ulepszenia"),
    dict(Task="CI/CD", Start="2026-09-01", Finish="2026-10-31", Resource="P5 Ulepszenia"),
]

colors = {
    "P1 Rdzeń": "#e74c3c",
    "P2 Analityka": "#f39c12",
    "P3 Infra": "#27ae60",
    "P4 DWH": "#95a5a6",
    "P5 Ulepszenia": "#3498db",
}

fig = ff.create_gantt(
    gantt_data,
    colors=colors,
    index_col="Resource",
    show_colorbar=True,
    group_tasks=True,
    showgrid_x=True,
    showgrid_y=True,
    title="",
)
fig.update_layout(height=600, xaxis_title="", yaxis_title="")
st.plotly_chart(fig, width="stretch")

st.divider()

# ── Documentation ────────────────────────────────────────────────────────────
st.markdown("### 📚 Dokumentacja projektu")

DOCS_DIR = PROJECT_ROOT / "docs"

tab_schema, tab_design, tab_todo = st.tabs(
    [
        "🗄️ Schemat bazy danych",
        "🏗️ Projekt systemu",
        "📝 TODO",
    ]
)

with tab_schema:
    schema_path = DOCS_DIR / "DATABASE_SCHEMA.md"
    if schema_path.exists():
        st.markdown(schema_path.read_text(encoding="utf-8"))
    else:
        st.warning("Plik docs/DATABASE_SCHEMA.md nie znaleziony")

with tab_design:
    design_path = DOCS_DIR / "PROJECT_DESIGN.md"
    if design_path.exists():
        st.markdown(design_path.read_text(encoding="utf-8"))
    else:
        st.warning("Plik docs/PROJECT_DESIGN.md nie znaleziony")

with tab_todo:
    todo_path = DOCS_DIR / "TODO.md"
    if todo_path.exists():
        st.markdown(todo_path.read_text(encoding="utf-8"))
    else:
        st.warning("Plik docs/TODO.md nie znaleziony")
