# Power BI — jobDB Documentation

> Kompletna dokumentacja modelu danych, calculated columns, measures i raportów Power BI
> dla projektu **jobDB** — trackera polskiego rynku pracy.

**Źródło danych:** MySQL 8+ (`localhost:3306/jobdb`) — 112k+ ofert pracy z 6 portali  
**Odświeżanie:** Scheduled Refresh co 6h (Import Mode) lub DirectQuery  
**Autor:** jobDB Pipeline (Python scrapers → MySQL → Power BI)

---

## Spis treści

1. [Architektura danych](#1-architektura-danych)
2. [Połączenie ze źródłem danych](#2-połączenie-ze-źródłem-danych)
3. [Power Query — transformacje (M)](#3-power-query--transformacje-m)
4. [Model danych (Star Schema)](#4-model-danych-star-schema)
5. [Relacje](#5-relacje)
6. [Tabela kalendarza (Date Table)](#6-tabela-kalendarza-date-table)
7. [Calculated Columns (DAX)](#7-calculated-columns-dax)
8. [Measures (DAX)](#8-measures-dax)
9. [Hierarchie](#9-hierarchie)
10. [Strony raportu](#10-strony-raportu)
11. [Row-Level Security (RLS)](#11-row-level-security-rls)
12. [Optymalizacja wydajności](#12-optymalizacja-wydajności)
13. [Deployment & Refresh](#13-deployment--refresh)

---

## 1. Architektura danych

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│   Python Scrapers   │────▶│   MySQL Database     │────▶│     Power BI        │
│                     │     │   (jobdb)            │     │   (Import Mode)     │
│ • praca.pl          │     │                      │     │                     │
│ • pracuj.pl         │     │ • job_offers  112k+  │     │ • Star Schema       │
│ • justjoin.it       │     │ • job_snapshots      │     │ • DAX Measures      │
│ • rocketjobs.pl     │     │ • daily_stats        │     │ • 6 Report Pages    │
│ • nofluffjobs.pl    │     │ • scrape_log         │     │ • Scheduled Refresh │
│ • jooble.org        │     └─────────────────────┘     └─────────────────────┘
└─────────────────────┘
```

**Tryb połączenia: Import Mode** (zalecany)
- Dane ładowane do pamięci VertiPaq — najlepsza wydajność
- Scheduled Refresh co 6h zsynchronizowany z pipeline scraping
- Incremental Refresh na tabeli `job_offers` po kolumnie `scraped_at`

---

## 2. Połączenie ze źródłem danych

### 2.1 MySQL Connector

Power BI Desktop → Get Data → MySQL Database:

| Parametr | Wartość |
|----------|---------|
| Server | `localhost:3306` |
| Database | `jobdb` |
| Data Connectivity Mode | `Import` |
| Advanced: Command timeout | `600` (sekund) |

### 2.2 Native Query (opcjonalnie)

Dla optymalizacji ładowania można użyć natywnego SQL bezpośrednio:

```sql
-- Załaduj tylko aktywne oferty z ostatnich 90 dni
SELECT * FROM job_offers
WHERE scraped_at >= DATE_SUB(CURRENT_DATE, INTERVAL 90 DAY)
```

### 2.3 Parametry połączenia

Utwórz parametry Power BI dla elastycznej konfiguracji:

| Parametr | Typ | Wartość domyślna | Opis |
|----------|-----|-------------------|------|
| `pDBServer` | Text | `localhost:3306` | Adres serwera MySQL |
| `pDBName` | Text | `jobdb` | Nazwa bazy danych |
| `pDaysBack` | Whole Number | `90` | Ile dni wstecz ładować |

---

## 3. Power Query — transformacje (M)

> **⚠️ WYMAGANE:** Przed wklejeniem poniższych zapytań M, najpierw utwórz parametry
> z sekcji [2.3](#23-parametry-połączenia) (`pDBServer`, `pDBName`, `pDaysBack`).
> W Power BI Desktop: **Home → Manage Parameters → New Parameter** — dodaj wszystkie 3.
> Bez nich pojawi się błąd: *Expression.Error: Import pDBServer nie pasuje do żadnego eksportu*.

### 3.1 Tabela `job_offers` — główna transformacja

```m
let
    // 1. Połączenie z MySQL
    Source = MySQL.Database(pDBServer, pDBName),
    job_offers = Source{[Schema="jobdb", Item="job_offers"]}[Data],

    // 2. Filtruj aktywne oferty (opcjonalnie z parametrem dat)
    FilteredRows = Table.SelectRows(job_offers, each
        [scraped_at] >= Date.AddDays(DateTime.LocalNow(), -pDaysBack)
    ),

    // 3. Typy kolumn
    TypedColumns = Table.TransformColumnTypes(FilteredRows, {
        {"id", type text},
        {"source", type text},
        {"title", type text},
        {"company_name", type text},
        {"location_city", type text},
        {"location_region", type text},
        {"work_mode", type text},
        {"seniority", type text},
        {"employment_type", type text},
        {"salary_min", type number},
        {"salary_max", type number},
        {"salary_currency", type text},
        {"salary_period", type text},
        {"salary_type", type text},
        {"category", type text},
        {"published_at", type datetime},
        {"first_seen_at", type datetime},
        {"last_seen_at", type datetime},
        {"is_active", type logical},
        {"scraped_at", type datetime}
    }),

    // 4. Normalizacja employment_type — uproszczenie 76 wariantów do kategorii bazowych
    NormalizedEmployment = Table.AddColumn(TypedColumns, "employment_category", each
        if Text.Contains([employment_type] ?? "", "B2B") and Text.Contains([employment_type] ?? "", "UoP")
            then "UoP + B2B"
        else if [employment_type] = "B2B" then "B2B"
        else if [employment_type] = "UoP" then "UoP"
        else if Text.Contains([employment_type] ?? "", "UZ")
            or Text.Contains([employment_type] ?? "", "zlecenie")
            then "Umowa zlecenie"
        else if [employment_type] = "staż" then "Staż"
        else if [employment_type] = null then "Nieokreślony"
        else "Inne",
        type text
    ),

    // 5. Parsowanie JSON technologies do tekstu rozdzielonego przecinkami
    ParsedTech = Table.TransformColumns(NormalizedEmployment, {
        {"technologies", each
            try Text.Combine(
                List.Transform(Json.Document(_), each Text.From(_)),
                ", "
            ) otherwise null,
            type text
        }
    }),

    // 6. Dodanie kolumny daty (bez czasu) do relacji z kalendarzem
    AddDateKey = Table.AddColumn(ParsedTech, "scraped_date", each
        DateTime.Date([scraped_at]), type date
    ),

    AddPublishedDate = Table.AddColumn(AddDateKey, "published_date", each
        DateTime.Date([published_at]), type date
    ),

    // 7. Dodanie flagi has_salary
    AddHasSalary = Table.AddColumn(AddPublishedDate, "has_salary", each
        [salary_min] <> null and [salary_min] > 0, type logical
    ),

    // 8. Usunięcie niepotrzebnych kolumn (opis, logo, raw location, dedup)
    RemovedColumns = Table.RemoveColumns(AddHasSalary, {
        "description_text", "company_logo_url", "source_id",
        "source_url", "location_raw", "dedup_cluster_id"
    })
in
    RemovedColumns
```

### 3.2 Tabela `scrape_log` — monitoring pipeline

```m
let
    Source = MySQL.Database(pDBServer, pDBName),
    scrape_log = Source{[Schema="jobdb", Item="scrape_log"]}[Data],

    TypedColumns = Table.TransformColumnTypes(scrape_log, {
        {"run_id", type text},
        {"source", type text},
        {"started_at", type datetime},
        {"finished_at", type datetime},
        {"offers_scraped", Int64.Type},
        {"offers_new", Int64.Type},
        {"offers_updated", Int64.Type},
        {"errors", Int64.Type},
        {"status", type text}
    }),

    // Czas trwania scrapowania w sekundach
    AddDuration = Table.AddColumn(TypedColumns, "duration_seconds", each
        Duration.TotalSeconds([finished_at] - [started_at]),
        type number
    ),

    AddDate = Table.AddColumn(AddDuration, "scrape_date", each
        DateTime.Date([started_at]), type date
    )
in
    AddDate
```

### 3.3 Tabela `job_snapshots` — dane historyczne

```m
let
    Source = MySQL.Database(pDBServer, pDBName),
    snapshots = Source{[Schema="jobdb", Item="job_snapshots"]}[Data],

    TypedColumns = Table.TransformColumnTypes(snapshots, {
        {"snapshot_date", type date},
        {"offer_id", type text},
        {"salary_min", type number},
        {"salary_max", type number},
        {"is_active", type logical}
    })
in
    TypedColumns
```

### 3.4 Tabela `daily_stats` — agregaty dzienne

```m
let
    Source = MySQL.Database(pDBServer, pDBName),
    daily_stats = Source{[Schema="jobdb", Item="daily_stats"]}[Data],

    TypedColumns = Table.TransformColumnTypes(daily_stats, {
        {"stat_date", type date},
        {"source", type text},
        {"category", type text},
        {"location_city", type text},
        {"total_offers", Int64.Type},
        {"offers_with_salary", Int64.Type},
        {"avg_salary_min", type number},
        {"avg_salary_max", type number},
        {"new_offers", Int64.Type},
        {"expired_offers", Int64.Type}
    })
in
    TypedColumns
```

---

## 4. Model danych (Star Schema)

```
                        ┌──────────────┐
                        │  dim_Date    │
                        │ (Calendar)   │
                        └──────┬───────┘
                               │ 1:N
    ┌──────────────┐    ┌──────┴───────┐    ┌──────────────┐
    │ dim_Source    │───▶│ fact_Offers  │◀───│ dim_Seniority│
    └──────────────┘ 1:N└──────┬───────┘N:1 └──────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
    ┌─────────┴────┐  ┌───────┴──────┐  ┌──────┴───────┐
    │ dim_Location │  │ dim_WorkMode │  │ dim_Contract │
    └──────────────┘  └──────────────┘  └──────────────┘
```

### Wymiary (Dimension Tables)

Wymiary tworzone jako **Calculated Tables** w DAX:

#### `dim_Source` — źródła danych

```dax
dim_Source =
DATATABLE(
    "SourceKey",   STRING,
    "SourceName",  STRING,
    "SourceURL",   STRING,
    "SourceType",  STRING,
    {
        { "pracapl",     "Praca.pl",      "https://www.praca.pl",      "Job Board"   },
        { "justjoinit",  "JustJoin.it",   "https://justjoin.it",       "IT Niche"    },
        { "pracuj",      "Pracuj.pl",     "https://www.pracuj.pl",     "Job Board"   },
        { "rocketjobs",  "RocketJobs.pl", "https://rocketjobs.pl",     "IT Niche"    },
        { "nofluffjobs", "NoFluffJobs",   "https://nofluffjobs.com",   "IT Niche"    },
        { "jooble",      "Jooble",        "https://pl.jooble.org",     "Aggregator"  }
    }
)
```

#### `dim_Seniority` — poziomy doświadczenia

```dax
dim_Seniority =
DATATABLE(
    "SeniorityKey",    STRING,
    "SeniorityName",   STRING,
    "SeniorityOrder",  INTEGER,
    "SeniorityGroup",  STRING,
    {
        { "intern",   "Intern / Stażysta",  1, "Junior"     },
        { "junior",   "Junior",             2, "Junior"     },
        { "mid",      "Mid / Regular",      3, "Mid"        },
        { "senior",   "Senior",             4, "Senior"     },
        { "lead",     "Lead / Tech Lead",   5, "Senior"     },
        { "manager",  "Manager / Kierownik",6, "Management" },
        { "unknown",  "Nieokreślony",       7, "Unknown"    }
    }
)
```

#### `dim_WorkMode` — tryby pracy

```dax
dim_WorkMode =
DATATABLE(
    "WorkModeKey",   STRING,
    "WorkModeName",  STRING,
    "WorkModeIcon",  STRING,
    "WorkModeOrder", INTEGER,
    {
        { "remote",  "Praca zdalna",     "🏠", 1 },
        { "hybrid",  "Praca hybrydowa",  "🔄", 2 },
        { "onsite",  "Praca stacjonarna","🏢", 3 },
        { "unknown", "Nieokreślony",     "❓", 4 }
    }
)
```

#### `dim_Location` — generowana z danych

```dax
dim_Location =
VAR _cities =
    SUMMARIZE(
        job_offers,
        job_offers[location_city],
        job_offers[location_region]
    )
RETURN
    ADDCOLUMNS(
        _cities,
        "CityRank", RANKX(_cities, CALCULATE(COUNTROWS(job_offers)), , DESC),
        "IsTopCity", IF(
            RANKX(_cities, CALCULATE(COUNTROWS(job_offers)), , DESC) <= 10,
            "Top 10",
            "Inne"
        ),
        "Region", IF(
            ISBLANK(job_offers[location_region]),
            "Nieznany",
            job_offers[location_region]
        )
    )
```

#### `dim_Contract` — typy umów (znormalizowane)

```dax
dim_Contract =
DATATABLE(
    "ContractKey",    STRING,
    "ContractName",   STRING,
    "ContractGroup",  STRING,
    "ContractOrder",  INTEGER,
    {
        { "UoP",             "Umowa o pracę",       "Etat",        1 },
        { "B2B",             "B2B / Kontrakt",      "Kontrakt",    2 },
        { "UoP + B2B",       "UoP + B2B",           "Mieszane",    3 },
        { "Umowa zlecenie",  "Umowa zlecenie",      "Cywilnoprawna", 4 },
        { "Staż",            "Staż / Praktyki",     "Staż",        5 },
        { "Inne",            "Inna forma",          "Inne",        6 },
        { "Nieokreślony",    "Nieokreślony",        "Nieokreślony",7 }
    }
)
```

---

## 5. Relacje

| Z tabeli | Kolumna | Do tabeli | Kolumna | Kardynalność | Kierunek | Aktywna |
|----------|---------|-----------|---------|--------------|----------|---------|
| `job_offers` | `source` | `dim_Source` | `SourceKey` | N:1 | Single | ✅ |
| `job_offers` | `seniority` | `dim_Seniority` | `SeniorityKey` | N:1 | Single | ✅ |
| `job_offers` | `work_mode` | `dim_WorkMode` | `WorkModeKey` | N:1 | Single | ✅ |
| `job_offers` | `employment_category` | `dim_Contract` | `ContractKey` | N:1 | Single | ✅ |
| `job_offers` | `scraped_date` | `dim_Date` | `Date` | N:1 | Single | ✅ |
| `job_offers` | `published_date` | `dim_Date` | `Date` | N:1 | Single | ❌ (inactive) |
| `job_snapshots` | `offer_id` | `job_offers` | `id` | N:1 | Single | ✅ |
| `job_snapshots` | `snapshot_date` | `dim_Date` | `Date` | N:1 | Single | ✅ |
| `daily_stats` | `stat_date` | `dim_Date` | `Date` | N:1 | Single | ✅ |
| `daily_stats` | `source` | `dim_Source` | `SourceKey` | N:1 | Single | ✅ |
| `scrape_log` | `scrape_date` | `dim_Date` | `Date` | N:1 | Single | ✅ |
| `scrape_log` | `source` | `dim_Source` | `SourceKey` | N:1 | Single | ✅ |

> **Uwaga:** Relacja `published_date → dim_Date` jest nieaktywna — aktywowana przez `USERELATIONSHIP()` w measures.

---

## 6. Tabela kalendarza (Date Table)

```dax
dim_Date =
VAR _minDate = MIN(job_offers[scraped_at])
VAR _maxDate = MAX(job_offers[scraped_at])
VAR _startDate = DATE(YEAR(_minDate), MONTH(_minDate), 1)
VAR _endDate = EOMONTH(_maxDate, 1)
VAR _dates = CALENDAR(_startDate, _endDate)
RETURN
    ADDCOLUMNS(
        _dates,
        "Year",             YEAR([Date]),
        "Month Number",     MONTH([Date]),
        "Month Name",       FORMAT([Date], "MMMM", "pl-PL"),
        "Month Short",      FORMAT([Date], "MMM", "pl-PL"),
        "Year-Month",       FORMAT([Date], "YYYY-MM"),
        "Quarter",          "Q" & FORMAT([Date], "Q"),
        "Year-Quarter",     FORMAT([Date], "YYYY") & "-Q" & FORMAT([Date], "Q"),
        "Day of Week",      WEEKDAY([Date], 2),
        "Day Name",         FORMAT([Date], "dddd", "pl-PL"),
        "Week Number",      WEEKNUM([Date], 2),
        "Is Weekend",       IF(WEEKDAY([Date], 2) >= 6, TRUE(), FALSE()),
        "Is Current Month", IF(
            YEAR([Date]) = YEAR(TODAY()) && MONTH([Date]) = MONTH(TODAY()),
            TRUE(), FALSE()
        ),
        "Month-Year Sort",  YEAR([Date]) * 100 + MONTH([Date]),
        "Relative Day",     DATEDIFF([Date], TODAY(), DAY) * -1
    )
```

Oznacz jako tabelę dat: `Table Tools > Mark as Date Table > Date`

---

## 7. Calculated Columns (DAX)

### 7.1 Na tabeli `job_offers`

#### Salary — kolumny kalkulowane

```dax
// Średnie wynagrodzenie (midpoint widełek)
Salary Midpoint =
IF(
    job_offers[salary_min] > 0 && job_offers[salary_max] > 0,
    (job_offers[salary_min] + job_offers[salary_max]) / 2,
    BLANK()
)
```

```dax
// Rozpiętość widełek (spread)
Salary Spread =
IF(
    job_offers[salary_min] > 0 && job_offers[salary_max] > 0,
    job_offers[salary_max] - job_offers[salary_min],
    BLANK()
)
```

```dax
// Rozpiętość widełek jako procent
Salary Spread % =
IF(
    job_offers[salary_min] > 0,
    DIVIDE(
        job_offers[salary_max] - job_offers[salary_min],
        job_offers[salary_min],
        0
    ),
    BLANK()
)
```

```dax
// Miesięczne wynagrodzenie znormalizowane (przeliczenie godzinowe/dzienne/roczne → miesięczne)
Salary Monthly Normalized =
VAR _min = job_offers[salary_min]
VAR _max = job_offers[salary_max]
VAR _mid = DIVIDE(_min + _max, 2, BLANK())
VAR _period = job_offers[salary_period]
RETURN
    SWITCH(
        _period,
        "month", _mid,
        "hour",  _mid * 168,        -- 21 dni × 8h = 168h
        "day",   _mid * 21,          -- 21 dni roboczych
        "year",  DIVIDE(_mid, 12),
        BLANK()
    )
```

```dax
// Przedział wynagrodzenia (salary band)
Salary Band =
VAR _monthly = job_offers[Salary Monthly Normalized]
RETURN
    SWITCH(
        TRUE(),
        ISBLANK(_monthly),                    "Brak danych",
        _monthly < 5000,                       "< 5 000 PLN",
        _monthly >= 5000  && _monthly < 8000,  "5 000 – 7 999",
        _monthly >= 8000  && _monthly < 12000, "8 000 – 11 999",
        _monthly >= 12000 && _monthly < 16000, "12 000 – 15 999",
        _monthly >= 16000 && _monthly < 22000, "16 000 – 21 999",
        _monthly >= 22000 && _monthly < 30000, "22 000 – 29 999",
        _monthly >= 30000,                     "30 000+ PLN",
        "Brak danych"
    )
```

```dax
// Sort order dla Salary Band
Salary Band Order =
VAR _monthly = job_offers[Salary Monthly Normalized]
RETURN
    SWITCH(
        TRUE(),
        ISBLANK(_monthly), 99,
        _monthly < 5000,   1,
        _monthly < 8000,   2,
        _monthly < 12000,  3,
        _monthly < 16000,  4,
        _monthly < 22000,  5,
        _monthly < 30000,  6,
        _monthly >= 30000, 7,
        99
    )
```

#### Czas życia oferty

```dax
// Ile dni oferta jest/była aktywna
Offer Lifespan Days =
VAR _start = job_offers[first_seen_at]
VAR _end = IF(job_offers[is_active], NOW(), job_offers[last_seen_at])
RETURN
    IF(
        NOT ISBLANK(_start),
        DATEDIFF(_start, _end, DAY),
        BLANK()
    )
```

```dax
// Kategoria czasu życia oferty
Offer Lifespan Category =
VAR _days = job_offers[Offer Lifespan Days]
RETURN
    SWITCH(
        TRUE(),
        ISBLANK(_days),    "Nieznane",
        _days <= 3,         "1–3 dni",
        _days <= 7,         "4–7 dni",
        _days <= 14,        "1–2 tygodnie",
        _days <= 30,        "2–4 tygodnie",
        _days <= 60,        "1–2 miesiące",
        _days > 60,         "60+ dni"
    )
```

#### Klasyfikacja stanowiska

```dax
// Czy oferta IT (na podstawie tytułu + source)
Is IT Offer =
VAR _title = LOWER(job_offers[title])
VAR _source = job_offers[source]
VAR _itKeywords = {"developer", "programist", "engineer", "devops", "frontend",
                   "backend", "fullstack", "full-stack", "data", "analyst",
                   "qa", "tester", "scrum", "agile", "cloud", "architect",
                   "python", "java", "react", ".net", "sql", "admin",
                   "cybersec", "security", "sysadmin", "kubernetes", "docker"}
VAR _isITSource = _source IN {"justjoinit", "rocketjobs", "nofluffjobs"}
VAR _hasTechInTitle = 
    SUMX(
        _itKeywords,
        IF(CONTAINSSTRING(_title, [Value]), 1, 0)
    ) > 0
RETURN
    _isITSource || _hasTechInTitle
```

```dax
// Flaga: czy oferta ma pełne dane (data quality score)
Data Completeness Score =
VAR _fields = {
    IF(NOT ISBLANK(job_offers[company_name]), 1, 0),
    IF(NOT ISBLANK(job_offers[location_city]), 1, 0),
    IF(job_offers[work_mode] <> "unknown", 1, 0),
    IF(job_offers[seniority] <> "unknown", 1, 0),
    IF(NOT ISBLANK(job_offers[employment_type]), 1, 0),
    IF(NOT ISBLANK(job_offers[salary_min]), 1, 0),
    IF(NOT ISBLANK(job_offers[category]), 1, 0)
}
RETURN
    DIVIDE(SUMX(_fields, [Value]), 7, 0)
```

```dax
// Etykieta Data Quality
Data Quality Label =
VAR _score = job_offers[Data Completeness Score]
RETURN
    SWITCH(
        TRUE(),
        _score >= 0.85, "🟢 Wysoka",
        _score >= 0.57, "🟡 Średnia",
        TRUE(),         "🔴 Niska"
    )
```

---

## 8. Measures (DAX)

### 8.1 Measures — KPI podstawowe

```dax
// ═══════════════════════════════════════
// FOLDER: 📊 KPI
// ═══════════════════════════════════════

Total Offers =
COUNTROWS(job_offers)

Active Offers =
CALCULATE(
    COUNTROWS(job_offers),
    job_offers[is_active] = TRUE()
)

Inactive Offers =
CALCULATE(
    COUNTROWS(job_offers),
    job_offers[is_active] = FALSE()
)

Offers With Salary =
CALCULATE(
    COUNTROWS(job_offers),
    NOT ISBLANK(job_offers[salary_min]),
    job_offers[salary_min] > 0
)

Salary Transparency % =
DIVIDE([Offers With Salary], [Total Offers], 0)

Unique Companies =
DISTINCTCOUNT(job_offers[company_name])

Unique Cities =
DISTINCTCOUNT(job_offers[location_city])

Unique Sources =
DISTINCTCOUNT(job_offers[source])
```

### 8.2 Measures — Wynagrodzenia

```dax
// ═══════════════════════════════════════
// FOLDER: 💰 Wynagrodzenia
// ═══════════════════════════════════════

Avg Salary Min =
CALCULATE(
    AVERAGE(job_offers[salary_min]),
    NOT ISBLANK(job_offers[salary_min]),
    job_offers[salary_min] > 0
)

Avg Salary Max =
CALCULATE(
    AVERAGE(job_offers[salary_max]),
    NOT ISBLANK(job_offers[salary_max]),
    job_offers[salary_max] > 0
)

Avg Salary Midpoint =
CALCULATE(
    AVERAGE(job_offers[Salary Midpoint]),
    NOT ISBLANK(job_offers[Salary Midpoint])
)

Median Salary Midpoint =
CALCULATE(
    MEDIAN(job_offers[Salary Midpoint]),
    NOT ISBLANK(job_offers[Salary Midpoint])
)

Salary P10 =
CALCULATE(
    PERCENTILE.INC(job_offers[Salary Midpoint], 0.10),
    NOT ISBLANK(job_offers[Salary Midpoint])
)

Salary P25 =
CALCULATE(
    PERCENTILE.INC(job_offers[Salary Midpoint], 0.25),
    NOT ISBLANK(job_offers[Salary Midpoint])
)

Salary P75 =
CALCULATE(
    PERCENTILE.INC(job_offers[Salary Midpoint], 0.75),
    NOT ISBLANK(job_offers[Salary Midpoint])
)

Salary P90 =
CALCULATE(
    PERCENTILE.INC(job_offers[Salary Midpoint], 0.90),
    NOT ISBLANK(job_offers[Salary Midpoint])
)

Avg Salary Spread =
CALCULATE(
    AVERAGE(job_offers[Salary Spread]),
    NOT ISBLANK(job_offers[Salary Spread])
)

// Znormalizowane wynagrodzenie miesięczne (PLN, month)
Avg Monthly Salary PLN =
CALCULATE(
    AVERAGE(job_offers[Salary Monthly Normalized]),
    job_offers[salary_currency] = "PLN",
    NOT ISBLANK(job_offers[Salary Monthly Normalized])
)

Median Monthly Salary PLN =
CALCULATE(
    MEDIAN(job_offers[Salary Monthly Normalized]),
    job_offers[salary_currency] = "PLN",
    NOT ISBLANK(job_offers[Salary Monthly Normalized])
)

// Dynamiczne formatowanie wynagrodzeń
Salary Display =
VAR _avg = [Avg Salary Midpoint]
RETURN
    IF(
        NOT ISBLANK(_avg),
        FORMAT(_avg, "#,##0") & " PLN",
        "Brak danych"
    )
```

### 8.3 Measures — Trendy czasowe (Time Intelligence)

```dax
// ═══════════════════════════════════════
// FOLDER: 📈 Trendy
// ═══════════════════════════════════════

// Oferty w poprzednim miesiącu
Offers Previous Month =
CALCULATE(
    [Total Offers],
    DATEADD(dim_Date[Date], -1, MONTH)
)

// Zmiana MoM (Month over Month)
Offers MoM Change =
VAR _current = [Total Offers]
VAR _previous = [Offers Previous Month]
RETURN
    IF(
        NOT ISBLANK(_previous) && _previous > 0,
        DIVIDE(_current - _previous, _previous, 0),
        BLANK()
    )

// Oferty MoM — ikona trendu
Offers MoM Trend Icon =
VAR _change = [Offers MoM Change]
RETURN
    SWITCH(
        TRUE(),
        ISBLANK(_change), "➡️",
        _change > 0.05,   "📈",
        _change < -0.05,  "📉",
        "➡️"
    )

// Wynagrodzenie w poprzednim miesiącu
Avg Salary Previous Month =
CALCULATE(
    [Avg Salary Midpoint],
    DATEADD(dim_Date[Date], -1, MONTH)
)

// Zmiana wynagrodzenia MoM
Salary MoM Change =
VAR _current = [Avg Salary Midpoint]
VAR _previous = [Avg Salary Previous Month]
RETURN
    IF(
        NOT ISBLANK(_previous) && _previous > 0,
        DIVIDE(_current - _previous, _previous, 0),
        BLANK()
    )

// Nowe oferty dziś
New Offers Today =
CALCULATE(
    COUNTROWS(job_offers),
    job_offers[scraped_date] = TODAY()
)

// Nowe oferty w bieżącym tygodniu
New Offers This Week =
CALCULATE(
    COUNTROWS(job_offers),
    DATESINPERIOD(dim_Date[Date], TODAY(), -7, DAY)
)

// Rolling 7-day average
Offers Rolling 7D Avg =
AVERAGEX(
    DATESINPERIOD(dim_Date[Date], MAX(dim_Date[Date]), -7, DAY),
    CALCULATE(COUNTROWS(job_offers))
)

// Rolling 30-day average
Offers Rolling 30D Avg =
AVERAGEX(
    DATESINPERIOD(dim_Date[Date], MAX(dim_Date[Date]), -30, DAY),
    CALCULATE(COUNTROWS(job_offers))
)

// Cumulative offers (running total)
Offers Running Total =
CALCULATE(
    [Total Offers],
    FILTER(
        ALL(dim_Date[Date]),
        dim_Date[Date] <= MAX(dim_Date[Date])
    )
)

// YTD Offers (Year to Date)
Offers YTD =
CALCULATE(
    [Total Offers],
    DATESYTD(dim_Date[Date])
)
```

### 8.4 Measures — Analiza źródeł

```dax
// ═══════════════════════════════════════
// FOLDER: 🌐 Źródła
// ═══════════════════════════════════════

// Udział źródła w total (%)
Source Share % =
DIVIDE([Total Offers], CALCULATE([Total Offers], ALL(job_offers[source])), 0)

// Przejrzystość wynagrodzeń per source
Source Salary Transparency % =
DIVIDE(
    [Offers With Salary],
    [Total Offers],
    0
)

// Najlepsze źródło pod kątem danych salary
Best Salary Source =
VAR _table =
    ADDCOLUMNS(
        VALUES(job_offers[source]),
        "@transparency", CALCULATE([Salary Transparency %])
    )
RETURN
    MAXX(TOPN(1, _table, [@transparency], DESC), job_offers[source])

// Średnia jakość danych per source
Avg Data Quality =
AVERAGE(job_offers[Data Completeness Score])
```

### 8.5 Measures — Analiza lokalizacji

```dax
// ═══════════════════════════════════════
// FOLDER: 🗺️ Lokalizacja
// ═══════════════════════════════════════

// % ofert remote
Remote Share % =
DIVIDE(
    CALCULATE(COUNTROWS(job_offers), job_offers[work_mode] = "remote"),
    COUNTROWS(job_offers),
    0
)

// Premium salaryjne za remote (vs onsite)
Remote Salary Premium =
VAR _remoteAvg = CALCULATE([Avg Salary Midpoint], job_offers[work_mode] = "remote")
VAR _onsiteAvg = CALCULATE([Avg Salary Midpoint], job_offers[work_mode] = "onsite")
RETURN
    IF(
        NOT ISBLANK(_remoteAvg) && NOT ISBLANK(_onsiteAvg) && _onsiteAvg > 0,
        DIVIDE(_remoteAvg - _onsiteAvg, _onsiteAvg, 0),
        BLANK()
    )

// Dominujące miasto w kontekście filtrów
Top City =
VAR _table =
    ADDCOLUMNS(
        VALUES(job_offers[location_city]),
        "@count", CALCULATE(COUNTROWS(job_offers))
    )
RETURN
    MAXX(TOPN(1, _table, [@count], DESC), job_offers[location_city])

// Indeks koncentracji (HHI — Herfindahl)
City Concentration HHI =
VAR _total = [Total Offers]
VAR _shares =
    ADDCOLUMNS(
        VALUES(job_offers[location_city]),
        "@share", DIVIDE(CALCULATE(COUNTROWS(job_offers)), _total, 0)
    )
RETURN
    SUMX(_shares, [@share] ^ 2)

// Warszawa vs reszta
Warsaw Share % =
DIVIDE(
    CALCULATE(COUNTROWS(job_offers), job_offers[location_city] = "Warszawa"),
    COUNTROWS(job_offers),
    0
)
```

### 8.6 Measures — Analiza firm

```dax
// ═══════════════════════════════════════
// FOLDER: 🏢 Firmy
// ═══════════════════════════════════════

// Średnia liczba ofert per firma
Avg Offers Per Company =
DIVIDE([Total Offers], [Unique Companies], 0)

// Firmy z >= 5 ofertami (duzi pracodawcy)
Large Employers Count =
CALCULATE(
    DISTINCTCOUNT(job_offers[company_name]),
    FILTER(
        VALUES(job_offers[company_name]),
        CALCULATE(COUNTROWS(job_offers)) >= 5
    )
)

// % ofert od Top 10 firm
Top10 Companies Share % =
VAR _top10 =
    TOPN(
        10,
        SUMMARIZE(job_offers, job_offers[company_name]),
        CALCULATE(COUNTROWS(job_offers)),
        DESC
    )
VAR _top10Count =
    CALCULATE(
        COUNTROWS(job_offers),
        TREATAS(_top10, job_offers[company_name])
    )
RETURN
    DIVIDE(_top10Count, CALCULATE(COUNTROWS(job_offers), ALL(job_offers[company_name])), 0)

// Czy firma oferuje remote?
Company Remote Availability =
VAR _hasRemote =
    CALCULATE(
        COUNTROWS(job_offers),
        job_offers[work_mode] = "remote"
    )
RETURN
    IF(_hasRemote > 0, "✅ Tak", "❌ Nie")
```

### 8.7 Measures — Analiza seniority

```dax
// ═══════════════════════════════════════
// FOLDER: 🎯 Seniority
// ═══════════════════════════════════════

// Luka płacowa Junior vs Senior
Junior Senior Salary Gap =
VAR _junior = CALCULATE([Avg Salary Midpoint], job_offers[seniority] = "junior")
VAR _senior = CALCULATE([Avg Salary Midpoint], job_offers[seniority] = "senior")
RETURN
    IF(
        NOT ISBLANK(_junior) && NOT ISBLANK(_senior),
        _senior - _junior,
        BLANK()
    )

// Mnożnik Senior/Junior
Senior Junior Multiplier =
VAR _junior = CALCULATE([Median Salary Midpoint], job_offers[seniority] = "junior")
VAR _senior = CALCULATE([Median Salary Midpoint], job_offers[seniority] = "senior")
RETURN
    IF(
        NOT ISBLANK(_junior) && _junior > 0,
        DIVIDE(_senior, _junior),
        BLANK()
    )

// Seniority Mix %
Seniority Share % =
DIVIDE(
    COUNTROWS(job_offers),
    CALCULATE(COUNTROWS(job_offers), ALL(job_offers[seniority])),
    0
)

// Demand Index (stosunek junior do senior — rynek pracodawcy vs pracownika)
Market Demand Index =
VAR _junior = CALCULATE(COUNTROWS(job_offers), job_offers[seniority] = "junior")
VAR _senior = CALCULATE(COUNTROWS(job_offers), job_offers[seniority] = "senior")
RETURN
    IF(
        _senior > 0,
        DIVIDE(_junior, _senior),
        BLANK()
    )
```

### 8.8 Measures — jakość danych i monitoring pipeline

```dax
// ═══════════════════════════════════════
// FOLDER: 🔧 Data Quality & Pipeline
// ═══════════════════════════════════════

// Completeness per pole
Completeness Company % =
DIVIDE(
    CALCULATE(COUNTROWS(job_offers), NOT ISBLANK(job_offers[company_name])),
    COUNTROWS(job_offers),
    0
)

Completeness City % =
DIVIDE(
    CALCULATE(COUNTROWS(job_offers), NOT ISBLANK(job_offers[location_city])),
    COUNTROWS(job_offers),
    0
)

Completeness Salary % =
[Salary Transparency %]

Completeness Seniority % =
DIVIDE(
    CALCULATE(COUNTROWS(job_offers), job_offers[seniority] <> "unknown"),
    COUNTROWS(job_offers),
    0
)

Completeness WorkMode % =
DIVIDE(
    CALCULATE(COUNTROWS(job_offers), job_offers[work_mode] <> "unknown"),
    COUNTROWS(job_offers),
    0
)

// Średni Data Completeness Score
Avg Data Completeness =
AVERAGE(job_offers[Data Completeness Score])

// Ostatni scraping
Last Scrape Time =
MAX(job_offers[scraped_at])

// Freshness (godziny od ostatniego scrapowania)
Data Freshness Hours =
DATEDIFF(MAX(job_offers[scraped_at]), NOW(), HOUR)

// Freshness status
Data Freshness Status =
VAR _hours = [Data Freshness Hours]
RETURN
    SWITCH(
        TRUE(),
        _hours <= 6,  "🟢 Świeże",
        _hours <= 24, "🟡 Do odświeżenia",
        "🔴 Nieaktualne"
    )

// Scrape success rate
Scrape Success Rate =
DIVIDE(
    CALCULATE(COUNTROWS(scrape_log), scrape_log[status] = "success"),
    COUNTROWS(scrape_log),
    0
)

// Avg scrape duration (seconds)
Avg Scrape Duration =
AVERAGE(scrape_log[duration_seconds])

// Total errors
Total Scrape Errors =
SUM(scrape_log[errors])
```

### 8.9 Measures — dynamiczne tytuły i KPI Cards

```dax
// ═══════════════════════════════════════
// FOLDER: 🏷️ Dynamic Labels
// ═══════════════════════════════════════

// Dynamiczny tytuł raportu
Report Title =
VAR _sources = CONCATENATEX(VALUES(dim_Source[SourceName]), dim_Source[SourceName], ", ")
VAR _cities = IF(
    ISFILTERED(job_offers[location_city]),
    " | " & CONCATENATEX(VALUES(job_offers[location_city]), job_offers[location_city], ", "),
    ""
)
RETURN
    "Rynek pracy — " & _sources & _cities

// KPI z warunkowym formatowaniem
Salary KPI Card =
VAR _avg = [Avg Salary Midpoint]
VAR _change = [Salary MoM Change]
VAR _arrow = IF(_change > 0, " ↑", IF(_change < 0, " ↓", ""))
RETURN
    FORMAT(_avg, "#,##0 PLN") & _arrow

// Tooltip: pełne info o filtrach
Active Filters Tooltip =
VAR _src = IF(ISFILTERED(job_offers[source]),
    "Źródła: " & CONCATENATEX(VALUES(job_offers[source]), job_offers[source], ", "),
    "Wszystkie źródła")
VAR _city = IF(ISFILTERED(job_offers[location_city]),
    " | Miasta: " & CONCATENATEX(VALUES(job_offers[location_city]), job_offers[location_city], ", "),
    "")
VAR _sen = IF(ISFILTERED(job_offers[seniority]),
    " | Poziomy: " & CONCATENATEX(VALUES(job_offers[seniority]), job_offers[seniority], ", "),
    "")
RETURN
    _src & _city & _sen
```

### 8.10 Measures — zaawansowane kalkulacje analityczne

```dax
// ═══════════════════════════════════════
// FOLDER: 🧮 Advanced Analytics
// ═══════════════════════════════════════

// Salary Percentile Rank per oferta (w kontekście filtrów)
Salary Percentile Rank =
VAR _currentSalary = SELECTEDVALUE(job_offers[Salary Midpoint])
VAR _allSalaries =
    CALCULATETABLE(
        VALUES(job_offers[Salary Midpoint]),
        ALL(job_offers),
        NOT ISBLANK(job_offers[Salary Midpoint])
    )
VAR _below = COUNTROWS(FILTER(_allSalaries, job_offers[Salary Midpoint] <= _currentSalary))
VAR _total = COUNTROWS(_allSalaries)
RETURN
    DIVIDE(_below, _total, 0)

// Market Heatmap Score (miasto × seniority)
// Wysoki = dużo ofert + dobre wynagrodzenia
Market Heatmap Score =
VAR _offerScore = DIVIDE(
    [Total Offers],
    CALCULATE([Total Offers], ALL(job_offers[location_city], job_offers[seniority])),
    0
) * 50
VAR _salaryScore = DIVIDE(
    [Avg Salary Midpoint],
    CALCULATE([Avg Salary Midpoint], ALL(job_offers[location_city], job_offers[seniority])),
    0
) * 50
RETURN
    _offerScore + _salaryScore

// Salary Competitiveness Index
// 100 = firma płaci średnio rynkowo, >100 = powyżej rynku
Salary Competitiveness Index =
VAR _companySalary = [Avg Salary Midpoint]
VAR _marketSalary = CALCULATE([Avg Salary Midpoint], ALL(job_offers[company_name]))
RETURN
    IF(
        NOT ISBLANK(_companySalary) && NOT ISBLANK(_marketSalary) && _marketSalary > 0,
        DIVIDE(_companySalary, _marketSalary) * 100,
        BLANK()
    )

// Offer Velocity — tempo pojawiania się nowych ofert (per dzień)
Offer Velocity =
VAR _period = DATEDIFF(MIN(dim_Date[Date]), MAX(dim_Date[Date]), DAY)
RETURN
    IF(_period > 0, DIVIDE([Total Offers], _period), BLANK())

// Churn Rate — % ofert które wygasły w okresie
Offer Churn Rate =
DIVIDE(
    [Inactive Offers],
    [Total Offers],
    0
)

// Diversity Index (Shannon Entropy) — jak zróżnicowany jest rynek per miasto
Location Diversity Index =
VAR _total = [Total Offers]
VAR _shares =
    ADDCOLUMNS(
        FILTER(
            VALUES(job_offers[location_city]),
            CALCULATE(COUNTROWS(job_offers)) > 0
        ),
        "@p", DIVIDE(CALCULATE(COUNTROWS(job_offers)), _total, 0)
    )
RETURN
    -SUMX(
        _shares,
        IF([@p] > 0, [@p] * LOG([@p], 2), 0)
    )
```

---

## 9. Hierarchie

### 9.1 Hierarchia lokalizacji

```
Location Hierarchy
├── location_region    (województwo)
│   └── location_city  (miasto)
```

Tworzenie: PPM na `location_region` → "Create Hierarchy" → dodaj `location_city`

### 9.2 Hierarchia czasu (Date)

```
Date Hierarchy
├── Year
│   ├── Quarter
│   │   ├── Month Name
│   │   │   └── Date
```

### 9.3 Hierarchia seniority

```
Seniority Hierarchy
├── SeniorityGroup   (Junior / Mid / Senior / Management)
│   └── SeniorityName
```

### 9.4 Hierarchia umów

```
Contract Hierarchy
├── ContractGroup    (Etat / Kontrakt / Cywilnoprawna / Staż)
│   └── ContractName
```

---

## 10. Strony raportu

### Strona 1: 📊 Executive Dashboard

**Cel:** Przegląd stanu rynku pracy jednym rzutem oka

| Wizualizacja | Typ | Dane | Measures |
|---|---|---|---|
| Aktywne oferty | KPI Card | — | `[Active Offers]` + `[Offers MoM Change]` |
| Z wynagrodzeniem | KPI Card | — | `[Offers With Salary]` + `[Salary Transparency %]` |
| Firmy | KPI Card | — | `[Unique Companies]` |
| Średnie wynagrodzenie | KPI Card | — | `[Avg Salary Midpoint]` + `[Salary MoM Change]` |
| Oferty wg źródła | Donut Chart | `source` | `[Total Offers]`, `[Source Share %]` |
| Oferty wg trybu pracy | Donut Chart | `work_mode` | `[Total Offers]` |
| Top 15 miast | Bar Chart (horizontal) | `location_city` | `[Total Offers]` |
| Trend dzienny | Line Chart | `dim_Date[Date]` | `[Total Offers]`, `[Offers Rolling 7D Avg]` |
| Freshness | Card | — | `[Data Freshness Status]`, `[Last Scrape Time]` |

**Slicery:** Source, City, Seniority, Work Mode, Date Range

---

### Strona 2: 💰 Salary Intelligence

**Cel:** Głęboka analiza wynagrodzeń

| Wizualizacja | Typ | Dane | Measures |
|---|---|---|---|
| Mediana salary | KPI Card | — | `[Median Salary Midpoint]` |
| Salary band | KPI Card | — | `[Salary P25]` – `[Salary P75]` |
| Box plot salary per seniority | Clustered Bar | `seniority` | `[Salary P10]`, `[Salary P25]`, `[Median]`, `[Salary P75]`, `[Salary P90]` |
| Salary per miasto (Top 10) | Bar Chart | `location_city` | `[Avg Salary Min]`, `[Avg Salary Max]` |
| Salary per tryb pracy | Grouped Bar | `work_mode` | `[Avg Salary Midpoint]` |
| Remote salary premium | Card | — | `[Remote Salary Premium]` |
| Junior vs Senior gap | Card | — | `[Junior Senior Salary Gap]`, `[Senior Junior Multiplier]` |
| Salary bands distribution | Stacked Bar | `Salary Band` | `[Total Offers]` |
| Rozkład salary | Histogram | `Salary Midpoint` (bins) | Count |
| Salary heatmap | Matrix | Rows: `location_city`, Cols: `seniority` | `[Avg Salary Midpoint]` (conditional formatting) |
| Salary trend | Line Chart | `dim_Date[Year-Month]` | `[Avg Salary Midpoint]` |

**Slicery:** Currency, Salary Period, Employment Type, Salary Type (brutto/netto)

---

### Strona 3: 🗺️ Rynek geograficzny

**Cel:** Rozkład geograficzny ofert i wynagrodzeń

| Wizualizacja | Typ | Dane | Measures |
|---|---|---|---|
| Mapa Polski | Filled Map / Shape Map | `location_city` | `[Total Offers]` (bubble size), `[Avg Salary Midpoint]` (color) |
| Top miasta — tabela | Table | `location_city`, `location_region` | `[Total Offers]`, `[Avg Salary Midpoint]`, `[Remote Share %]`, `[Salary Transparency %]` |
| Warszawa share | Card | — | `[Warsaw Share %]` |
| Koncentracja HHI | Gauge | — | `[City Concentration HHI]` |
| Comparison: wybrane miasto vs reszta | KPI Cards (x4) | — | Salary, Offers, Remote %, Seniority Mix |
| Oferty per województwo | Bar Chart | `location_region` | `[Total Offers]` |
| Work mode per miasto | Stacked Bar (100%) | `location_city` | `[Total Offers]` by `work_mode` |

**Slicery:** Region, City, Work Mode

---

### Strona 4: 🏢 Employer Analytics

**Cel:** Analiza pracodawców — kto rekrutuje, kto płaci najlepiej

| Wizualizacja | Typ | Dane | Measures |
|---|---|---|---|
| Top 20 firm | Table | `company_name` | `[Total Offers]`, `[Avg Salary Midpoint]`, `[Salary Competitiveness Index]`, `[Company Remote Availability]` |
| Avg offers per company | Card | — | `[Avg Offers Per Company]` |
| Top10 share | Card | — | `[Top10 Companies Share %]` |
| Large employers | Card | — | `[Large Employers Count]` |
| Company salary ranking | Bar Chart | `company_name` (Top 20 by salary) | `[Avg Salary Midpoint]` |
| Firmy per miasto | Matrix | Rows: `company_name`, Cols: `location_city` | `[Total Offers]` |
| Company × Seniority | Matrix | Rows: `company_name`, Cols: `seniority` | `[Total Offers]` |

**Slicery:** City, Source, Seniority, Min Offers (parametr)

---

### Strona 5: 📈 Trendy i dynamika rynku

**Cel:** Analiza temporalna — jak zmienia się rynek w czasie

| Wizualizacja | Typ | Dane | Measures |
|---|---|---|---|
| Offer velocity | KPI Card | — | `[Offer Velocity]` ofert/dzień |
| MoM change | KPI Card | — | `[Offers MoM Change]` z ikoną trendu |
| Dzienny napływ ofert | Area Chart | `dim_Date[Date]` | `[Total Offers]`, `[Offers Rolling 7D Avg]`, `[Offers Rolling 30D Avg]` |
| Running total | Line Chart | `dim_Date[Date]` | `[Offers Running Total]` |
| Churn rate trend | Line Chart | `dim_Date[Date]` | `[Offer Churn Rate]` |
| Sezonowość | Column Chart | `dim_Date[Day Name]` | `[Total Offers]` (avg per dzień tygodnia) |
| Salary trend | Line + Column | `dim_Date[Year-Month]` | `[Avg Salary Midpoint]` (line), `[Total Offers]` (column) |
| MoM comparison table | Matrix | Rows: `source`, Cols: current vs previous month | `[Total Offers]`, `[Offers MoM Change]` |

**Slicery:** Date Range, Source

---

### Strona 6: 🔧 Data Quality & Pipeline Monitoring

**Cel:** Monitoring scrape pipeline, jakość danych, alerty

| Wizualizacja | Typ | Dane | Measures |
|---|---|---|---|
| Freshness | Card | — | `[Data Freshness Status]`, `[Data Freshness Hours]` |
| Scrape success rate | Gauge (0–100%) | — | `[Scrape Success Rate]` |
| Avg duration | Card | — | `[Avg Scrape Duration]` |
| Total errors | Card | — | `[Total Scrape Errors]` |
| Completeness radar | Radar / Bar | fields | `[Completeness Company %]`, `[City %]`, `[Salary %]`, etc. |
| Scrape log | Table | `scrape_log` | Wszystkie kolumny, sorted by date DESC |
| Avg data quality per source | Clustered Bar | `source` | `[Avg Data Quality]` |
| Data quality trend | Line | `dim_Date[Date]` | `[Avg Data Completeness]` |
| Pipeline timeline | Gantt-like / Table | `scrape_log` | started_at, finished_at, duration, status |
| Missing data heatmap | Matrix | Rows: `source`, Cols: fields | Completeness % (conditional formatting red→green) |

---

## 11. Row-Level Security (RLS)

### Scenariusz: ograniczenie widoczności per źródło

Jeśli raport jest współdzielony z partnerami z portali pracy:

```dax
// Rola: PracaPL_Only
[source] = "pracapl"

// Rola: IT_Portals
[source] IN {"justjoinit", "rocketjobs", "nofluffjobs"}

// Rola: All_Data (admin)
// Brak filtra — pełen dostęp
```

Konfiguracja: `Modeling > Manage Roles > New Role`

---

## 12. Optymalizacja wydajności

### 12.1 Model VertiPaq

| Optymalizacja | Opis |
|---|---|
| **Usunięcie `description_text`** | Kolumna LONGTEXT — ogromna kardynalność, nie używana w wizualizacjach |
| **Usunięcie `source_url`** | Wysokie unique — nie potrzebne w modelu (ew. drillthrough) |
| **Usunięcie `company_logo_url`** | Nie używane w VertiPaq |
| **Integer zamiast text seniority/work_mode** | Klucze numeryczne w dim tables → mniejszy rozmiar |
| **Summarize by: None** | Na kolumnach FK (`source`, `seniority`, `work_mode`) — zapobiegaj implicit measures |
| **Data types** | `salary_min/max` → Fixed Decimal; `is_active` → True/False |

### 12.2 DAX Best Practices

| Praktyka | Przykład |
|---|---|
| **DIVIDE() zamiast `/`** | Unikaj division by zero |
| **Zmienne (VAR)** | Oblicz raz, użyj wielokrotnie |
| **CALCULATE + FILTER** | Preferuj proste predykaty nad FILTER na dużych tabelach |
| **ISBLANK() nad = BLANK()** | Szybsze porównanie |
| **DISTINCTCOUNT** | Zamiast `COUNTROWS(DISTINCT(...))` |
| **TREATAS nad FILTER+ALL** | Dla virtual relationships |
| **Unikaj EARLIER** | Użyj VAR + CALCULATE |

### 12.3 Incremental Refresh

Konfiguracja na tabeli `job_offers`:

| Parametr | Wartość |
|---|---|
| Archive starting | `3 years ago` |
| Incrementally refresh starting | `7 days ago` |
| Detect data changes (column) | `scraped_at` |
| Only refresh complete days | ☑️ No |

Wymagane parametry M: `RangeStart` i `RangeEnd` (type `datetime`)

```m
// Dodać do query job_offers:
FilteredByRange = Table.SelectRows(TypedColumns, each
    [scraped_at] >= RangeStart and [scraped_at] < RangeEnd
)
```

---

## 13. Deployment & Refresh

### 13.1 Power BI Service Setup

```
1. Publish .pbix → Power BI Service (workspace: "jobDB Analytics")
2. Dataset Settings:
   - Gateway: Personal / On-premises data gateway
   - Data source credentials: MySQL (Basic auth)
   - Scheduled refresh: co 6h (00:00, 06:00, 12:00, 18:00)
3. Dashboard: Pin visuals from report pages
4. Alerts: Set data-driven alerts on KPI cards
```

### 13.2 Gateway Configuration

| Pole | Wartość |
|------|---------|
| Data Source Type | MySQL |
| Server | `localhost:3306` |
| Database | `jobdb` |
| Authentication | Basic |
| Privacy Level | Organizational |

### 13.3 Naming Conventions

| Element | Convention | Przykład |
|---------|-----------|---------|
| Measures | PascalCase, verby | `Total Offers`, `Avg Salary Midpoint` |
| Calculated Columns | PascalCase, nouns | `Salary Band`, `Offer Lifespan Days` |
| Parameters | prefix `p` | `pDBServer`, `pDaysBack` |
| Dimension Tables | prefix `dim_` | `dim_Source`, `dim_Date` |
| Measure Folders | Emoji + topic | `📊 KPI`, `💰 Wynagrodzenia` |
| Report Pages | Emoji + title | `📊 Executive Dashboard` |

---

## Appendix A: Mapa kolumn źródłowych

| Kolumna MySQL | Typ MySQL | Użycie w Power BI | Tabela docelowa |
|---|---|---|---|
| `id` | VARCHAR(64) | PK, JOIN key | `job_offers` |
| `source` | VARCHAR(50) | FK → `dim_Source` | `job_offers` |
| `title` | VARCHAR(500) | Wyświetlanie, search | `job_offers` |
| `company_name` | VARCHAR(500) | Wymiar, grouping | `job_offers` |
| `location_city` | VARCHAR(255) | Wymiar, geograficzna | `job_offers` → `dim_Location` |
| `location_region` | VARCHAR(255) | Wymiar hierarchy | `job_offers` → `dim_Location` |
| `work_mode` | VARCHAR(50) | FK → `dim_WorkMode` | `job_offers` |
| `seniority` | VARCHAR(50) | FK → `dim_Seniority` | `job_offers` |
| `employment_type` | VARCHAR(100) | Normalizacja → `employment_category` | `job_offers` |
| `salary_min` | DOUBLE | Measures, calculated cols | `job_offers` |
| `salary_max` | DOUBLE | Measures, calculated cols | `job_offers` |
| `salary_currency` | VARCHAR(10) | Slicer, filtr | `job_offers` |
| `salary_period` | VARCHAR(20) | Normalizacja → monthly | `job_offers` |
| `salary_type` | VARCHAR(20) | Slicer (brutto/netto) | `job_offers` |
| `technologies` | JSON | Parsowane w PQ | `job_offers` |
| `published_at` | DATETIME | Inactive relationship → `dim_Date` | `job_offers` |
| `first_seen_at` | DATETIME | Lifespan calc | `job_offers` |
| `last_seen_at` | DATETIME | Lifespan calc | `job_offers` |
| `is_active` | BOOLEAN | Filtr, measures | `job_offers` |
| `scraped_at` | DATETIME | Active relationship → `dim_Date` | `job_offers` |

## Appendix B: Pełna lista Measures

| # | Measure | Folder | Format | Opis |
|---|---------|--------|--------|------|
| 1 | `Total Offers` | 📊 KPI | `#,##0` | Łączna liczba ofert |
| 2 | `Active Offers` | 📊 KPI | `#,##0` | Aktywne oferty |
| 3 | `Inactive Offers` | 📊 KPI | `#,##0` | Wygasłe oferty |
| 4 | `Offers With Salary` | 📊 KPI | `#,##0` | Oferty z wynagrodzeniem |
| 5 | `Salary Transparency %` | 📊 KPI | `0.0%` | % ofert z salary |
| 6 | `Unique Companies` | 📊 KPI | `#,##0` | Unikalne firmy |
| 7 | `Unique Cities` | 📊 KPI | `#,##0` | Unikalne miasta |
| 8 | `Unique Sources` | 📊 KPI | `#,##0` | Źródła danych |
| 9 | `Avg Salary Min` | 💰 Wynagrodzenia | `#,##0 PLN` | Średnia min salary |
| 10 | `Avg Salary Max` | 💰 Wynagrodzenia | `#,##0 PLN` | Średnia max salary |
| 11 | `Avg Salary Midpoint` | 💰 Wynagrodzenia | `#,##0 PLN` | Średni midpoint |
| 12 | `Median Salary Midpoint` | 💰 Wynagrodzenia | `#,##0 PLN` | Mediana midpoint |
| 13 | `Salary P10` | 💰 Wynagrodzenia | `#,##0 PLN` | 10. percentyl |
| 14 | `Salary P25` | 💰 Wynagrodzenia | `#,##0 PLN` | 25. percentyl |
| 15 | `Salary P75` | 💰 Wynagrodzenia | `#,##0 PLN` | 75. percentyl |
| 16 | `Salary P90` | 💰 Wynagrodzenia | `#,##0 PLN` | 90. percentyl |
| 17 | `Avg Salary Spread` | 💰 Wynagrodzenia | `#,##0 PLN` | Średni rozrzut widełek |
| 18 | `Avg Monthly Salary PLN` | 💰 Wynagrodzenia | `#,##0 PLN` | Znormalizowana miesięczna PLN |
| 19 | `Median Monthly Salary PLN` | 💰 Wynagrodzenia | `#,##0 PLN` | Mediana monthly PLN |
| 20 | `Salary Display` | 💰 Wynagrodzenia | Text | Sformatowany tekst |
| 21 | `Offers Previous Month` | 📈 Trendy | `#,##0` | Oferty miesiąc temu |
| 22 | `Offers MoM Change` | 📈 Trendy | `+0.0%;-0.0%` | Zmiana MoM |
| 23 | `Offers MoM Trend Icon` | 📈 Trendy | Text | Ikona trendu |
| 24 | `Avg Salary Previous Month` | 📈 Trendy | `#,##0 PLN` | Salary miesiąc temu |
| 25 | `Salary MoM Change` | 📈 Trendy | `+0.0%;-0.0%` | Zmiana salary MoM |
| 26 | `New Offers Today` | 📈 Trendy | `#,##0` | Nowe dzisiaj |
| 27 | `New Offers This Week` | 📈 Trendy | `#,##0` | Nowe w tym tygodniu |
| 28 | `Offers Rolling 7D Avg` | 📈 Trendy | `#,##0.0` | Średnia krocząca 7 dni |
| 29 | `Offers Rolling 30D Avg` | 📈 Trendy | `#,##0.0` | Średnia krocząca 30 dni |
| 30 | `Offers Running Total` | 📈 Trendy | `#,##0` | Suma narastająca |
| 31 | `Offers YTD` | 📈 Trendy | `#,##0` | Year to Date |
| 32 | `Source Share %` | 🌐 Źródła | `0.0%` | Udział źródła |
| 33 | `Source Salary Transparency %` | 🌐 Źródła | `0.0%` | Transparentność per źródło |
| 34 | `Best Salary Source` | 🌐 Źródła | Text | Najlepsze źródło dla salary |
| 35 | `Avg Data Quality` | 🌐 Źródła | `0.0%` | Średnia jakość danych |
| 36 | `Remote Share %` | 🗺️ Lokalizacja | `0.0%` | % ofert remote |
| 37 | `Remote Salary Premium` | 🗺️ Lokalizacja | `+0.0%;-0.0%` | Premium za remote |
| 38 | `Top City` | 🗺️ Lokalizacja | Text | Dominujące miasto |
| 39 | `City Concentration HHI` | 🗺️ Lokalizacja | `0.000` | Indeks Herfindahla |
| 40 | `Warsaw Share %` | 🗺️ Lokalizacja | `0.0%` | Udział Warszawy |
| 41 | `Avg Offers Per Company` | 🏢 Firmy | `#,##0.0` | Oferty per firma |
| 42 | `Large Employers Count` | 🏢 Firmy | `#,##0` | Duzi pracodawcy |
| 43 | `Top10 Companies Share %` | 🏢 Firmy | `0.0%` | Udział Top 10 firm |
| 44 | `Company Remote Availability` | 🏢 Firmy | Text | Czy firma ma remote |
| 45 | `Junior Senior Salary Gap` | 🎯 Seniority | `#,##0 PLN` | Luka Junior↔Senior |
| 46 | `Senior Junior Multiplier` | 🎯 Seniority | `0.0x` | Mnożnik Senior/Junior |
| 47 | `Seniority Share %` | 🎯 Seniority | `0.0%` | Udział poziomu |
| 48 | `Market Demand Index` | 🎯 Seniority | `0.00` | Junior/Senior ratio |
| 49 | `Completeness Company %` | 🔧 Quality | `0.0%` | Kompletność: firma |
| 50 | `Completeness City %` | 🔧 Quality | `0.0%` | Kompletność: miasto |
| 51 | `Completeness Salary %` | 🔧 Quality | `0.0%` | Kompletność: salary |
| 52 | `Completeness Seniority %` | 🔧 Quality | `0.0%` | Kompletność: seniority |
| 53 | `Completeness WorkMode %` | 🔧 Quality | `0.0%` | Kompletność: tryb pracy |
| 54 | `Avg Data Completeness` | 🔧 Quality | `0.0%` | Sredni score jakości |
| 55 | `Last Scrape Time` | 🔧 Quality | `datetime` | Ostatni scrape |
| 56 | `Data Freshness Hours` | 🔧 Quality | `#,##0` | Godziny od scrape |
| 57 | `Data Freshness Status` | 🔧 Quality | Text | Status freshness |
| 58 | `Scrape Success Rate` | 🔧 Quality | `0.0%` | % sukces scrapowania |
| 59 | `Avg Scrape Duration` | 🔧 Quality | `#,##0.0 s` | Średni czas scrape |
| 60 | `Total Scrape Errors` | 🔧 Quality | `#,##0` | Suma błędów |
| 61 | `Report Title` | 🏷️ Labels | Text | Dynamiczny tytuł |
| 62 | `Salary KPI Card` | 🏷️ Labels | Text | Salary + trend |
| 63 | `Active Filters Tooltip` | 🏷️ Labels | Text | Podsumowanie filtrów |
| 64 | `Salary Percentile Rank` | 🧮 Advanced | `0.0%` | Percentyl salary |
| 65 | `Market Heatmap Score` | 🧮 Advanced | `0.0` | Score miasto×seniority |
| 66 | `Salary Competitiveness Index` | 🧮 Advanced | `0.0` | Indeks konkurencyjności |
| 67 | `Offer Velocity` | 🧮 Advanced | `#,##0.0` | Oferty/dzień |
| 68 | `Offer Churn Rate` | 🧮 Advanced | `0.0%` | Wskaźnik wygasania |
| 69 | `Location Diversity Index` | 🧮 Advanced | `0.00` | Shannon Entropy miast |

---

## Appendix C: Conditional Formatting Rules

### Salary Heatmap (Matrix)

| Warunek | Kolor tła |
|---------|-----------|
| `Avg Salary Midpoint` < P25 | `#FFF2CC` (jasno żółty) |
| `Avg Salary Midpoint` P25–P75 | `#D9EAD3` (jasno zielony) |
| `Avg Salary Midpoint` > P75 | `#274E13` (ciemno zielony, biały tekst) |

### Data Quality

| Warunek | Kolor |
|---------|-------|
| Completeness ≥ 85% | 🟢 `#00B050` |
| Completeness 50–85% | 🟡 `#FFC000` |
| Completeness < 50% | 🔴 `#FF0000` |

### MoM Change

| Warunek | Kolor ikony |
|---------|-------------|
| Change > +5% | 🟢 `#00B050` |
| Change -5% → +5% | ⚪ `#808080` |
| Change < -5% | 🔴 `#FF0000` |

---

## Appendix D: Bookmarks & Navigation

### Sugerowana nawigacja

```
📊 Executive Dashboard  ←→  💰 Salary Intelligence
                         ←→  🗺️ Rynek geograficzny
                         ←→  🏢 Employer Analytics
                         ←→  📈 Trendy i dynamika
                         ←→  🔧 Data Quality
```

### Bookmarks

| Bookmark | Strona | Filtry | Opis |
|----------|--------|--------|------|
| `IT Market Overview` | Executive | source IN {justjoinit, rocketjobs, nofluffjobs} | Tylko rynek IT |
| `Warsaw Focus` | Geograficzny | city = Warszawa | Analiza Warszawa |
| `Salary Deep Dive` | Salary | is_active = true, has_salary = true | Tylko aktywne z salary |
| `Data Quality Alert` | Quality | Completeness < 50% | Problematyczne źródła |
| `Remote Work Trend` | Trendy | work_mode = remote | Trend pracy zdalnej |

---

## Appendix E: Słownik pojęć biznesowych

| Termin | Definicja |
|--------|-----------|
| **Aktywna oferta** | Oferta widoczna na portalu przy ostatnim scrapowaniu (`is_active = TRUE`) |
| **Salary Midpoint** | Środek widełek wynagrodzenia: `(salary_min + salary_max) / 2` |
| **Salary Transparency** | % ofert z podanym wynagrodzeniem vs łączna liczba ofert |
| **Scrape** | Jednorazowe pobranie ofert ze źródła przez pipeline Python |
| **Source** | Portal z ofertami pracy (praca.pl, pracuj.pl, justjoin.it, rocketjobs.pl, nofluffjobs.com, jooble.org) |
| **Seniority** | Poziom doświadczenia wymagany w ofercie (intern→senior→manager) |
| **Work Mode** | Tryb pracy: remote (zdalny), hybrid, onsite (stacjonarny) |
| **Employment Category** | Znormalizowany typ umowy (UoP, B2B, UZ, mieszane) |
| **Offer Lifespan** | Czas między `first_seen_at` a `last_seen_at` — jak długo oferta była aktywna |
| **Churn Rate** | % ofert które zostały oznaczone jako nieaktywne w danym okresie |
| **Offer Velocity** | Tempo napływu nowych ofert wyrażone liczbą ofert na dzień |
| **HHI (Herfindahl Index)** | Miara koncentracji rynku — im bliżej 1, tym bardziej zdominowany przez jedno miasto |
| **Salary Competitiveness** | Indeks 100 = rynkowa średnia; >100 = firma płaci powyżej rynku |
| **Remote Premium** | Różnica % w wynagrodzeniach ofert remote vs onsite |
| **Data Completeness Score** | 0–1 score ile z 7 kluczowych pól jest wypełnionych w ofercie |
| **Shannon Diversity Index** | Miara zróżnicowania rozkładu ofert po miastach (entropia) |
