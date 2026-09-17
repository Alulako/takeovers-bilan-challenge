from __future__ import annotations

import json
from pathlib import Path

import pytest

from bilan.checks import OutputContractError, validate_results_payload
from bilan.inputs import inventory, load_documents

ROOT = Path(__file__).resolve().parents[1]


def _minimal_payload() -> dict:
    return {
        "documents": [
            {
                "pdf": "data/123456789/bilans/pdf/example.pdf",
                "siren": "123456789",
                "fiscal_year_end": "2025-12-31",
                "fields": [
                    {
                        "field_key": "BS_TOTAL_ASSETS_FRGAAP",
                        "value": 1000,
                        "unit": "EUR",
                        "page": 1,
                        "bbox": [0.1, 0.2, 0.3, 0.25],
                    }
                ],
            }
        ],
        "run": {
            "cost_eur_per_page": 0.0,
            "seconds_per_page": 0.01,
            "pages_processed": 1,
            "model": "provided OCR + deterministic rules",
            "notes": "test",
        },
    }


def test_official_schema_plus_semantic_validation_accepts_valid_payload() -> None:
    validate_results_payload(
        _minimal_payload(), ROOT / "schema/results.schema.json", ROOT / "schema/financial_fields.json"
    )


def test_semantic_validation_rejects_unknown_field_and_reversed_bbox() -> None:
    payload = _minimal_payload()
    payload["documents"][0]["fields"][0]["field_key"] = "NOT_A_FIELD"
    payload["documents"][0]["fields"][0]["bbox"] = [0.4, 0.2, 0.3, 0.25]
    with pytest.raises(OutputContractError):
        validate_results_payload(
            payload, ROOT / "schema/results.schema.json", ROOT / "schema/financial_fields.json"
        )


def test_local_scope_inventory_matches_audited_corpus_when_reference_is_present() -> None:
    data_root = ROOT / "challenge-reference/data"
    if not data_root.exists():
        pytest.skip("local challenge corpus is intentionally not distributed with candidate repository")
    docs = load_documents(data_root, ROOT / "scope.json")
    inv = inventory(docs)
    assert inv["documents"] == 15
    assert inv["pages"] == 415
    assert inv["empty_ocr_pages"] == 41
    assert inv["empty_layout_pages"] == 46
