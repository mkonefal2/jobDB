# TODO — jobDB

Lista funkcjonalności do zaimplementowania, pogrupowana wg priorytetów.

---

## 🔴 Priorytet 1 — Krytyczne (rdzeń systemu)

### ~~1.1 Scrapery~~ ✅ DONE

Wszystkie 5 scraperów zaimplementowane i aktywne w `SCRAPER_REGISTRY`:

| Source | Portal | Typ | Status |
|---|---|---|---|
| `pracapl` | praca.pl | HTML (selectolax) | ✅ Gotowy |
| `justjoinit` | justjoin.it | API | ✅ Gotowy |
| `rocketjobs` | rocketjobs.pl | API (wspólna baza z justjoin) | ✅ Gotowy |
| `pracuj` | pracuj.pl | Playwright | ✅ Gotowy |
| `nofluffjobs` | nofluffjobs.com | API | ✅ Gotowy |
| ~~`jooble`~~ | ~~jooble.org~~ | ~~Playwright~~ | ⛔ Wyłączony (agregator) |

### ~~1.2 Integracja deduplicatora w pipeline~~ ✅ DONE

Deduplikacja cross-source zintegrowana w `orchestrator.py` — wywoływana po upsert gdy ≥2 źródła.

### ~~1.3 Śledzenie cyklu życia ofert~~ ✅ DONE

`mark_inactive()` wywoływane w pipeline po upsert dla każdego źródła.

**Pozostałe do zrobienia:**
- [ ] Dashboard: wskaźnik "oferty wygasłe dzisiaj"
- [ ] Metryka: średni czas życia oferty (first_seen → last_seen)

---

## 🟡 Priorytet 2 — Ważne (analityka i dane historyczne)

### ~~2.1 Populowanie tabeli `daily_stats`~~ ✅ DONE

Agregacja wywoływana automatycznie w pipeline.

**Pozostałe:**
- [ ] Dashboard: wykresy trendów dziennych (nowe oferty, wygasłe, średnie salary)

### ~~2.2 Populowanie tabeli `job_snapshots`~~ ✅ DONE

`create_daily_snapshot()` wywoływane automatycznie w pipeline po scrapowaniu.

**Pozostałe:**
- [ ] Dashboard: wykres zmian salary w czasie dla konkretnej oferty/firmy/miasta

### 2.3 Moduł analizy (`src/analysis/`)

Katalog `src/analysis/` jest **pusty**.

**Pomysły na implementację:**
- [ ] Analiza trendów wynagrodzeń per miasto/technologia/seniority
- [ ] Porównania regionalne (np. Warszawa vs Kraków vs Remote)
- [ ] Detekcja anomalii (nagły wzrost/spadek ofert, outlier-owe salary)
- [ ] Indeks rynku pracy (własny wskaźnik oparty na danych)
- [ ] Eksport raportów (PDF/HTML)

### 2.4 Dashboard — rozwój (`src/dashboard/html/`)

Dashboard HTML/FastAPI jest zaimplementowany z 6 stronami.

**Pomysły:**
- [ ] Strona trendów — wykresy historyczne z `daily_stats` i `job_snapshots`
- [ ] Strona porównań — zestawienie miast/źródeł/branż
- [ ] Strona szczegółów oferty — pełny widok z historią zmian
- [ ] Strona detekcji duplikatów — podgląd klastrów deduplikacji

---

## 🟢 Priorytet 3 — Infrastruktura

### ~~3.1 Scheduler (automatyczne scrapowanie)~~ ✅ DONE

Zaimplementowany w `scripts/schedule_scraper.py`:
- Integracja z Windows Task Scheduler (`--schedule`, `--unschedule`, `--status`)
- Konfigurowalna godzina (`--time HH:MM`, domyślnie 07:00)
- Wybór źródeł (`-s pracapl pracujpl`)
- Logowanie do `data/logs/` z rotacją (ostatnie 30 plików)

### ~~3.2 System logowania~~ ✅ DONE

