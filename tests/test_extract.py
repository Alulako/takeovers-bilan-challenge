from __future__ import annotations

from decimal import Decimal

import pytest

from bilan.extract import normalize_text, parse_number


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0", Decimal("0")),
        ("4 982 524", Decimal("4982524")),
        ("(2 778)", Decimal("-2778")),
        ("2 778)", Decimal("-2778")),
        ("111 724.81-", Decimal("-111724.81")),
        ("1 234,56", Decimal("1234.56")),
        ("+ 955 934,07", Decimal("955934.07")),
        ("1.234.567", Decimal("1234567")),
    ],
)
def test_parse_number_supported_formats(raw: str, expected: Decimal) -> None:
    assert parse_number(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "-", "1.234", "7.113 7042 290 400", "12A34", "1 23 456", "1,234,56"],
)
def test_parse_number_rejects_ambiguity(raw: str) -> None:
    assert parse_number(raw) is None


def test_normalize_text_handles_accents_without_touching_numbers() -> None:
    assert normalize_text("Résultat financier (V - VI)") == "resultat financier (v - vi)"
    assert normalize_text("Impôts sur les bénéfices") == "impots sur les benefices"
