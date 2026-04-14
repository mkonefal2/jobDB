// ============================================================================
// jobDB — Tabular Editor 2 C# Script
// Dziala na istniejacych tabelach z Power BI Desktop (MySQL import)
//
// INSTRUKCJA:
// 1. W Power BI Desktop: Get Data > MySQL > zaladuj tabele job_offers
// 2. External Tools > Tabular Editor
// 3. Advanced Scripting > wklej > Run (F5)
// 4. Ctrl+S aby zapisac zmiany do Power BI Desktop
// ============================================================================

// ── Walidacja ───────────────────────────────────────────────────────────────

if (Model == null) { Error("Model is null"); return; }

// Safe helpers (try-catch indexer — jedyny sposob ktory dziala w TE2)
Func<string, bool> TableExists = (n) => { try { return Model.Tables[n] != null; } catch { return false; } };
Func<string, string, bool> ColExists = (t, c) => { try { return Model.Tables[t].Columns[c] != null; } catch { return false; } };
Func<string, string, bool> MeasExists = (t, m) => { try { return Model.Tables[t].Measures[m] != null; } catch { return false; } };

// ── Wykryj nazwe tabeli (moze miec prefix "jobdb ") ─────────────────────────
string JO = "";
if (TableExists("job_offers")) { JO = "job_offers"; }
else if (TableExists("jobdb job_offers")) { JO = "jobdb job_offers"; }
else if (TableExists("jobdb.job_offers")) { JO = "jobdb.job_offers"; }
else if (TableExists("jobdb_job_offers")) { JO = "jobdb_job_offers"; }

if (JO == "") { Error("Nie znaleziono tabeli job_offers. Zaladuj ja w Power BI Desktop."); return; }

// DAX nazwa tabeli (ze single quotes jesli ma spacje)
string DJ = JO.Contains(" ") ? "'" + JO + "'" : JO;

Info("Tabela znaleziona: " + JO + " (DAX: " + DJ + ")");

// ── Helpers ─────────────────────────────────────────────────────────────────

Action<string, string, string, string> AddCol = (name, expression, format, desc) => {
    try {
        if (ColExists(JO, name)) return;
        var c = Model.Tables[JO].AddCalculatedColumn(name);
        if (c != null) {
            c.Expression = expression;
            if (!string.IsNullOrEmpty(format)) c.FormatString = format;
            c.SummarizeBy = AggregateFunction.None;
        }
    } catch (Exception ex) { Warning("Col '" + name + "': " + ex.Message); }
};

Action<string, string, string, string> AddMeas = (name, expression, folder, format) => {
    try {
        if (MeasExists(JO, name)) {
            var existing = Model.Tables[JO].Measures[name];
            existing.Expression = expression;
            if (!string.IsNullOrEmpty(folder)) existing.DisplayFolder = folder;
            if (!string.IsNullOrEmpty(format)) existing.FormatString = format;
        } else {
            var m = Model.Tables[JO].AddMeasure(name);
            m.Expression = expression;
            if (!string.IsNullOrEmpty(folder)) m.DisplayFolder = folder;
            if (!string.IsNullOrEmpty(format)) m.FormatString = format;
        }
    } catch (Exception ex) { Warning("Meas '" + name + "': " + ex.Message); }
};

// ═════════════════════════════════════════════════════════════════════════════
// KROK 1: CALCULATED COLUMNS
// ═════════════════════════════════════════════════════════════════════════════

Info("Krok 1/3: Calculated columns...");

AddCol("Salary Midpoint",
    "IF( " + DJ + "[salary_min] > 0 && " + DJ + "[salary_max] > 0, (" + DJ + "[salary_min] + " + DJ + "[salary_max]) / 2, BLANK() )",
    "#,##0", "");

AddCol("Salary Spread",
    "IF( " + DJ + "[salary_min] > 0 && " + DJ + "[salary_max] > 0, " + DJ + "[salary_max] - " + DJ + "[salary_min], BLANK() )",
    "#,##0", "");

AddCol("Salary Spread Pct",
    "IF( " + DJ + "[salary_min] > 0, DIVIDE( " + DJ + "[salary_max] - " + DJ + "[salary_min], " + DJ + "[salary_min], 0 ), BLANK() )",
    "0.0%", "");

