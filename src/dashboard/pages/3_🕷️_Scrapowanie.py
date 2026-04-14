"""Zakładka Scrapowanie — uruchamianie scraperów z poziomu dashboardu."""

import sys
import threading
from datetime import datetime
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import SOURCES
from src.models.schema import Source
from src.pipeline.orchestrator import SCRAPER_REGISTRY

st.set_page_config(
    page_title="JobDB — Scrapowanie",
    page_icon="🕷️",
    layout="wide",
)

st.title("🕷️ Scrapowanie")
st.caption("Uruchom scrapowanie ofert z wybranego portalu")

# ── Session state init ───────────────────────────────────────────────────────
if "scrape_running" not in st.session_state:
    st.session_state.scrape_running = False
if "scrape_log" not in st.session_state:
    st.session_state.scrape_log = []


def _run_scrape(source: Source, max_pages: int | None, result_box: list) -> None:
    """Run pipeline in a thread and store result in *result_box* (plain list).

    We cannot touch st.session_state from a background thread because
    Streamlit's ScriptRunContext is not available there.
    """
    from src.pipeline.orchestrator import run_pipeline

    try:
        results = run_pipeline(sources=[source], max_pages=max_pages)
        entry = results.get(source)
        if entry:
            result_box.append(
                {
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "source": source.value,
                    "status": entry.status.value,
                    "new": entry.offers_new,
                    "updated": entry.offers_updated,
                    "errors": entry.errors,
                }
            )
        else:
            result_box.append(
                {
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "source": source.value,
                    "status": "no_result",
                    "new": 0,
                    "updated": 0,
                    "errors": 0,
                }
            )
    except Exception as e:
        result_box.append(
            {
                "time": datetime.now().strftime("%H:%M:%S"),
                "source": source.value,
                "status": f"error: {e}",
                "new": 0,
                "updated": 0,
                "errors": 1,
            }
        )


# ── Settings ─────────────────────────────────────────────────────────────────
with st.sidebar:
    max_pages = st.number_input(
        "Maks. stron do scrapowania",
        min_value=1,
        max_value=100,
        value=3,
        help="Ogranicza liczbę stron listingu do pobrania (domyślnie 3)",
    )

# ── Source cards ─────────────────────────────────────────────────────────────
st.subheader("Dostępne źródła")

cols = st.columns(len(SOURCES))

for idx, (key, cfg) in enumerate(SOURCES.items()):
    source = Source(key)
    implemented = source in SCRAPER_REGISTRY

    with cols[idx]:
        st.markdown(f"### {cfg['name']}")
        st.caption(cfg["base_url"])

        if implemented:
            st.success("✅ Obsługiwane", icon="✅")
        else:
            st.warning("🚧 Nie zaimplementowane", icon="🚧")

        if implemented:
            if st.session_state.scrape_running:
                st.button(
                    f"⏳ Scrapuj",
                    key=f"btn_{key}",
                    disabled=True,
                    use_container_width=True,
                )
            else:
                if st.button(
                    f"▶️ Scrapuj",
                    key=f"btn_{key}",
                    use_container_width=True,
                ):
                    st.session_state.scrape_running = True
                    result_box: list[dict] = []
                    thread = threading.Thread(
                        target=_run_scrape,
                        args=(source, max_pages, result_box),
                        daemon=True,
                    )
                    thread.start()
                    thread.join()  # wait for completion so we can rerun
                    st.session_state.scrape_log.extend(result_box)
                    st.session_state.scrape_running = False
                    st.rerun()
        else:
            st.button(
                "🚧 Niedostępne",
                key=f"btn_{key}",
                disabled=True,
                use_container_width=True,
            )

# ── Scrape log ───────────────────────────────────────────────────────────────
if st.session_state.scrape_log:
    st.divider()
    st.subheader("📜 Log scrapowania (sesja)")

    for entry in reversed(st.session_state.scrape_log):
        status_icon = "✅" if entry["status"] == "success" else "⚠️"
        st.markdown(
            f"**{entry['time']}** — {status_icon} **{entry['source']}** | "
            f"Nowe: {entry['new']}, Zaktualizowane: {entry['updated']}, "
            f"Błędy: {entry['errors']} | Status: `{entry['status']}`"
        )
