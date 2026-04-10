# TODO — jobDB

Lista funkcjonalności do zaimplementowania, pogrupowana wg priorytetów.

---

## 🔴 Priorytet 1 — Krytyczne (rdzeń systemu)

### 1.1 Brakujące scrapery (4 z 5)

Enumy i konfiguracja źródeł istnieją, ale klasy scraperów nie zostały zaimplementowane.

| Source | Portal | Uwagi |
|---|---|---|
| `justjoinit` | justjoin.it | SPA (React) — wymaga Playwright lub API |
| `pracuj` | pracuj.pl | Duży portal — możliwe zabezpieczenia anti-bot, delay 3.0s |
| `rocketjobs` | rocketjobs.pl | SPA — prawdopodobnie wymaga Playwright |
| `jooble` | jooble.org | Agregator — może mieć API publiczne |

**Do zrobienia:**
- [ ] `src/scrapers/justjoinit.py` — scraper justjoin.it (Playwright + API)
- [ ] `src/scrapers/pracuj.py` — scraper pracuj.pl
- [ ] `src/scrapers/rocketjobs.py` — scraper rocketjobs.pl
- [ ] `src/scrapers/jooble.py` — scraper jooble.org
- [ ] Rejestracja nowych scraperów w `SCRAPER_REGISTRY`
- [ ] Testy parsowania salary/seniority dla każdego portalu

### 1.2 Integracja deduplicatora w pipeline

Moduł `deduplicator.py` jest w pełni zaimplementowany (fuzzy matching company ≥70%, title ≥85%), ale **nie jest wywoływany** w `orchestrator.py`.

**Do zrobienia:**
- [ ] Wywołanie `deduplicate_offers()` w `run_pipeline()` po normalizacji
- [ ] Zapis `dedup_cluster_id` do bazy
- [ ] Dashboard: widok klastrów deduplikacji (ta sama oferta z różnych źródeł)

### 1.3 Śledzenie cyklu życia ofert

Funkcja `mark_inactive()` istnieje w `queries.py`, ale nie jest wywoływana.

**Do zrobienia:**
- [ ] Wywołanie `mark_inactive(source, active_ids)` w pipeline po upsert
- [ ] Dashboard: wskaźnik "oferty wygasłe dzisiaj"
- [ ] Metryka: średni czas życia oferty (first_seen → last_seen)

---

## 🟡 Priorytet 2 — Ważne (analityka i dane historyczne)

### 2.1 Populowanie tabeli `daily_stats`

Tabela istnieje w schemacie, ale nigdy nie jest wypełniana.

**Do zrobienia:**
- [ ] Agregacja danych po każdym uruchomieniu pipeline lub jako osobny krok
- [ ] Dashboard: wykresy trendów dziennych (nowe oferty, wygasłe, średnie salary)

### 2.2 Populowanie tabeli `job_snapshots`

Funkcja `create_daily_snapshot()` istnieje, ale nie jest wywoływana.

**Do zrobienia:**
- [ ] Automatyczne tworzenie snapshotów (np. raz dziennie w pipeline)
- [ ] Dashboard: wykres zmian salary w czasie dla konkretnej oferty/firmy/miasta

### 2.3 Moduł analizy (`src/analysis/`)

Katalog `src/analysis/` jest **pusty**.

**Pomysły na implementację:**
- [ ] Analiza trendów wynagrodzeń per miasto/technologia/seniority
- [ ] Porównania regionalne (np. Warszawa vs Kraków vs Remote)
- [ ] Detekcja anomalii (nagły wzrost/spadek ofert, outlier-owe salary)
- [ ] Indeks rynku pracy (własny wskaźnik oparty na danych)
- [ ] Eksport raportów (PDF/HTML)

### 2.4 Dashboard — podstrony (`src/dashboard/pages/`)

Katalog `pages/` jest **pusty**. Streamlit wspiera multi-page apps.

**Pomysły:**
- [ ] Strona trendów — wykresy historyczne z `daily_stats` i `job_snapshots`
- [ ] Strona porównań — zestawienie miast/źródeł/branż
- [ ] Strona szczegółów oferty — pełny widok z historią zmian
- [ ] Strona detekcji duplikatów — podgląd klastrów deduplikacji