AddCol("Salary Monthly Normalized",
    "VAR _min = " + DJ + "[salary_min] " +
    "VAR _max = " + DJ + "[salary_max] " +
    "VAR _mid = DIVIDE(_min + _max, 2, BLANK()) " +
    "VAR _period = " + DJ + "[salary_period] " +
    "RETURN SWITCH( _period, \"month\", _mid, \"hour\", _mid * 168, \"day\", _mid * 21, \"year\", DIVIDE(_mid, 12), BLANK() )",
    "#,##0", "");

AddCol("Salary Band",
    "VAR _m = " + DJ + "[Salary Monthly Normalized] " +
    "RETURN SWITCH( TRUE(), ISBLANK(_m), \"Brak danych\", " +
    "_m < 5000, \"< 5 000 PLN\", " +
    "_m >= 5000 && _m < 8000, \"5 000 - 7 999\", " +
    "_m >= 8000 && _m < 12000, \"8 000 - 11 999\", " +
    "_m >= 12000 && _m < 16000, \"12 000 - 15 999\", " +
    "_m >= 16000 && _m < 22000, \"16 000 - 21 999\", " +
    "_m >= 22000 && _m < 30000, \"22 000 - 29 999\", " +
    "_m >= 30000, \"30 000+ PLN\", \"Brak danych\" )",
    "", "");

AddCol("Salary Band Order",
    "VAR _m = " + DJ + "[Salary Monthly Normalized] " +
    "RETURN SWITCH( TRUE(), ISBLANK(_m), 99, _m < 5000, 1, _m < 8000, 2, _m < 12000, 3, _m < 16000, 4, _m < 22000, 5, _m < 30000, 6, _m >= 30000, 7, 99 )",
    "", "");

// Sort Salary Band by Order
try {
    if (ColExists(JO, "Salary Band") && ColExists(JO, "Salary Band Order")) {
        Model.Tables[JO].Columns["Salary Band"].SortByColumn = Model.Tables[JO].Columns["Salary Band Order"];
        Model.Tables[JO].Columns["Salary Band Order"].IsHidden = true;
    }
} catch {}

AddCol("Data Completeness Score",
    "VAR _a = IF(NOT ISBLANK(" + DJ + "[company_name]), 1, 0) " +
    "VAR _b = IF(NOT ISBLANK(" + DJ + "[location_city]), 1, 0) " +
    "VAR _c = IF(" + DJ + "[work_mode] <> \"unknown\", 1, 0) " +
    "VAR _d = IF(" + DJ + "[seniority] <> \"unknown\", 1, 0) " +
    "VAR _e = IF(NOT ISBLANK(" + DJ + "[employment_type]), 1, 0) " +
    "VAR _f = IF(NOT ISBLANK(" + DJ + "[salary_min]), 1, 0) " +
    "RETURN DIVIDE(_a + _b + _c + _d + _e + _f, 6, 0)",
    "0.0%", "");

AddCol("Data Quality Label",
    "VAR _s = " + DJ + "[Data Completeness Score] " +
    "RETURN SWITCH( TRUE(), _s >= 0.85, \"Wysoka\", _s >= 0.5, \"Srednia\", TRUE(), \"Niska\" )",
    "", "");

Info("Calculated columns done.");

// ═════════════════════════════════════════════════════════════════════════════
// KROK 2: MEASURES
// ═════════════════════════════════════════════════════════════════════════════

Info("Krok 2/3: Measures...");

// -- KPI --
AddMeas("Total Offers", "COUNTROWS(" + DJ + ")", "KPI", "#,##0");
AddMeas("Active Offers", "CALCULATE( COUNTROWS(" + DJ + "), " + DJ + "[is_active] = TRUE() )", "KPI", "#,##0");
AddMeas("Inactive Offers", "CALCULATE( COUNTROWS(" + DJ + "), " + DJ + "[is_active] = FALSE() )", "KPI", "#,##0");
AddMeas("Offers With Salary", "CALCULATE( COUNTROWS(" + DJ + "), NOT ISBLANK(" + DJ + "[salary_min]), " + DJ + "[salary_min] > 0 )", "KPI", "#,##0");
AddMeas("Salary Transparency Pct", "DIVIDE([Offers With Salary], [Total Offers], 0)", "KPI", "0.0%");
AddMeas("Unique Companies", "DISTINCTCOUNT(" + DJ + "[company_name])", "KPI", "#,##0");
AddMeas("Unique Cities", "DISTINCTCOUNT(" + DJ + "[location_city])", "KPI", "#,##0");
AddMeas("Unique Sources", "DISTINCTCOUNT(" + DJ + "[source])", "KPI", "#,##0");

