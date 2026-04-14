# Power BI — jobDB Semantic Model

## Pliki

| Plik | Opis |
|------|------|
| `model.bim` | Tabular Model Definition (JSON) — pełny model semantyczny |
| `../docs/POWERBI_DOCUMENTATION.md` | Dokumentacja measures, calculated columns, raportów |

## Co to jest `model.bim`?

Plik w formacie **Tabular Object Model (TOM)** — standard Microsoft do definiowania modeli Power BI / Analysis Services jako kod. Można go wersjonować w git, reviewować w PR-ach i deployować automatycznie.

## Jak użyć

### Opcja 1: Tabular Editor (zalecane)

1. Pobierz [Tabular Editor 2](https://github.com/TabularEditor/TabularEditor/releases) (free) lub [Tabular Editor 3](https://tabulareditor.com/) (paid)
2. `File > Open > Model from File > model.bim`
3. Edytuj measures, relacje, calculated columns w GUI
4. Deploy do Power BI Service: `Model > Deploy`

### Opcja 2: Import do Power BI Desktop

1. Otwórz Tabular Editor
2. Załaduj `model.bim`
3. `File > Save to Folder` → export jako folder structure
4. Użyj `pbi-tools` do konwersji na `.pbix`

### Opcja 3: XMLA Endpoint (Power BI Premium)

```powershell
# Deploy via PowerShell (wymaga Az.AnalysisServices)
Invoke-ASCmd -Server "powerbi://api.powerbi.com/v1.0/myorg/WorkspaceName" `
             -InputFile "model.bim"
```

### Opcja 4: CI/CD Pipeline

```yaml
# GitHub Actions / Azure DevOps
- name: Deploy to Power BI
  run: |
    TabularEditor.exe model.bim -D "powerbi://api.powerbi.com/v1.0/myorg/Workspace" "jobDB"
```

## Zawartość modelu

- **4 tabele źródłowe**: `job_offers`, `scrape_log`, `job_snapshots`, `daily_stats`
- **5 tabel wymiarów**: `dim_Date`, `dim_Source`, `dim_Seniority`, `dim_WorkMode`, `dim_Contract`
- **12 relacji** (w tym 1 inactive: published_date)
- **12 calculated columns** (salary bands, lifespan, data quality)
- **69 measures** w 8 folderach
- **4 hierarchie** (Date, Location, Seniority, Contract)
- **3 role RLS** (PracaPL_Only, IT_Portals, All_Data)
- **3 parametry M** (pDBServer, pDBName, pDaysBack)
- Power Query (M) transformacje z normalizacją employment_type i parsowaniem JSON

## Wymagania

- MySQL 8+ z bazą `jobdb` (patrz `config/settings.py`)
- MySQL ODBC Connector lub MySQL for Power BI
- Power BI Desktop (luty 2023+) lub Tabular Editor 2/3