---

## 🟢 Priorytet 3 — Infrastruktura

### 3.1 Scheduler (automatyczne scrapowanie)

Moduł `schedule` jest zainstalowany, ale nieużywany.

**Do zrobienia:**
- [ ] Cron / daemon do cyklicznego uruchamiania pipeline (np. co 6h)
- [ ] Alternatywa: GitHub Actions / Windows Task Scheduler
- [ ] Konfiguracja harmonogramu per źródło (różne częstotliwości)

### 3.2 System logowania

Aktualnie system używa `print()` i `rich.console`.

**Do zrobienia:**
- [ ] Wdrożenie `logging` (Python stdlib) z poziomami DEBUG/INFO/WARNING/ERROR
- [ ] Rotacja logów (plik + konsola)
- [ ] Strukturalne logi (JSON) dla łatwiejszego parsowania

### 3.3 Eksport danych

`EXPORTS_DIR = "data/exports"` jest zdefiniowany w config, ale nigdzie nie używany.

**Do zrobienia:**
- [ ] Eksport do CSV/Parquet/JSON
- [ ] CLI: `jobdb-export --format csv --filters ...`
- [ ] Automatyczny eksport po scrapowaniu (opcjonalny)

### 3.4 Alerting / Monitoring

**Do zrobienia:**
- [ ] Alerty przy statusie `failed` / `partial` (email, Slack, Discord webhook)
- [ ] Monitorowanie stanu scrapowania (uptime, error rate)
- [ ] Alert gdy portal zmieni strukturę HTML (0 ofert zescrapowanych)

---

## ⚪ Priorytet 4 — Migracja do hurtowni danych (PostgreSQL + Power BI)

### 4.1 Migracja DuckDB → PostgreSQL

Docelowo system będzie działał na PostgreSQL jako hurtownia danych podłączona do Power BI.

**Fazy migracji:**

#### Faza A: Przygotowanie schematu PostgreSQL
- [ ] Zaprojektować schemat gwiazdy (star schema) dla hurtowni:
  - **Tabela faktów**: `fact_job_offers` (salary, is_active, timestamps)
  - **Wymiary**: `dim_company`, `dim_location`, `dim_source`, `dim_seniority`, `dim_work_mode`
  - **Tabela faktów snapshotów**: `fact_daily_snapshots`
  - **Tabela agregatów**: `fact_daily_stats`
- [ ] Zdefiniować indeksy pod zapytania analityczne Power BI
- [ ] Dodać partycjonowanie po `scraped_at` (monthly range partitioning)
- [ ] Skrypt migracji DDL: `src/db/postgres_schema.sql`

#### Faza B: Warstwa abstrakcji bazy danych
- [ ] Abstrakcja `DatabaseBackend` (protocol/ABC) w `src/db/database.py`
- [ ] Implementacja `DuckDBBackend` (obecna logika)
- [ ] Implementacja `PostgreSQLBackend` (asyncpg lub psycopg3)
- [ ] Konfiguracja backendu w `config/settings.py` (przełącznik DuckDB ↔ PostgreSQL)
- [ ] Adapter queries — zunifikowane API niezależne od silnika

#### Faza C: Migracja danych
- [ ] Skrypt ETL: DuckDB → PostgreSQL (`scripts/migrate_to_postgres.py`)
- [ ] Walidacja danych po migracji (row counts, checksums)
- [ ] Testy regresyjne pipeline na PostgreSQL

#### Faza D: Power BI
- [ ] Konfiguracja połączenia Power BI → PostgreSQL (DirectQuery lub Import)
- [ ] Model danych Power BI oparty na star schema
- [ ] Raporty Power BI:
  - Dashboard główny (KPI, trendy, mapa miast)
  - Analiza wynagrodzeń (widełki per city/seniority/source)
  - Raport jakości danych (completeness, freshness)
  - Trendy historyczne (daily_stats + snapshots)
- [ ] Automatyczne odświeżanie datasetu (scheduled refresh)

### 4.2 Optymalizacja pod hurtownię

