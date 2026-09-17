from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable, Sequence

from .geometry import normalize_box, same_row, union_line_box
from .models import Candidate, DocumentRecord, Issue, OCRLine, PageRecord, SourceRef, Unit


@dataclass(frozen=True)
class FieldSpec:
    field_key: str
    code: str | None
    aliases: tuple[str, ...]
    statement: str
    priority: str = "P0"


FIELD_SPECS: tuple[FieldSpec, ...] = (
    FieldSpec(
        "BS_TOTAL_ASSETS_FRGAAP",
        "CO",
        ("total general actif", "total general", "total actif (i a vi)", "total actif (i e vi)"),
        "BS_ASSET",
    ),
    FieldSpec(
        "BS_TOTAL_EQUITY_FRGAAP",
        "DL",
        ("total des capitaux propres", "total capitaux propres", "capitaux propres total"),
        "BS_LIABILITY",
    ),
    FieldSpec(
        "PL_REVENUE_FRGAAP",
        "FL",
        ("chiffres d'affaires nets", "chiffre d'affaires net", "chiffre d'affaires"),
        "PL",
    ),
    FieldSpec(
        "PL_EXT_SERVICES_COSTS_FRGAAP",
        "FW",
        ("autres achats et charges externes",),
        "PL",
    ),
    FieldSpec(
        "PL_FINANCIAL_RESULTS_FRGAAP",
        "GV",
        ("resultat financier",),
        "PL",
    ),
    FieldSpec(
        "PL_INCOME_TAX_FRGAAP",
        "HK",
        ("impots sur les benefices", "impot sur les benefices"),
        "PL",
    ),
)

DEFERRED_FIELDS = {
    "PL_COGS_FRGAAP",
    "PL_DEPRECIATION_AMORTIZATION_FRGAAP",
    "BS_CAPITAL_EQUITY_FRGAAP",
    "BS_CASH_CURRENT_ASSET_FRGAAP",
}

P1_FIELDS = {"PL_PERSONNEL_COSTS_FRGAAP", "META_AVG_WORKFORCE_FRGAAP"}


