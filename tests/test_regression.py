from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from bilan.extract import extract_document
from bilan.inputs import load_documents

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "challenge-reference/data"


def _document(doc_id: str):
    if not DATA_ROOT.exists():
        pytest.skip("local challenge corpus is intentionally not distributed with candidate repository")
    docs = load_documents(DATA_ROOT, ROOT / "scope.json")
    return next(doc for doc in docs if doc.doc_id == doc_id)


def _accepted(doc_id: str) -> dict[str, object]:
    accepted, _, _ = extract_document(_document(doc_id))
    return {candidate.field_key: candidate for candidate in accepted}


def test_total_assets_uses_net_n_not_depreciation_on_standard_2050() -> None:
    # BERNACHON 2021 p2 prints gross 7,113,704; depreciation 2,290,400;
    # and net current-period assets 4,823,303. A fixed x-position rule used
    # to select depreciation here, so keep this as a permanent regression.
    fields = _accepted("63e8ebbb54febda17c19ee7d")
    assets = fields["BS_TOTAL_ASSETS_FRGAAP"]
    assert assets.value == 4_823_303
    assert assets.page == 2
    assert assets.snippet == "4 823 303"
    assert assets.diagnostics["column_basis"] == "net_header"


def test_accountant_balance_selects_current_net_and_current_equity() -> None:
    # PAUTET 2021 carries N and N-1 side by side. The current exercise is
    # identified from the fiscal close header rather than from the rightmost value.
    fields = _accepted("6493e4372f502414800f8164")
    assert fields["BS_TOTAL_ASSETS_FRGAAP"].value == 638_962
    assert fields["BS_TOTAL_EQUITY_FRGAAP"].value == 322_009
    assert fields["BS_TOTAL_ASSETS_FRGAAP"].diagnostics["column_basis"] == "net_header"
    assert fields["BS_TOTAL_EQUITY_FRGAAP"].diagnostics["column_basis"] == "fiscal_year_header"


def test_rotated_pdf_keeps_correct_current_net_asset_value() -> None:
    # CREAMANDE 2025 is PDF-rotated, but displayed OCR geometry is upright.
    fields = _accepted("68f0a715f28d8aaf48046416")
    assets = fields["BS_TOTAL_ASSETS_FRGAAP"]
    assert assets.value == 1_135_864
    assert assets.page == 2
    assert assets.diagnostics["column_basis"] == "net_header"


def test_standard_pl_recovers_total_column_when_fl_code_is_ocr_missed() -> None:
    # CREAMANDE 2022 p4 has France=1,770,709, export=30,117 and
    # total net revenue=1,800,826. OCR misses/corrupts FL, so a generic
    # x-position rule previously returned the export amount.
    fields = _accepted("63e881158be6eb9f9d1ff975")
    revenue = fields["PL_REVENUE_FRGAAP"]
    assert revenue.value == 1_800_826
    assert revenue.page == 4
    assert revenue.diagnostics["column_basis"] == "standard_form_total_column"


def test_trailing_parenthesis_ocr_still_preserves_negative_financial_result() -> None:
    fields = _accepted("63e881158be6eb9f9d1ff975")
    financial_result = fields["PL_FINANCIAL_RESULTS_FRGAAP"]
    assert financial_result.value == -2_778
    assert financial_result.page == 4


def test_asset_total_does_not_confuse_immobilised_or_current_asset_subtotals() -> None:
    fields = _accepted("63e8ebbb54febda17c19ee7c")
    assets = fields["BS_TOTAL_ASSETS_FRGAAP"]
    assert assets.value == 3_500_529
    assert assets.page == 2


def test_disclosed_review_sample_matches_source_checked_references() -> None:
    if not DATA_ROOT.exists():
        pytest.skip("local challenge corpus is intentionally not distributed with candidate repository")
    reviewed = json.loads((ROOT / "tests/fixtures/reviewed.json").read_text(encoding="utf-8"))
    docs = {doc.doc_id: doc for doc in load_documents(DATA_ROOT, ROOT / "scope.json")}
    extracted: dict[str, dict[str, object]] = {}
    for doc_id in {item["doc_id"] for item in reviewed["items"]}:
        accepted, _, _ = extract_document(docs[doc_id])
        extracted[doc_id] = {candidate.field_key: candidate for candidate in accepted}

    assert len(reviewed["items"]) == 30
    for item in reviewed["items"]:
        candidate = extracted[item["doc_id"]][item["field_key"]]
        assert candidate.value == Decimal(str(item["value"]))
        assert candidate.unit == item["unit"]
        assert candidate.page == item["page"]
        assert item["snippet"] in candidate.snippet
