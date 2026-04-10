---
description: "Run a quick data credibility check on scraped job offers from praca.pl"
mode: "agent"
agent: "data-verifier"
---

Run a full data credibility verification for the praca.pl scraper:

1. First run `python scripts/verify_credibility.py` to get the automated report
2. Query the database for 5 sample offers that have salary data
3. Open https://www.praca.pl/oferty-pracy.html and compare the first few offers with what's in our database
4. Check 2-3 specific offer URLs from the database to verify they actually exist and data matches
5. Report your findings with a credibility score out of 10