// -- Wynagrodzenia --
AddMeas("Avg Salary Min", "CALCULATE( AVERAGE(" + DJ + "[salary_min]), NOT ISBLANK(" + DJ + "[salary_min]), " + DJ + "[salary_min] > 0 )", "Wynagrodzenia", "#,##0");
AddMeas("Avg Salary Max", "CALCULATE( AVERAGE(" + DJ + "[salary_max]), NOT ISBLANK(" + DJ + "[salary_max]), " + DJ + "[salary_max] > 0 )", "Wynagrodzenia", "#,##0");
AddMeas("Avg Salary Midpoint", "CALCULATE( AVERAGE(" + DJ + "[Salary Midpoint]), NOT ISBLANK(" + DJ + "[Salary Midpoint]) )", "Wynagrodzenia", "#,##0");
AddMeas("Median Salary Midpoint", "CALCULATE( MEDIAN(" + DJ + "[Salary Midpoint]), NOT ISBLANK(" + DJ + "[Salary Midpoint]) )", "Wynagrodzenia", "#,##0");
AddMeas("Salary P10", "CALCULATE( PERCENTILE.INC(" + DJ + "[Salary Midpoint], 0.10), NOT ISBLANK(" + DJ + "[Salary Midpoint]) )", "Wynagrodzenia", "#,##0");
AddMeas("Salary P25", "CALCULATE( PERCENTILE.INC(" + DJ + "[Salary Midpoint], 0.25), NOT ISBLANK(" + DJ + "[Salary Midpoint]) )", "Wynagrodzenia", "#,##0");
AddMeas("Salary P75", "CALCULATE( PERCENTILE.INC(" + DJ + "[Salary Midpoint], 0.75), NOT ISBLANK(" + DJ + "[Salary Midpoint]) )", "Wynagrodzenia", "#,##0");
AddMeas("Salary P90", "CALCULATE( PERCENTILE.INC(" + DJ + "[Salary Midpoint], 0.90), NOT ISBLANK(" + DJ + "[Salary Midpoint]) )", "Wynagrodzenia", "#,##0");
AddMeas("Avg Salary Spread", "CALCULATE( AVERAGE(" + DJ + "[Salary Spread]), NOT ISBLANK(" + DJ + "[Salary Spread]) )", "Wynagrodzenia", "#,##0");
AddMeas("Avg Monthly Salary", "CALCULATE( AVERAGE(" + DJ + "[Salary Monthly Normalized]), NOT ISBLANK(" + DJ + "[Salary Monthly Normalized]) )", "Wynagrodzenia", "#,##0");
AddMeas("Median Monthly Salary", "CALCULATE( MEDIAN(" + DJ + "[Salary Monthly Normalized]), NOT ISBLANK(" + DJ + "[Salary Monthly Normalized]) )", "Wynagrodzenia", "#,##0");
AddMeas("Salary Display", "VAR _avg = [Avg Salary Midpoint] RETURN IF( NOT ISBLANK(_avg), FORMAT(_avg, \"#,##0\") & \" PLN\", \"Brak danych\" )", "Wynagrodzenia", "");

// -- Trendy (bez dim_Date — uzywa scraped_at) --
AddMeas("New Offers Today", "CALCULATE( COUNTROWS(" + DJ + "), " + DJ + "[scraped_at] >= TODAY() )", "Trendy", "#,##0");
AddMeas("New Offers This Week", "CALCULATE( COUNTROWS(" + DJ + "), " + DJ + "[scraped_at] >= TODAY() - 7 )", "Trendy", "#,##0");
AddMeas("New Offers This Month", "CALCULATE( COUNTROWS(" + DJ + "), MONTH(" + DJ + "[scraped_at]) = MONTH(TODAY()), YEAR(" + DJ + "[scraped_at]) = YEAR(TODAY()) )", "Trendy", "#,##0");

// -- Zrodla --
AddMeas("Source Share Pct", "DIVIDE([Total Offers], CALCULATE([Total Offers], ALL(" + DJ + "[source])), 0)", "Zrodla", "0.0%");
AddMeas("Source Salary Transparency", "DIVIDE( [Offers With Salary], [Total Offers], 0 )", "Zrodla", "0.0%");
AddMeas("Avg Data Quality", "AVERAGE(" + DJ + "[Data Completeness Score])", "Zrodla", "0.0%");

