from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any

from .checks import (
    OutputContractError,
    add_balance_check,
    build_coverage,
    evaluate_review_sample,
    load_field_catalog,
    outcome_to_document_result,
    semantic_validate_document,
    validate_results_payload,
)
from .extract import extract_document
from .inputs import InputContractError, inventory, load_documents
from .models import DocumentOutcome, decimal_to_json


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m bilan",
        description="Provenance-first extractor for the Takeovers Bilan challenge.",
    )
    parser.add_argument("--data-root", default="challenge-reference/data", help="root containing <siren>/bilans/...")
    parser.add_argument("--scope", default="scope.json", help="exact 15-document manifest")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("inventory", help="verify scope and report input counts")

    run = sub.add_parser("run", help="extract fields, validate output and produce diagnostics")
    run.add_argument("--output", default="results.json")
    run.add_argument("--review-output", default="review.json")
    run.add_argument("--schema", default="schema/results.schema.json")
    run.add_argument("--field-catalog", default="schema/financial_fields.json")
    run.add_argument("--review-reference", default="tests/fixtures/reviewed.json")
    run.add_argument("--dry-run", action="store_true", help="validate and print a summary without writing files")
    run.add_argument("--print-results", action="store_true", help="print the validated results payload to stdout")

    validate = sub.add_parser("validate", help="validate an existing results.json")
    validate.add_argument("path", nargs="?", default="results.json")
    validate.add_argument("--schema", default="schema/results.schema.json")
    validate.add_argument("--field-catalog", default="schema/financial_fields.json")
    return parser


def _source_payload(source) -> dict[str, Any] | None:
    if source is None:
        return None
    return {
        "page": source.page,
        "line_indexes": list(source.line_indexes),
        "texts": list(source.texts),
        "bbox": [round(v, 8) for v in source.bbox],
        "role": source.role,
    }


def _candidate_review(candidate) -> dict[str, Any]:
    return {
        "field_key": candidate.field_key,
        "value": decimal_to_json(candidate.value),
        "unit": candidate.unit,
        "method": candidate.method,
        "heuristic_ranking_score": round(candidate.confidence, 3),
        "value_source": _source_payload(candidate.value_source),
        "label_source": _source_payload(candidate.label_source),
        "unit_source": _source_payload(candidate.unit_source),
        "period_source": _source_payload(candidate.period_source),
        "diagnostics": candidate.diagnostics,
        "derivation": candidate.derivation,
    }


def _issue_review(issue) -> dict[str, Any]:
    return {
        "status": issue.status,
        "field_key": issue.field_key,
        "page": issue.page,
        "message": issue.message,
        "details": issue.details,
    }


def _safe_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(temp, path)


def _run(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    start = time.perf_counter()
    load_start = start
    documents = load_documents(args.data_root, args.scope)
    load_seconds = time.perf_counter() - load_start
    inv = inventory(documents)

    field_catalog = load_field_catalog(args.field_catalog)
    outcomes: list[DocumentOutcome] = []
    extraction_start = time.perf_counter()
    document_times: dict[str, float] = {}
    for document in documents:
        doc_start = time.perf_counter()
        accepted, issues, _all_candidates = extract_document(document)
        outcome = DocumentOutcome(document=document, accepted=accepted, issues=issues)
        add_balance_check(outcome)
        semantic_errors = semantic_validate_document(outcome, field_catalog)
        if semantic_errors:
            raise OutputContractError(
                f"semantic validation failed for {document.doc_id}: " + "; ".join(semantic_errors)
            )
        outcomes.append(outcome)
        document_times[document.doc_id] = time.perf_counter() - doc_start
    extraction_seconds = time.perf_counter() - extraction_start

    elapsed_before_serialization = time.perf_counter() - start
    pages_processed = inv["pages"]
    results: dict[str, Any] = {
        "documents": [outcome_to_document_result(outcome) for outcome in outcomes],
        "run": {
            "cost_eur_per_page": 0.0,
            "seconds_per_page": elapsed_before_serialization / pages_processed if pages_processed else 0.0,
            "pages_processed": pages_processed,
            "model": "provided OCR + deterministic rules",
            "notes": (
                "Measured locally over all physical PDF pages inspected by the run, including empty OCR pages. "
                "Incremental extraction API cost is EUR 0/page because the MVP makes no model/API calls; upstream OCR, "
                "local compute and human review are excluded. Timing covers input loading, extraction and checks up to "
                "final JSON serialization/validation bookkeeping."
            ),
        },
    }
    validate_results_payload(results, args.schema, args.field_catalog)

    coverage = build_coverage(outcomes)
    evaluation = evaluate_review_sample(outcomes, args.review_reference)
    review: dict[str, Any] = {
        "about": "Diagnostics are intentionally separate from the scorer-facing results.json.",
        "scope": inv,
        "coverage": coverage,
        "evaluation": evaluation,
        "timing": {
            "load_seconds": load_seconds,
            "extraction_and_checks_seconds": extraction_seconds,
            "elapsed_before_serialization_seconds": elapsed_before_serialization,
            "seconds_per_page_reported": results["run"]["seconds_per_page"],
            "document_seconds": document_times,
        },
        "runtime": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "command_model": "provided OCR + deterministic rules",
            "api_calls": 0,
            "api_cost_eur": 0.0,
        },
        "documents": [],
        "limitations": [
            "The MVP implements six P0 fields only; two P1 fields are left disabled and four catalogue definitions remain unresolved.",
            "A French-form EUR default is used only when no contrary scale cue is found; that basis is exposed per candidate.",
            "Consistency checks are validation evidence, not a substitute for independently reviewed ground truth.",
            "The supplied OCR can contain reading errors; accepted values preserve the exact OCR snippet and bbox used.",
        ],
    }
    for outcome in outcomes:
        review["documents"].append(
            {
                "siren": outcome.document.siren,
                "doc_id": outcome.document.doc_id,
                "pdf": outcome.document.logical_pdf,
                "fiscal_year_end": outcome.document.fiscal_year_end,
                "input_sha256": outcome.document.input_sha256,
                "accepted": [_candidate_review(candidate) for candidate in outcome.accepted],
                "issues": [_issue_review(issue) for issue in outcome.issues],
                "checks": outcome.checks,
            }
        )
    return results, review


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    try:
        if args.command == "inventory":
            documents = load_documents(args.data_root, args.scope)
            print(json.dumps(inventory(documents), indent=2))
            return 0
        if args.command == "validate":
            with Path(args.path).open("r", encoding="utf-8") as fh:
                payload = json.load(fh)
            validate_results_payload(payload, args.schema, args.field_catalog)
            print(f"valid: {args.path}")
            return 0
        if args.command == "run":
            results, review = _run(args)
            if args.print_results:
                print(json.dumps(results, ensure_ascii=False, indent=2))
            print(
                json.dumps(
                    {
                        "documents": len(results["documents"]),
                        "pages_processed": results["run"]["pages_processed"],
                        "accepted_fields": review["coverage"]["accepted_total"],
                        "accepted_by_field": review["coverage"]["accepted_by_field"],
                        "seconds_per_page": results["run"]["seconds_per_page"],
                        "dry_run": args.dry_run,
                    },
                    indent=2,
                ),
                file=sys.stderr if args.print_results else sys.stdout,
            )
            if not args.dry_run:
                _safe_write_json(Path(args.output), results)
                _safe_write_json(Path(args.review_output), review)
            return 0
    except (InputContractError, OutputContractError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