- [ ] Materialized views dla częstych zapytań dashboardowych
- [ ] Partycjonowanie tabeli `job_offers` po `source` lub `scraped_at`
- [ ] Indeksy GIN na `technologies` (array) i GiST na `location_city`
- [ ] Connection pooling (PgBouncer) dla wielu klientów (Streamlit + Power BI + pipeline)
- [ ] Monitoring wydajności zapytań (`pg_stat_statements`)

---

## 🔵 Priorytet 5 — Ulepszenia

### 5.1 Playwright (automatyzacja przeglądarki)

Zainstalowany (`playwright>=1.40`), ale nieużywany. Potrzebny do portali SPA (justjoin.it, rocketjobs).

**Do zrobienia:**
- [ ] Wariant `BaseScraper` z Playwright (headless browser)
- [ ] Obsługa JS-rendered content
- [ ] Pool przeglądarek z zarządzaniem zasobami

### 5.2 Walidacja jakości danych

**Do zrobienia:**
- [ ] Reguły walidacji: salary > 0, company_name nie puste, URL format
- [ ] Raport completeness % per batch (ile ofert ma salary, city, company)
- [ ] Dashboard widget z monitoringiem jakości danych
- [ ] Automatyczne oznaczanie podejrzanych danych (salary = 1 zł, tytuł < 3 znaki)

### 5.3 Rozszerzenie modelu danych

**Potencjalne nowe pola:**
- [ ] `benefits` — lista benefitów (np. prywatna opieka, multisport)
- [ ] `requirements` — wymagane umiejętności (wyodrębnione z opisu)
- [ ] `experience_years` — wymagane lata doświadczenia
- [ ] `company_size` — wielkość firmy
- [ ] `industry` — branża (bardziej szczegółowa niż category)

### 5.4 Testy

**Brakujące testy:**
- [ ] Testy normalizera (city mapping, work mode detection)
- [ ] Testy deduplicatora (fuzzy matching, klasteryzacja)
- [ ] Testy pipeline (integration test z mock scraperami)
- [ ] Testy queries (upsert, mark_inactive, snapshots z in-memory DuckDB)
- [ ] Testy dashboardu (Streamlit testing framework)

### 5.5 CI/CD

**Do zrobienia:**
- [ ] GitHub Actions: lint (ruff) + testy przy PR
- [ ] Automatyczny deploy dashboardu (np. Streamlit Cloud)
- [ ] Pre-commit hooks (ruff, formatowanie)

---

## Podsumowanie statusu

| Komponent | Status |
|---|---|
| Scraper praca.pl | ✅ Gotowy |
| Scraper justjoin.it | ❌ Brak |
| Scraper pracuj.pl | ❌ Brak |
| Scraper rocketjobs.pl | ❌ Brak |
| Scraper jooble.org | ❌ Brak |
| Normalizer | ✅ Gotowy |
| Deduplicator | ⚠️ Kod gotowy, niezintegrowany |
| Pipeline orchestrator | ✅ Gotowy (bez dedup + mark_inactive) |
| Baza danych (DDL) | ✅ Gotowa |
| Upsert + Log | ✅ Gotowe |
| mark_inactive | ⚠️ Kod gotowy, niewywoływany |
| daily_stats | ⚠️ Tabela pusta |
| job_snapshots | ⚠️ Tabela pusta |
| Dashboard (główny) | ✅ Gotowy |
| Dashboard (podstrony) | ❌ Brak |
| Moduł analizy | ❌ Brak |
| Scheduler | ❌ Brak |
| System logowania | ❌ Brak (print) |
| Eksport danych | ❌ Brak |
| Testy salary parsing | ✅ 26 testów |
| Testy normalizer | ❌ Brak |
| Testy deduplicator | ❌ Brak |
| Testy integracyjne | ❌ Brak |
| CI/CD | ❌ Brak |
| Schemat PostgreSQL (star schema) | ❌ Brak |
| Abstrakcja bazy danych | ❌ Brak (hardcoded DuckDB) |
| Migracja DuckDB → PostgreSQL | ❌ Brak |
| Power BI (raporty + połączenie) | ❌ Brak |
| Dashboard: zakładka Postęp prac | ✅ Gotowa |
| Agent: progress-tracker | ✅ Gotowy |
