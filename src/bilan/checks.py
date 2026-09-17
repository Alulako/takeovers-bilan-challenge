from __future__ import annotations

import json
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .extract import current_period_line, normalize_text, numeric_groups_on_row, parse_number
from .geometry import normalize_box, union_line_box
from .models import Candidate, DocumentOutcome, DocumentRecord, OCRLine, decimal_to_json


class OutputContractError(RuntimeError):
    pass


def load_field_catalog(path: str | Path) -> dict[str, dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return {field["field_key"]: field for field in raw["fields"]}


def candidate_to_result(candidate: Candidate) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "field_key": candidate.field_key,
        "value": decimal_to_json(candidate.value),
        "unit": candidate.unit,
        "page": candidate.page,
        "bbox": [round(float(v), 8) for v in candidate.bbox],
        "snippet": candidate.snippet,
    }
    if candidate.derivation is not None:
        payload["derivation"] = candidate.derivation
    return payload


def outcome_to_document_result(outcome: DocumentOutcome) -> dict[str, Any]:
    return {
        "pdf": outcome.document.logical_pdf,
        "siren": outcome.document.siren,
        "fiscal_year_end": outcome.document.fiscal_year_end,
        "fields": [candidate_to_result(candidate) for candidate in sorted(outcome.accepted, key=lambda c: c.field_key)],
    }


def semantic_validate_document(
    outcome: DocumentOutcome, field_catalog: dict[str, dict[str, Any]]
) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for candidate in outcome.accepted:
        if candidate.field_key not in field_catalog:
            errors.append(f"unknown field_key {candidate.field_key}")
        if candidate.field_key in seen:
            errors.append(f"duplicate field_key {candidate.field_key}")
        seen.add(candidate.field_key)
        x0, y0, x1, y1 = candidate.bbox
        if not (0 <= x0 <= x1 <= 1 and 0 <= y0 <= y1 <= 1):
            errors.append(f"invalid bbox for {candidate.field_key}: {candidate.bbox}")
        if not 1 <= candidate.page <= outcome.document.page_count:
            errors.append(f"page out of range for {candidate.field_key}: {candidate.page}")
        if candidate.field_key == "META_AVG_WORKFORCE_FRGAAP":
            if candidate.unit != "count":
                errors.append("average workforce must use count")
        elif candidate.unit not in {"EUR", "kEUR"}:
            errors.append(f"monetary field {candidate.field_key} has unit {candidate.unit}")
    return errors


def validate_results_payload(
    payload: dict[str, Any], schema_path: str | Path, field_catalog_path: str | Path
) -> None:
    with Path(schema_path).open("r", encoding="utf-8") as fh:
        schema = json.load(fh)
    validator = Draft202012Validator(schema)
    schema_errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    if schema_errors:
        rendered = "; ".join(f"{list(err.path)}: {err.message}" for err in schema_errors[:8])
        raise OutputContractError(f"results.json schema validation failed: {rendered}")

    catalog = load_field_catalog(field_catalog_path)
    allowed = set(catalog)
    seen_docs: set[tuple[str, str]] = set()
    semantic_errors: list[str] = []
    for document in payload.get("documents", []):
        identity = (document.get("siren"), document.get("pdf"))
        if identity in seen_docs:
            semantic_errors.append(f"duplicate result document {identity}")
        seen_docs.add(identity)
        keys: set[str] = set()
        for field in document.get("fields", []):
            key = field.get("field_key")
            if key not in allowed:
                semantic_errors.append(f"unknown field key {key}")
            if key in keys:
                semantic_errors.append(f"duplicate field {key} in {identity}")
            keys.add(key)
            bbox = field.get("bbox")
            if isinstance(bbox, list) and len(bbox) == 4:
                x0, y0, x1, y1 = bbox
                if x0 > x1 or y0 > y1:
                    semantic_errors.append(f"reversed bbox for {identity} {key}")
            if key == "META_AVG_WORKFORCE_FRGAAP" and field.get("unit") != "count":
                semantic_errors.append(f"workforce field must use count in {identity}")
            if key != "META_AVG_WORKFORCE_FRGAAP" and field.get("unit") == "count":
                semantic_errors.append(f"monetary field cannot use count in {identity}: {key}")
    if semantic_errors:
        raise OutputContractError("semantic validation failed: " + "; ".join(semantic_errors[:12]))


def _select_current_balance_number(
    document: DocumentRecord, page, groups: list[list[OCRLine]]
) -> list[OCRLine] | None:
    if not groups:
        return None
    period_line = current_period_line(document, page)
    if period_line is not None:
        target = period_line.cx
    else:
        width_px = page.width_pt * (300.0 / 72.0)
        target = 0.77 * width_px
    return min(
        groups,
        key=lambda group: abs((((min(line.x0 for line in group) + max(line.x1 for line in group)) / 2)) - target),
    )


