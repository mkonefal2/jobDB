# jobDB — Dokumentacja

**jobDB** to tracker polskiego rynku pracy w stylu SteamDB. System scrapuje oferty z 5 portali (praca.pl, pracuj.pl, justjoin.it, rocketjobs.pl, nofluffjobs.com), normalizuje dane, przechowuje je w MySQL i wizualizuje w dashboardzie HTML/FastAPI oraz Power BI.

**Deploy:** Railway (Docker + uvicorn) | **Baza:** MySQL (env vars)

## Sekcje

* [Architektura projektu](PROJECT_DESIGN.md)
* [Schemat bazy danych](DATABASE_SCHEMA.md)
* [Power BI — dokumentacja](POWERBI_DOCUMENTATION.md)
* [TODO / Roadmap](TODO.md)
