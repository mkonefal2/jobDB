"""Tests for salary parsing from praca.pl scraper."""

from __future__ import annotations

from src.models.schema import SalaryPeriod
from src.scrapers.pracapl import _parse_salary


class TestParseSalary:
    """Test _parse_salary with various real-world formats."""

    def test_range_with_spaces_pln_brutto(self):
        text = "12 500 - 14 500 zł brutto/mies."
        s_min, s_max, cur, per, s_type = _parse_salary(text)
        assert s_min == 12500
        assert s_max == 14500
        assert cur == "PLN"
        assert per == SalaryPeriod.MONTH
        assert s_type == "brutto"

    def test_single_value(self):
        text = "5 100 zł brutto/mies."
        s_min, s_max, cur, per, s_type = _parse_salary(text)
        assert s_min == 5100
        assert s_max == 5100
        assert cur == "PLN"
        assert per == SalaryPeriod.MONTH
        assert s_type == "brutto"

    def test_hourly_rate(self):
        text = "35 zł brutto/godz."
        s_min, s_max, cur, per, s_type = _parse_salary(text)
        assert s_min == 35
        assert s_max == 35
        assert cur == "PLN"
        assert per == SalaryPeriod.HOUR
        assert s_type == "brutto"

    def test_hourly_range(self):
        text = "30 - 45 zł netto/godz."
        s_min, s_max, cur, per, s_type = _parse_salary(text)
        assert s_min == 30
        assert s_max == 45
        assert cur == "PLN"
        assert per == SalaryPeriod.HOUR
        assert s_type == "netto"

    def test_euro_currency(self):
        text = "3 000 - 5 000 € brutto/mies."
        s_min, s_max, cur, per, s_type = _parse_salary(text)
        assert s_min == 3000
        assert s_max == 5000
        assert cur == "EUR"
        assert per == SalaryPeriod.MONTH

    def test_eur_text(self):
        text = "11 000 EUR brutto/mies."
        s_min, s_max, cur, per, s_type = _parse_salary(text)
        assert s_min == 11000
        assert s_max == 11000
        assert cur == "EUR"

    def test_usd_currency(self):
        text = "8 000 - 12 000 USD brutto/mies."
        s_min, s_max, cur, per, s_type = _parse_salary(text)
        assert s_min == 8000
        assert s_max == 12000
        assert cur == "USD"

    def test_netto(self):
        text = "4 500 zł netto/mies."
        s_min, s_max, cur, per, s_type = _parse_salary(text)
        assert s_min == 4500
        assert s_max == 4500
        assert s_type == "netto"

    def test_na_reke(self):
        text = "6 000 zł na rękę"
        s_min, s_max, cur, per, s_type = _parse_salary(text)
        assert s_min == 6000
        assert s_type == "netto"

    def test_yearly(self):
        text = "120 000 zł brutto/rok"
        s_min, s_max, cur, per, s_type = _parse_salary(text)
        assert s_min == 120000
        assert per == SalaryPeriod.YEAR

    def test_empty_string(self):
        assert _parse_salary("") == (None, None, None, None, None)

    def test_none(self):
        assert _parse_salary(None) == (None, None, None, None, None)

    def test_no_salary_text(self):
        text = "umowa o pracę · pełny etat"
        s_min, s_max, cur, per, s_type = _parse_salary(text)
        assert s_min is None
        assert s_max is None

    def test_nbsp_handling(self):
        text = "5\xa0100\xa0zł brutto/mies."
        s_min, s_max, cur, per, s_type = _parse_salary(text)
        assert s_min == 5100

    def test_mixed_details_text(self):
        """Salary embedded in main-details text with employment type info."""
        text = "pracownik fizyczny · umowa zlecenie · pełny etat · 12 500 - 14 500 zł brutto/mies. · aplikuj szybko"
        s_min, s_max, cur, per, s_type = _parse_salary(text)
        assert s_min == 12500
        assert s_max == 14500
        assert cur == "PLN"
        assert per == SalaryPeriod.MONTH
        assert s_type == "brutto"

    def test_gbp_currency(self):
        text = "3 500 £ brutto/mies."
        s_min, s_max, cur, per, s_type = _parse_salary(text)
        assert s_min == 3500
        assert cur == "GBP"

    def test_chf_currency(self):
        text = "8 000 CHF brutto/mies."
        s_min, s_max, cur, per, s_type = _parse_salary(text)
        assert s_min == 8000
        assert cur == "CHF"

    def test_daily_rate(self):
        text = "350 zł brutto/dzień"
        s_min, s_max, cur, per, s_type = _parse_salary(text)
        assert s_min == 350
        assert per == SalaryPeriod.DAY

    def test_no_type_defaults_none(self):
        """If brutto/netto not specified, salary_type should be None."""
        text = "5 000 zł/mies."
        s_min, s_max, cur, per, s_type = _parse_salary(text)
        assert s_min == 5000
        assert s_type is None

    def test_b2b_in_text_ignored(self):
        """Digit inside 'B2B' should not be parsed as salary number."""
        text = (
            "specjalista / ekspert  umowa o pracę / kontrakt B2B  "
            "pełny etat  8 000 - 14 000 zł / mies. (w zal. od umowy)"
        )
        s_min, s_max, cur, per, s_type = _parse_salary(text)
        assert s_min == 8000
        assert s_max == 14000

    def test_range_with_dash_no_spaces(self):
        text = "4500-6000 zł brutto/mies."
        s_min, s_max, cur, per, s_type = _parse_salary(text)
        assert s_min == 4500
        assert s_max == 6000