// -- Lokalizacja --
AddMeas("Remote Share Pct", "DIVIDE( CALCULATE(COUNTROWS(" + DJ + "), " + DJ + "[work_mode] = \"remote\"), COUNTROWS(" + DJ + "), 0 )", "Lokalizacja", "0.0%");

AddMeas("Remote Salary Premium",
    "VAR _ra = CALCULATE([Avg Salary Midpoint], " + DJ + "[work_mode] = \"remote\") " +
    "VAR _oa = CALCULATE([Avg Salary Midpoint], " + DJ + "[work_mode] = \"onsite\") " +
    "RETURN IF( NOT ISBLANK(_ra) && NOT ISBLANK(_oa) && _oa > 0, DIVIDE(_ra - _oa, _oa, 0), BLANK() )",
    "Lokalizacja", "+0.0%;-0.0%;0.0%");

AddMeas("Top City",
    "VAR _t = ADDCOLUMNS( VALUES(" + DJ + "[location_city]), \"@cnt\", CALCULATE(COUNTROWS(" + DJ + ")) ) " +
    "RETURN MAXX(TOPN(1, _t, [@cnt], DESC), " + DJ + "[location_city])",
    "Lokalizacja", "");

AddMeas("Warsaw Share Pct", "DIVIDE( CALCULATE(COUNTROWS(" + DJ + "), " + DJ + "[location_city] = \"Warszawa\"), COUNTROWS(" + DJ + "), 0 )", "Lokalizacja", "0.0%");

AddMeas("City Concentration HHI",
    "VAR _total = [Total Offers] " +
    "VAR _shares = ADDCOLUMNS( VALUES(" + DJ + "[location_city]), \"@s\", DIVIDE(CALCULATE(COUNTROWS(" + DJ + ")), _total, 0) ) " +
    "RETURN SUMX(_shares, [@s] ^ 2)",
    "Lokalizacja", "0.000");

// -- Firmy --
AddMeas("Avg Offers Per Company", "DIVIDE([Total Offers], [Unique Companies], 0)", "Firmy", "#,##0.0");

AddMeas("Large Employers Count",
    "CALCULATE( DISTINCTCOUNT(" + DJ + "[company_name]), FILTER( VALUES(" + DJ + "[company_name]), CALCULATE(COUNTROWS(" + DJ + ")) >= 5 ) )",
    "Firmy", "#,##0");

AddMeas("Top10 Companies Share Pct",
    "VAR _top10 = TOPN(10, SUMMARIZE(" + DJ + ", " + DJ + "[company_name]), CALCULATE(COUNTROWS(" + DJ + ")), DESC) " +
    "VAR _cnt = CALCULATE(COUNTROWS(" + DJ + "), TREATAS(_top10, " + DJ + "[company_name])) " +
    "RETURN DIVIDE(_cnt, CALCULATE(COUNTROWS(" + DJ + "), ALL(" + DJ + "[company_name])), 0)",
    "Firmy", "0.0%");

// -- Seniority --
AddMeas("Junior Senior Salary Gap",
    "VAR _j = CALCULATE([Avg Salary Midpoint], " + DJ + "[seniority] = \"junior\") " +
    "VAR _s = CALCULATE([Avg Salary Midpoint], " + DJ + "[seniority] = \"senior\") " +
    "RETURN IF(NOT ISBLANK(_j) && NOT ISBLANK(_s), _s - _j, BLANK())",
    "Seniority", "#,##0");

AddMeas("Senior Junior Multiplier",
    "VAR _j = CALCULATE([Median Salary Midpoint], " + DJ + "[seniority] = \"junior\") " +
    "VAR _s = CALCULATE([Median Salary Midpoint], " + DJ + "[seniority] = \"senior\") " +
    "RETURN IF(NOT ISBLANK(_j) && _j > 0, DIVIDE(_s, _j), BLANK())",
    "Seniority", "0.0x");

AddMeas("Seniority Share Pct", "DIVIDE( COUNTROWS(" + DJ + "), CALCULATE(COUNTROWS(" + DJ + "), ALL(" + DJ + "[seniority])), 0 )", "Seniority", "0.0%");