def independent_passif_total(document: DocumentRecord) -> dict[str, Any] | None:
    """Read EE/full passif strictly as a validation operand, never as an output field."""
    options: list[dict[str, Any]] = []
    for page in document.pages:
        for line in page.lines:
            if normalize_text(line.text).upper() != "EE":
                continue
            groups = numeric_groups_on_row(page, line, line.x1 + 3)
            group = _select_current_balance_number(document, page, groups)
            if not group:
                continue
            value = parse_number(" ".join(item.text for item in group))
            if value is None:
                continue
            raw_box = union_line_box(group)
            try:
                bbox = normalize_box(raw_box, page.width_pt, page.height_pt)
            except ValueError:
                continue
            options.append(
                {
                    "value": value,
                    "page": page.number,
                    "bbox": bbox,
                    "snippet": " ".join(item.text for item in group),
                    "code_line": line.text,
                }
            )
    if not options:
        return None
    # Prefer an option from a page that actually looks like the liability statement.
    def score(option: dict[str, Any]) -> int:
        page = document.pages[option["page"] - 1]
        text = " ".join(normalize_text(line.text) for line in page.lines)
        return (20 if "passif" in text else 0) + (10 if "total" in text else 0)
    return max(options, key=score)


def add_balance_check(outcome: DocumentOutcome) -> None:
    asset = next((c for c in outcome.accepted if c.field_key == "BS_TOTAL_ASSETS_FRGAAP"), None)
    if asset is None:
        outcome.checks.append({"check": "assets_vs_passif", "status": "not_attempted", "reason": "assets_missing"})
        return
    passif = independent_passif_total(outcome.document)
    if passif is None:
        outcome.checks.append({"check": "assets_vs_passif", "status": "not_attempted", "reason": "passif_total_not_found"})
        return
    delta = asset.value - passif["value"]
    tolerance = Decimal("1")
    outcome.checks.append(
        {
            "check": "assets_vs_passif",
            "status": "passed" if abs(delta) <= tolerance else "warning",
            "asset_value": decimal_to_json(asset.value),
            "passif_value": decimal_to_json(passif["value"]),
            "delta": decimal_to_json(delta),
            "tolerance_reporting_units": 1,
            "asset_source": {"page": asset.page, "bbox": list(asset.bbox), "snippet": asset.snippet},
            "passif_source": {
                "page": passif["page"],
                "bbox": list(passif["bbox"]),
                "snippet": passif["snippet"],
            },
        }
    )


def evaluate_review_sample(outcomes: list[DocumentOutcome], reference_path: str | Path) -> dict[str, Any]:
    path = Path(reference_path)
    if not path.exists():
        return {"status": "not_run", "reason": f"reference sample not found: {path}"}
    with path.open("r", encoding="utf-8") as fh:
        reference = json.load(fh)

    lookup = {
        (outcome.document.doc_id, candidate.field_key): candidate
        for outcome in outcomes
        for candidate in outcome.accepted
    }
    items = reference.get("items", [])
    exact = 0
    grounded = 0
    missed = 0
    mismatches: list[dict[str, Any]] = []
    for item in items:
        key = (item["doc_id"], item["field_key"])
        candidate = lookup.get(key)
        if candidate is None:
            missed += 1
            mismatches.append({"doc_id": key[0], "field_key": key[1], "reason": "not_emitted"})
            continue
        value_ok = candidate.value == Decimal(str(item["value"]))
        unit_ok = candidate.unit == item["unit"]
        page_ok = candidate.page == item["page"]
        snippet_ok = item["snippet"] in candidate.snippet
        if value_ok and unit_ok:
            exact += 1
        if value_ok and unit_ok and page_ok and snippet_ok:
            grounded += 1
        if not (value_ok and unit_ok and page_ok and snippet_ok):
            mismatches.append(
                {
                    "doc_id": key[0],
                    "field_key": key[1],
                    "expected": {
                        "value": item["value"],
                        "unit": item["unit"],
                        "page": item["page"],
                        "snippet": item["snippet"],
                    },
                    "actual": {
                        "value": decimal_to_json(candidate.value),
                        "unit": candidate.unit,
                        "page": candidate.page,
                        "snippet": candidate.snippet,
                    },
                }
            )
    total = len(items)
    return {
        "status": "completed",
        "reference_items": total,
        "value_unit_matches": exact,
        "grounded_matches": grounded,
        "missed_available": missed,
        "value_unit_agreement": exact / total if total else None,
        "grounded_agreement": grounded / total if total else None,
        "mismatches": mismatches,
        "claim_scope": "Agreement on the disclosed reviewed sample only; not a global accuracy estimate.",
    }


def build_coverage(outcomes: list[DocumentOutcome]) -> dict[str, Any]:
    accepted_by_field = Counter(c.field_key for outcome in outcomes for c in outcome.accepted)
    issue_by_status = Counter(issue.status for outcome in outcomes for issue in outcome.issues)
    per_company: dict[str, int] = defaultdict(int)
    for outcome in outcomes:
        per_company[outcome.document.siren] += len(outcome.accepted)
    return {
        "accepted_total": sum(accepted_by_field.values()),
        "accepted_by_field": dict(sorted(accepted_by_field.items())),
        "issues_by_status": dict(sorted(issue_by_status.items())),
        "accepted_by_company": dict(sorted(per_company.items())),
    }
