from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

Unit = Literal["EUR", "kEUR", "count"]
ReviewStatus = Literal[
    "accepted",
    "not_implemented",
    "not_found",
    "source_absent",
    "ocr_empty",
    "unit_ambiguous",
    "period_ambiguous",
    "candidate_conflict",
    "definition_unresolved",
    "invalid_bbox",
    "missing_component",
    "input_error",
]


@dataclass(frozen=True)
class OCRLine:
    index: int
    text: str
    polygon: tuple[tuple[float, float], ...]
    score: float | None = None
    orientation_angle: float | int | None = None

    @property
    def x0(self) -> float:
        return min(p[0] for p in self.polygon)

    @property
    def x1(self) -> float:
        return max(p[0] for p in self.polygon)

    @property
    def y0(self) -> float:
        return min(p[1] for p in self.polygon)

    @property
    def y1(self) -> float:
        return max(p[1] for p in self.polygon)

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def height(self) -> float:
        return self.y1 - self.y0


@dataclass(frozen=True)
class SourceRef:
    page: int
    line_indexes: tuple[int, ...]
    texts: tuple[str, ...]
    polygons: tuple[tuple[tuple[float, float], ...], ...]
    bbox: tuple[float, float, float, float]
    role: str = "value"

    @property
    def snippet(self) -> str:
        return " ".join(t.strip() for t in self.texts if t.strip())


@dataclass
class PageRecord:
    number: int
    width_pt: float
    height_pt: float
    lines: list[OCRLine]
    layout: list[dict[str, Any]]
    raw: dict[str, Any]
    ocr_path: Path
    pdf_rotation: int = 0

    @property
    def has_text(self) -> bool:
        return bool(self.lines)


@dataclass
class DocumentRecord:
    siren: str
    doc_id: str
    deposit_date: str
    fiscal_year_end: str | None
    denomination: str | None
    logical_pdf: str
    pdf_path: Path
    meta_path: Path
    ocr_dir: Path
    pages: list[PageRecord]
    metadata: dict[str, Any]
    input_sha256: str

    @property
    def page_count(self) -> int:
        return len(self.pages)


@dataclass(frozen=True)
class UnitEvidence:
    unit: Unit
    page: int
    line_index: int
    text: str
    scope: Literal["field", "statement", "page", "document"]
    score: int


@dataclass
class Candidate:
    field_key: str
    value: Decimal
    unit: Unit
    value_source: SourceRef
    label_source: SourceRef | None = None
    unit_source: SourceRef | None = None
    period_source: SourceRef | None = None
    method: str = "direct"
    confidence: float = 0.9
    derivation: dict[str, Any] | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)

    @property
    def page(self) -> int:
        return self.value_source.page

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return self.value_source.bbox

    @property
    def snippet(self) -> str:
        return self.value_source.snippet


@dataclass
class Issue:
    status: ReviewStatus
    message: str
    field_key: str | None = None
    page: int | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentOutcome:
    document: DocumentRecord
    accepted: list[Candidate] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    checks: list[dict[str, Any]] = field(default_factory=list)


def decimal_to_json(value: Decimal) -> int | float:
    if value == value.to_integral_value():
        return int(value)
    return float(value)