// -- Data Quality --
AddMeas("Completeness Company Pct", "DIVIDE( CALCULATE(COUNTROWS(" + DJ + "), NOT ISBLANK(" + DJ + "[company_name])), COUNTROWS(" + DJ + "), 0 )", "Data Quality", "0.0%");
AddMeas("Completeness City Pct", "DIVIDE( CALCULATE(COUNTROWS(" + DJ + "), NOT ISBLANK(" + DJ + "[location_city])), COUNTROWS(" + DJ + "), 0 )", "Data Quality", "0.0%");
AddMeas("Completeness Salary Pct", "[Salary Transparency Pct]", "Data Quality", "0.0%");
AddMeas("Completeness Seniority Pct", "DIVIDE( CALCULATE(COUNTROWS(" + DJ + "), " + DJ + "[seniority] <> \"unknown\"), COUNTROWS(" + DJ + "), 0 )", "Data Quality", "0.0%");
AddMeas("Completeness WorkMode Pct", "DIVIDE( CALCULATE(COUNTROWS(" + DJ + "), " + DJ + "[work_mode] <> \"unknown\"), COUNTROWS(" + DJ + "), 0 )", "Data Quality", "0.0%");
AddMeas("Avg Data Completeness", "AVERAGE(" + DJ + "[Data Completeness Score])", "Data Quality", "0.0%");
AddMeas("Last Scrape Time", "MAX(" + DJ + "[scraped_at])", "Data Quality", "yyyy-MM-dd HH:mm");
AddMeas("Data Freshness Hours", "DATEDIFF(MAX(" + DJ + "[scraped_at]), NOW(), HOUR)", "Data Quality", "#,##0");
AddMeas("Data Freshness Status",
    "VAR _h = [Data Freshness Hours] RETURN SWITCH(TRUE(), _h <= 6, \"Swieze\", _h <= 24, \"Do odswiezenia\", \"Nieaktualne\")",
    "Data Quality", "");

// -- Advanced --
AddMeas("Salary Competitiveness Index",
    "VAR _cs = [Avg Salary Midpoint] " +
    "VAR _ms = CALCULATE([Avg Salary Midpoint], ALL(" + DJ + "[company_name])) " +
    "RETURN IF(NOT ISBLANK(_cs) && NOT ISBLANK(_ms) && _ms > 0, DIVIDE(_cs, _ms) * 100, BLANK())",
    "Advanced", "0.0");

AddMeas("Offer Churn Rate", "DIVIDE([Inactive Offers], [Total Offers], 0)", "Advanced", "0.0%");

AddMeas("Location Diversity Index",
    "VAR _total = [Total Offers] " +
    "VAR _sh = ADDCOLUMNS( FILTER(VALUES(" + DJ + "[location_city]), CALCULATE(COUNTROWS(" + DJ + ")) > 0), \"@p\", DIVIDE(CALCULATE(COUNTROWS(" + DJ + ")), _total, 0) ) " +
    "RETURN -SUMX(_sh, IF([@p] > 0, [@p] * LOG([@p], 2), 0))",
    "Advanced", "0.00");

// -- Labels --
AddMeas("Report Title",
    "\"Rynek pracy -- \" & IF(HASONEVALUE(" + DJ + "[source]), VALUES(" + DJ + "[source]), \"Wszystkie zrodla\")",
    "Labels", "");

AddMeas("Active Filters Tooltip",
    "\"Oferty: \" & FORMAT([Total Offers], \"#,##0\") & \" | Aktywne: \" & FORMAT([Active Offers], \"#,##0\")",
    "Labels", "");

Info("Measures done.");

// ═════════════════════════════════════════════════════════════════════════════
// KROK 3: HIERARCHIA (opcjonalnie)
// ═════════════════════════════════════════════════════════════════════════════

Info("Krok 3/3: Hierarchia...");

try {
    Func<string, string, bool> HierExists = (t, h) => { try { return Model.Tables[t].Hierarchies[h] != null; } catch { return false; } };
    if (!HierExists(JO, "Location") && ColExists(JO, "location_region") && ColExists(JO, "location_city")) {
        var locH = Model.Tables[JO].AddHierarchy("Location");
        locH.AddLevel(Model.Tables[JO].Columns["location_region"], "Region");
        locH.AddLevel(Model.Tables[JO].Columns["location_city"], "City");
        Info("Hierarchia Location utworzona");
    }
} catch (Exception ex) { Warning("Hierarchia: " + ex.Message); }

Info("=== GOTOWE! Ctrl+S aby zapisac zmiany do Power BI Desktop ===");
