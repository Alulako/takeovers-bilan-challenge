from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pymupdf

from .models import DocumentRecord, OCRLine, PageRecord


class InputContractError(RuntimeError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError as exc:
        raise InputContractError(f"missing input: {path}") from exc
    except json.JSONDecodeError as exc:
        raise InputContractError(f"invalid JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise InputContractError(f"expected object in {path}")
    return data


def _safe_polygon(value: Any, path: Path, line_index: int) -> tuple[tuple[float, float], ...]:
    if not isinstance(value, list) or len(value) < 2:
        raise InputContractError(f"invalid polygon in {path} line {line_index}")
    try:
        points = tuple((float(p[0]), float(p[1])) for p in value)
    except (TypeError, ValueError, IndexError) as exc:
        raise InputContractError(f"invalid polygon in {path} line {line_index}") from exc
    return points


def _hash_inputs(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda p: p.as_posix()):
        digest.update(path.name.encode("utf-8"))
        with path.open("rb") as fh:
            while chunk := fh.read(1024 * 1024):
                digest.update(chunk)
    return digest.hexdigest()


def load_scope(scope_path: str | Path) -> dict[str, Any]:
    path = Path(scope_path)
    data = _load_json(path)
    documents = data.get("documents")
    if not isinstance(documents, list) or not documents:
        raise InputContractError("scope.json must contain a non-empty documents list")
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(documents):
        if not isinstance(item, dict):
            raise InputContractError(f"scope document {index} is not an object")
        required = {"siren", "deposit_date", "doc_id", "pdf", "meta", "ocr"}
        missing = required.difference(item)
        if missing:
            raise InputContractError(f"scope document {index} missing {sorted(missing)}")
        identity = (str(item["siren"]), str(item["doc_id"]))
        if identity in seen:
            raise InputContractError(f"duplicate document in scope: {identity}")
        seen.add(identity)
    return data


def load_document(data_root: str | Path, item: dict[str, Any]) -> DocumentRecord:
    root = Path(data_root)
    pdf_path = root / str(item["pdf"])
    meta_path = root / str(item["meta"])
    ocr_dir = root / str(item["ocr"])
    if not pdf_path.is_file():
        raise InputContractError(f"missing PDF: {pdf_path}")
    if not meta_path.is_file():
        raise InputContractError(f"missing metadata: {meta_path}")
    if not ocr_dir.is_dir():
        raise InputContractError(f"missing OCR directory: {ocr_dir}")

    metadata = _load_json(meta_path)
    expected_siren = str(item["siren"])
    expected_id = str(item["doc_id"])
    if str(metadata.get("siren")) != expected_siren:
        raise InputContractError(
            f"SIREN mismatch for {expected_id}: scope={expected_siren}, meta={metadata.get('siren')}"
        )
    if str(metadata.get("id")) != expected_id:
        raise InputContractError(
            f"document id mismatch: scope={expected_id}, meta={metadata.get('id')}"
        )

    page_files = sorted(ocr_dir.glob("page_*.json"))
    if not page_files:
        raise InputContractError(f"no OCR pages in {ocr_dir}")

    pdf = pymupdf.open(pdf_path)
    try:
        if len(page_files) != len(pdf):
            raise InputContractError(
                f"OCR/PDF page-count mismatch for {expected_id}: {len(page_files)} vs {len(pdf)}"
            )
        pages: list[PageRecord] = []
        for page_number, (ocr_path, pdf_page) in enumerate(zip(page_files, pdf), start=1):
            expected_name = f"page_{page_number:03d}.json"
            if ocr_path.name != expected_name:
                raise InputContractError(
                    f"non-contiguous OCR pages for {expected_id}: expected {expected_name}, got {ocr_path.name}"
                )
            raw = _load_json(ocr_path)
            if raw.get("page") != page_number:
                raise InputContractError(
                    f"OCR page number mismatch in {ocr_path}: {raw.get('page')} != {page_number}"
                )
            raw_lines = raw.get("ocr") or []
            if not isinstance(raw_lines, list):
                raise InputContractError(f"ocr must be a list in {ocr_path}")
            lines: list[OCRLine] = []
            for line_index, raw_line in enumerate(raw_lines):
                if not isinstance(raw_line, dict):
                    raise InputContractError(f"invalid OCR line in {ocr_path}: {line_index}")
                polygon = _safe_polygon(raw_line.get("polygon"), ocr_path, line_index)
                score_raw = raw_line.get("score")
                try:
                    score = None if score_raw is None else float(score_raw)
                except (TypeError, ValueError):
                    score = None
                lines.append(
                    OCRLine(
                        index=line_index,
                        text=str(raw_line.get("text") or ""),
                        polygon=polygon,
                        score=score,
                        orientation_angle=raw_line.get("orientation_angle"),
                    )
                )
            pages.append(
                PageRecord(
                    number=page_number,
                    width_pt=float(pdf_page.rect.width),
                    height_pt=float(pdf_page.rect.height),
                    lines=lines,
                    layout=list(raw.get("layout") or []),
                    raw=raw,
                    ocr_path=ocr_path,
                    pdf_rotation=int(pdf_page.rotation or 0),
                )
            )
    finally:
        pdf.close()

    source_paths = [pdf_path, meta_path, *page_files]
    input_sha256 = _hash_inputs(source_paths)
    return DocumentRecord(
        siren=expected_siren,
        doc_id=expected_id,
        deposit_date=str(item["deposit_date"]),
        fiscal_year_end=metadata.get("dateCloture"),
        denomination=metadata.get("denomination"),
        logical_pdf=f"data/{item['pdf']}",
        pdf_path=pdf_path,
        meta_path=meta_path,
        ocr_dir=ocr_dir,
        pages=pages,
        metadata=metadata,
        input_sha256=input_sha256,
    )


def load_documents(data_root: str | Path, scope_path: str | Path) -> list[DocumentRecord]:
    scope = load_scope(scope_path)
    documents = [load_document(data_root, item) for item in scope["documents"]]
    if len(documents) != 15:
        raise InputContractError(f"expected 15 challenge documents, loaded {len(documents)}")
    return documents


def inventory(documents: list[DocumentRecord]) -> dict[str, int]:
    pages = sum(doc.page_count for doc in documents)
    empty_ocr = sum(1 for doc in documents for page in doc.pages if not page.lines)
    empty_layout = sum(1 for doc in documents for page in doc.pages if not page.layout)
    return {
        "documents": len(documents),
        "pages": pages,
        "empty_ocr_pages": empty_ocr,
        "empty_layout_pages": empty_layout,
    }