def normalize_text(text: str) -> str:
    text = text.replace("�", "e").replace("’", "'").replace("`", "'")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().replace("\u00a0", " ").replace("\u202f", " ")
    text = re.sub(r"[^a-z0-9€%+'().,/_ -]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _looks_numeric_fragment(text: str) -> bool:
    s = text.strip().replace("\u00a0", " ").replace("\u202f", " ")
    if not s:
        return False
    if re.search(r"[A-Za-zÀ-ÿ€]", s):
        return False
    return bool(re.fullmatch(r"[+\-−–—()\d\s.,_']+", s)) and bool(re.search(r"\d", s))


def parse_number(text: str) -> Decimal | None:
    """Parse a conservative French/European accounting number.

    The parser intentionally refuses ambiguous punctuation rather than using an
    accounting identity as an oracle. It never substitutes OCR letters for digits.
    """
    raw = text.strip().replace("\u00a0", " ").replace("\u202f", " ")
    raw = raw.replace("−", "-").replace("–", "-").replace("—", "-").replace("_", " ")
    if not raw or not re.search(r"\d", raw):
        return None
    if re.search(r"[A-Za-zÀ-ÿ€]", raw):
        return None

    negative = False
    raw = raw.strip()
    if raw.startswith("(") and raw.endswith(")"):
        negative = True
        raw = raw[1:-1].strip()
    elif raw.endswith(")") and "(" not in raw:
        # Observed OCR failure mode: the opening accounting parenthesis can be
        # dropped while the closing parenthesis survives (e.g. ``2 778)``).
        negative = True
        raw = raw[:-1].strip()
    elif raw.startswith("(") and ")" not in raw:
        negative = True
        raw = raw[1:].strip()
    if raw.endswith("-"):
        negative = True
        raw = raw[:-1].strip()
    if raw.startswith("-"):
        negative = True
        raw = raw[1:].strip()
    elif raw.startswith("+"):
        raw = raw[1:].strip()

    raw = raw.replace("'", "")
    raw = re.sub(r"\s+", " ", raw).strip()
    if not raw or not re.fullmatch(r"[\d .,]+", raw):
        return None

    # Comma is the decimal separator when present once with 1–2 trailing digits.
    if "," in raw:
        if raw.count(",") != 1:
            return None
        integer, frac = raw.split(",", 1)
        if not frac.isdigit() or len(frac) not in (1, 2):
            return None
        integer_digits = _parse_integer_part(integer)
        if integer_digits is None:
            return None
        normalized = f"{integer_digits}.{frac}"
    elif "." in raw:
        # A single dot followed by 1–2 digits is accepted as an observed decimal.
        if raw.count(".") == 1:
            before, after = raw.split(".", 1)
            if after.isdigit() and len(after) in (1, 2):
                integer_digits = _parse_integer_part(before)
                if integer_digits is None:
                    return None
                normalized = f"{integer_digits}.{after}"
            else:
                # '1.234' is deliberately ambiguous: decimal vs thousands.
                return None
        else:
            parts = raw.split(".")
            if not parts[0].isdigit() or any(not p.isdigit() or len(p) != 3 for p in parts[1:]):
                return None
            normalized = "".join(parts)
    else:
        integer_digits = _parse_integer_part(raw)
        if integer_digits is None:
            return None
        normalized = integer_digits

    try:
        value = Decimal(normalized)
    except InvalidOperation:
        return None
    return -value if negative else value


def _parse_integer_part(text: str) -> str | None:
    text = text.strip()
    if not text:
        return "0"
    if " " not in text:
        return text if text.isdigit() else None
    groups = text.split()
    if not groups or not all(g.isdigit() for g in groups):
        return None
    if len(groups) == 1:
        return groups[0]
    if not 1 <= len(groups[0]) <= 3:
        return None
    if any(len(g) != 3 for g in groups[1:]):
        return None
    return "".join(groups)


def _source_ref(page: PageRecord, lines: Sequence[OCRLine], role: str) -> SourceRef:
    if not lines:
        raise ValueError("source reference needs at least one OCR line")
    raw_box = union_line_box(lines)
    bbox = normalize_box(raw_box, page.width_pt, page.height_pt)
    return SourceRef(
        page=page.number,
        line_indexes=tuple(line.index for line in lines),
        texts=tuple(line.text for line in lines),
        polygons=tuple(line.polygon for line in lines),
        bbox=bbox,
        role=role,
    )


def numeric_groups_on_row(page: PageRecord, anchor: OCRLine, min_x: float) -> list[list[OCRLine]]:
    row_lines = [
        line
        for line in page.lines
        if line.x0 >= min_x - 5 and same_row(anchor, line) and _looks_numeric_fragment(line.text)
    ]
    row_lines.sort(key=lambda line: line.x0)
    groups: list[list[OCRLine]] = []
    for line in row_lines:
        if not groups:
            groups.append([line])
            continue
        prev = groups[-1][-1]
        gap = line.x0 - prev.x1
        # Split columns aggressively; merge split thousands/sign fragments only.
        if gap <= max(42.0, 1.05 * max(line.height, prev.height)):
            trial = " ".join(x.text.strip() for x in [*groups[-1], line])
            if parse_number(trial) is not None or line.text.strip() in {"-", "+"}:
                groups[-1].append(line)
            else:
                groups.append([line])
        else:
            groups.append([line])
    return [group for group in groups if parse_number(" ".join(line.text for line in group)) is not None]


def _statement_score(page: PageRecord, statement: str) -> int:
    text = " ".join(normalize_text(line.text) for line in page.lines)
    if statement == "BS_ASSET":
        if "bilan" in text and "actif" in text:
            return 20
        if "total actif" in text or "actif circulant" in text:
            return 12
    elif statement == "BS_LIABILITY":
        if "bilan" in text and "passif" in text:
            return 20
        if "total passif" in text or "capitaux propres" in text:
            return 12
    elif statement == "PL":
        if "compte de resultat" in text:
            return 20
        markers = sum(
            marker in text
            for marker in (
                "charges d'exploitation",
                "produits d'exploitation",
                "resultat financier",
                "chiffre d'affaires",
            )
        )
        if markers >= 2:
            return 12
    return 0


def _primary_statement_score(page: PageRecord, statement: str) -> int:
    text = " ".join(normalize_text(line.text) for line in page.lines)
    if statement == "BS_ASSET":
        if "dgfip" in text and "2050" in text:
            return 30
        if "bilan actif" in text and "note" not in text[:250]:
            return 20
    elif statement == "BS_LIABILITY":
        if "dgfip" in text and "2051" in text:
            return 30
        if "bilan passif" in text and "note" not in text[:250]:
            return 20
    elif statement == "PL":
        if "dgfip" in text and ("2052" in text or "2053" in text):
            return 30
        if "compte de resultat" in text and "notes sur le compte de resultat" not in text:
            return 20
    return 0


def _unit_from_page(document: DocumentRecord, page: PageRecord, anchor: OCRLine) -> tuple[Unit, SourceRef | None, str]:
    # Only local, statement-like kEUR cues are allowed to override the form default.
    local_k: list[OCRLine] = []
    local_eur: list[OCRLine] = []
    for line in page.lines:
        norm = normalize_text(line.text)
        if re.search(r"\b(k€|keur)\b|kilo.?euros|milliers? d[' ]?euros|montants?.{0,20}k€", norm):
            local_k.append(line)
        if re.search(r"\ben euros\b|dossier.{0,40}en euros|montants?.{0,20}en euros", norm):
            local_eur.append(line)

    # Prefer cues near the target row or cues that explicitly state a table/statement scale.
    nearby_k = [line for line in local_k if abs(line.cy - anchor.cy) <= 700 or "montant" in normalize_text(line.text) or "tableau" in normalize_text(line.text)]
    nearby_eur = [line for line in local_eur if abs(line.cy - anchor.cy) <= 700 or "dossier" in normalize_text(line.text) or "montant" in normalize_text(line.text)]
    if nearby_k and not nearby_eur:
        line = sorted(nearby_k, key=lambda x: abs(x.cy - anchor.cy))[0]
        return "kEUR", _source_ref(page, [line], "unit"), "explicit_page_kEUR"
    if nearby_eur and not nearby_k:
        line = sorted(nearby_eur, key=lambda x: abs(x.cy - anchor.cy))[0]
        return "EUR", _source_ref(page, [line], "unit"), "explicit_page_EUR"
    if nearby_k and nearby_eur:
        # A local conflict is too dangerous for a 1000x-sensitive value.
        raise ValueError("conflicting unit evidence on statement page")

    # Search conservative document-wide wording. Specific amounts such as dividends,
    # share capital, subsidiaries and individual transactions do not establish scale.
    for other in document.pages:
        for line in other.lines:
            norm = normalize_text(line.text)
            if any(word in norm for word in ("dividende", "capital de", "filiale", "participation", "abandon", "emprunt")):
                continue
            if re.search(r"dossier.{0,40}en euros|comptes?.{0,40}en euros|montants?.{0,20}en euros", norm):
                return "EUR", _source_ref(other, [line], "unit"), "explicit_document_EUR"
            if re.search(r"comptes?.{0,40}(k€|keur|milliers)|montants?.{0,20}(k€|keur|milliers)", norm):
                return "kEUR", _source_ref(other, [line], "unit"), "explicit_document_kEUR"

    # French tax/accounting forms are reported in euros unless a scale is explicitly
    # stated. This fallback is disclosed in review.json rather than masquerading as a cue.
    return "EUR", None, "form_default_EUR_no_contrary_scale"


def _label_match_score(line: OCRLine, aliases: Sequence[str]) -> int:
    norm = normalize_text(line.text)
    best = 0
    for alias in aliases:
        a = normalize_text(alias)
        if norm == a:
            best = max(best, 35)
        elif a in norm:
            best = max(best, 30)
        elif len(a) >= 12:
            # OCR often damages a few accented characters; word-overlap is bounded and
            # is never used on numeric text.
            aw = {w for w in a.split() if len(w) >= 4}
            nw = set(norm.split())
            if aw and len(aw & nw) / len(aw) >= 0.75:
                best = max(best, 20)
    return best


def _date_tokens(value: str | None) -> set[str]:
    if not value or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return set()
    year, month, day = value.split("-")
    short_year = year[-2:]
    return {
        f"{day}/{month}/{year}",
        f"{day}-{month}-{year}",
        f"{year}/{month}/{day}",
        value,
        f"{day}/{month}/{short_year}",
        f"{day}-{month}-{short_year}",
    }


def current_period_line(document: DocumentRecord, page: PageRecord) -> OCRLine | None:
    """Return OCR evidence for the filing's current exercise when it is explicit on the page."""
    tokens = _date_tokens(document.fiscal_year_end)
    if not tokens:
        return None
    hits: list[OCRLine] = []
    for line in page.lines:
        compact = re.sub(r"\s+", "", line.text)
        if any(token in compact for token in tokens):
            hits.append(line)
    if not hits:
        return None
    # Header dates are preferable to dates repeated in notes/footers.
    page_height_px = page.height_pt * (300.0 / 72.0)
    return min(hits, key=lambda line: (line.cy > 0.35 * page_height_px, line.cy))


def _column_target_x(document: DocumentRecord, page: PageRecord, spec: FieldSpec) -> tuple[float | None, OCRLine | None, str]:
    """Infer the current-period column from explicit page headers before using geometry priors."""
    period_line = current_period_line(document, page)
    page_height_px = page.height_pt * (300.0 / 72.0)

    if spec.statement == "BS_ASSET":
        net_headers = [
            line
            for line in page.lines
            if normalize_text(line.text) == "net" and line.cy <= 0.35 * page_height_px
        ]
        if net_headers:
            if period_line is not None:
                net = min(net_headers, key=lambda line: abs(line.cx - period_line.cx))
            elif len(net_headers) == 1:
                net = net_headers[0]
            else:
                # Common accountant layouts put current N before N-1. This is only
                # a fallback when the date header was OCR-missed; diagnostics expose it.
                net = min(net_headers, key=lambda line: line.cx)
            return net.cx, period_line, "net_header"

    if period_line is not None and spec.statement in {"BS_ASSET", "BS_LIABILITY", "PL"}:
        return period_line.cx, period_line, "fiscal_year_header"

    return None, period_line, "none"


def _select_value_group(
    document: DocumentRecord,
    page: PageRecord,
    groups: list[list[OCRLine]],
    spec: FieldSpec,
    used_code: bool,
) -> tuple[list[OCRLine] | None, OCRLine | None, str]:
    if not groups:
        return None, None, "no_groups"
    if used_code and spec.statement == "PL":
        # In standard 2052/2053 forms the code is immediately left of the current value.
        period_line = current_period_line(document, page)
        return groups[0], period_line, "first_group_right_of_code"

    page_width_px = page.width_pt * (300.0 / 72.0)
    explicit_target, period_line, target_basis = _column_target_x(document, page, spec)

    if not used_code and spec.statement == "PL" and explicit_target is None:
        page_text = " ".join(normalize_text(line.text) for line in page.lines[:80])
        if "dgfip" in page_text and ("2052" in page_text or "2053" in page_text):
            # Standard French tax forms put the current-period total in the
            # rightmost numeric column. This matters when the two-letter row
            # code itself was missed by OCR (e.g. FJ/FK/FL revenue rows).
            group = max(groups, key=lambda g: max(line.x1 for line in g))
            return group, period_line, "standard_form_total_column"
    target_x = explicit_target if explicit_target is not None else 0.77 * page_width_px

    plausible = []
    for group in groups:
        x0 = min(line.x0 for line in group)
        x1 = max(line.x1 for line in group)
        cx = (x0 + x1) / 2
        plausible.append((abs(cx - target_x), cx, group))
    plausible.sort(key=lambda item: item[0])
    best = plausible[0]

    # Only use the legacy nearest-right safeguard when no semantic column target exists.
    if explicit_target is None and used_code and all(item[1] > 0.84 * page_width_px for item in plausible):
        return min(groups, key=lambda g: min(line.x0 for line in g)), period_line, "nearest_right_code_fallback"
    return best[2], period_line, target_basis if explicit_target is not None else "geometric_prior"


def _candidate_from_anchor(
    document: DocumentRecord,
    page: PageRecord,
    spec: FieldSpec,
    anchor: OCRLine,
    label: OCRLine | None,
    used_code: bool,
) -> Candidate | Issue:
    min_x = anchor.x1 + 3 if used_code else (label or anchor).x1 + 5
    groups = numeric_groups_on_row(page, anchor, min_x)
    if not groups and label is not None and anchor is not label:
        groups = numeric_groups_on_row(page, label, label.x1 + 5)
    group, period_line, column_basis = _select_value_group(document, page, groups, spec, used_code)
    if group is None:
        return Issue("not_found", "anchor found but no unambiguous numeric group on the row", spec.field_key, page.number)
    raw = " ".join(line.text.strip() for line in group)
    value = parse_number(raw)
    if value is None:
        return Issue("not_found", f"numeric group could not be parsed: {raw!r}", spec.field_key, page.number)
    try:
        unit, unit_source, unit_basis = _unit_from_page(document, page, anchor)
    except ValueError as exc:
        return Issue("unit_ambiguous", str(exc), spec.field_key, page.number)

    label_line = label or anchor
    statement_score = _statement_score(page, spec.statement)
    primary_statement_score = _primary_statement_score(page, spec.statement)
    base = 0.66
    if used_code:
        base += 0.16
    if label is not None:
        base += min(0.12, _label_match_score(label, spec.aliases) / 300)
    base += min(0.05, statement_score / 400)
    if unit_source is not None:
        base += 0.03
    confidence = min(0.98, base)
    value_source = _source_ref(page, group, "value")
    label_source = _source_ref(page, [label_line], "label")
    period_source = _source_ref(page, [period_line], "period") if period_line is not None else None
    return Candidate(
        field_key=spec.field_key,
        value=value,
        unit=unit,
        value_source=value_source,
        label_source=label_source,
        unit_source=unit_source,
        period_source=period_source,
        method="code+geometry" if used_code else "label+geometry",
        confidence=confidence,
        diagnostics={
            "unit_basis": unit_basis,
            "statement_score": statement_score,
            "primary_statement_score": primary_statement_score,
            "anchor_text": anchor.text,
            "group_count": len(groups),
            "column_basis": column_basis,
        },
    )


def _label_allowed_for_field(spec: FieldSpec, line: OCRLine) -> bool:
    norm = normalize_text(line.text)
    if spec.field_key == "BS_TOTAL_ASSETS_FRGAAP" and any(
        token in norm for token in ("immobilise", "circulant")
    ):
        return False
    return True


def _find_candidates_for_spec(document: DocumentRecord, spec: FieldSpec) -> tuple[list[Candidate], list[Issue]]:
    candidates: list[Candidate] = []
    issues: list[Issue] = []
    for page in document.pages:
        if not page.lines:
            continue
        statement_score = _statement_score(page, spec.statement)
        labels = [
            line
            for line in page.lines
            if _label_allowed_for_field(spec, line) and _label_match_score(line, spec.aliases) >= 20
        ]
        codes = [
            line
            for line in page.lines
            if spec.code is not None and normalize_text(line.text).upper() == spec.code.upper()
        ]

        # Strongest path: code plus a semantically matching label on the same row.
        used_any = False
        for code in codes:
            nearby_labels = [line for line in labels if same_row(code, line) and line.x1 <= code.x1 + 30]
            label = max(nearby_labels, key=lambda l: _label_match_score(l, spec.aliases), default=None)
            if label is None and statement_score < 10:
                continue
            result = _candidate_from_anchor(document, page, spec, code, label, True)
            if isinstance(result, Candidate):
                candidates.append(result)
            else:
                issues.append(result)
            used_any = True

        # Label-only path handles accountant-specific statements and OCR-missed codes.
        for label in labels:
            if statement_score < 10:
                continue
            if any(same_row(label, code) for code in codes):
                continue
            result = _candidate_from_anchor(document, page, spec, label, label, False)
            if isinstance(result, Candidate):
                candidates.append(result)
            else:
                issues.append(result)
            used_any = True

        if (codes or labels) and not used_any and statement_score == 0:
            issues.append(Issue("not_found", "matching text appeared outside a supported statement context", spec.field_key, page.number))
    return candidates, issues


def _deduplicate_candidates(candidates: list[Candidate], field_key: str) -> tuple[Candidate | None, Issue | None, list[Candidate]]:
    if not candidates:
        return None, None, []
    ranked = sorted(
        candidates,
        key=lambda c: (
            c.diagnostics.get("primary_statement_score", 0),
            c.method == "code+geometry",
            c.diagnostics.get("statement_score", 0),
            c.unit_source is not None,
            c.confidence,
            -c.page,
        ),
        reverse=True,
    )
    best = ranked[0]
    equivalent = [c for c in ranked if c.value == best.value and c.unit == best.unit]
    conflicts = [c for c in ranked if c.value != best.value or c.unit != best.unit]
    if conflicts:
        def score(c: Candidate) -> float:
            return (
                2 * float(c.diagnostics.get("primary_statement_score", 0))
                + (20 if c.method == "code+geometry" else 0)
                + float(c.diagnostics.get("statement_score", 0))
                + (4 if c.unit_source is not None else 0)
                + c.confidence * 10
            )
        second = max(conflicts, key=score)
        primary_gap = float(best.diagnostics.get("primary_statement_score", 0)) - float(
            second.diagnostics.get("primary_statement_score", 0)
        )
        if score(best) - score(second) < 15 and primary_gap < 10:
            return None, Issue(
                "candidate_conflict",
                "multiple well-supported sources disagree; abstaining instead of first-match wins",
                field_key,
                details={
                    "candidates": [
                        {"value": str(c.value), "unit": c.unit, "page": c.page, "method": c.method}
                        for c in ranked[:6]
                    ]
                },
            ), ranked
        best.diagnostics["disagreeing_sources"] = [
            {"page": c.page, "value": str(c.value), "unit": c.unit, "snippet": c.snippet, "method": c.method}
            for c in conflicts[:5]
        ]
    best.diagnostics["equivalent_sources"] = [
        {"page": c.page, "snippet": c.snippet, "method": c.method}
        for c in equivalent[1:]
    ]
    return best, None, ranked


def extract_document(document: DocumentRecord) -> tuple[list[Candidate], list[Issue], dict[str, list[Candidate]]]:
    accepted: list[Candidate] = []
    issues: list[Issue] = []
    all_candidates: dict[str, list[Candidate]] = {}

    for spec in FIELD_SPECS:
        candidates, local_issues = _find_candidates_for_spec(document, spec)
        all_candidates[spec.field_key] = candidates
        chosen, conflict, _ = _deduplicate_candidates(candidates, spec.field_key)
        if chosen is not None:
            accepted.append(chosen)
        elif conflict is not None:
            issues.append(conflict)
        else:
            if not any(page.lines for page in document.pages):
                issues.append(Issue("ocr_empty", "document has no OCR text", spec.field_key))
            elif not any(_statement_score(page, spec.statement) >= 10 for page in document.pages):
                issues.append(
                    Issue(
                        "source_absent",
                        f"no supported {spec.statement} statement was found in the filing",
                        spec.field_key,
                    )
                )
            else:
                issues.append(Issue("not_found", "supported statement exists but no defensible candidate was found", spec.field_key))
        # Keep only meaningful local issues to avoid flooding review.json.
        issues.extend(issue for issue in local_issues if issue.status in {"unit_ambiguous", "period_ambiguous"})

    for field_key in sorted(DEFERRED_FIELDS):
        issues.append(Issue("definition_unresolved", "field intentionally deferred because the supplied catalogue is semantically ambiguous", field_key))
    for field_key in sorted(P1_FIELDS):
        issues.append(Issue("not_implemented", "P1 field not enabled in the deterministic MVP", field_key))

    accepted.sort(key=lambda c: c.field_key)
    return accepted, issues, all_candidates


def iter_field_specs() -> Iterable[FieldSpec]:
    return iter(FIELD_SPECS)