Zaimplementowany w scheduler:
- Python `logging` z handlerami: plik + konsola
- Format: `%(asctime)s %(levelname)-8s %(message)s`
- Pliki w `data/logs/scrape_YYYYMMDD_HHMMSS.log`
- Automatyczna rotacja — ostatnie 30 plików

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

## ⚪ Priorytet 4 — Rozszerzenia Power BI

### 4.1 Raporty Power BI

Model danych Power BI jest zaimplementowany (`powerbi/model.bim`) z 69 miarami DAX.

**Do zrobienia:**
- [ ] Raporty Power BI:
  - Dashboard główny (KPI, trendy, mapa miast)
  - Analiza wynagrodzeń (widełki per city/seniority/source)
  - Raport jakości danych (completeness, freshness)
  - Trendy historyczne (daily_stats + snapshots)
- [ ] Automatyczne odświeżanie datasetu (scheduled refresh)

### 4.2 Optymalizacja bazy

- [ ] Indeksy pod zapytania analityczne Power BI
- [ ] Monitoring wydajności zapytań

---

## 🔵 Priorytet 5 — Ulepszenia

### ~~5.1 Playwright (automatyzacja przeglądarki)~~ ✅ DONE

Używany aktywnie przez scrapery `pracujpl.py` i `jooble.py`:
- Headless browser dla JS-rendered content
- Konfigurowane timeouty w `config/settings.py`

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
- [ ] Testy queries (upsert, mark_inactive, snapshots z testową bazą MySQL)
- [ ] Testy dashboardu (FastAPI TestClient)

### 5.5 CI/CD

**Do zrobienia:**
- [ ] GitHub Actions: lint (ruff) + testy przy PR
- [ ] Automatyczny deploy dashboardu (Railway)
- [ ] Pre-commit hooks (ruff, formatowanie)

---

## Podsumowanie statusu

| Komponent | Status |
|---|---|
| Scraper praca.pl | ✅ Gotowy |
| Scraper justjoin.it | ✅ Gotowy (API) |
| Scraper pracuj.pl | ✅ Gotowy (Playwright) |
| Scraper rocketjobs.pl | ✅ Gotowy (API) |
| Scraper nofluffjobs.com | ✅ Gotowy (API) |
| Scraper jooble.org | ⛔ Wyłączony (agregator) |
| Normalizer | ✅ Gotowy |
| Deduplicator | ✅ Zintegrowany z pipeline |
| Pipeline orchestrator | ✅ Gotowy (dedup + mark_inactive + snapshots) |
| Baza danych (DDL) | ✅ Gotowa (MySQL, env vars) |
| Upsert + Log | ✅ Gotowe |
| mark_inactive | ✅ Zintegrowany |
| daily_stats | ✅ Populowane automatycznie |
| job_snapshots | ✅ Populowane automatycznie |
| Dashboard HTML/FastAPI | ✅ Gotowy (6 stron SPA) |
| Power BI model | ✅ Gotowy (69 miar DAX) |
| Moduł analizy | ❌ Brak |
| Scheduler | ✅ Windows Task Scheduler |
| Logging | ✅ Plik + konsola, rotacja |
| Deploy (Railway) | ✅ Docker + uvicorn |
| Eksport danych | ❌ Brak |
| Backup DB | ✅ mysqldump (`scripts/backup_db.py`) |
| Testy salary parsing | ✅ 26 testów |
| Testy normalizer | ❌ Brak |
| Testy deduplicator | ❌ Brak |
| Testy integracyjne | ❌ Brak |
| CI/CD | ❌ Brak |
| Schemat PostgreSQL (star schema) | ❌ Brak |
| Abstrakcja bazy danych | ❌ Brak (hardcoded MySQL) |
| Migracja MySQL → PostgreSQL | ❌ Brak |
| Power BI (raporty + połączenie) | ❌ Brak |
| Dashboard: zakładka Postęp prac | ✅ Gotowa |
| Agent: progress-tracker | ✅ Gotowy |
