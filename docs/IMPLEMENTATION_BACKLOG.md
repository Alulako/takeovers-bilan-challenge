# Implementation backlog and interview preparation

Status: executable plan, not completed implementation. Read [TECHNICAL_PLAN.md](TECHNICAL_PLAN.md) and [FIELD_MATRIX.md](FIELD_MATRIX.md) first. All file paths below are relative to the proposed candidate repository root, the current workspace folder.

## Delivery discipline and time box

- Implement one task at a time. Each handoff includes the task ID, dependencies, permitted files and acceptance criteria. Review the diff and evidence before marking it done.
- The tasks are independently assignable **after their dependencies are complete**; this is not a request to implement them concurrently.
- Use the supplied files through the data-root option. Do not modify OCR/PDF sources, weaken the official schema, read gold fixtures from production code, or fabricate missing amounts/units/boxes.
- Follow the matrix. No task enables COGS, capital/reserves, cash/VMP or depreciation/provisions by guessing a definition.
- Keep a simple actual-time ledger. The budgets below are estimates and include a notional 30 minutes for discovery; the actual planning/learning time already spent must replace that estimate. Reduce feature scope if the total exceeds the challenge's budget. Do not claim that AI-assisted discovery consumed no time.

| Work | Planned minutes |
|---|---:|
| M0 discovery/design checkpoint | 30 |
| T01–T14 mandatory implementation/verification/reporting | 335 |
| T15–T16 optional personnel/workforce | 35 |
| Contingency and final review | 80 |
| **Maximum envelope** | **480 (8 hours)** |

The mandatory route plus discovery is approximately 6 hours 5 minutes before contingency. At hour six stop adding fields. If the schedule slips, drop T15/T16 and narrow difficult layout recovery before cutting provenance, schema validation, measurement or disclosure. The current comprehensive planning package is preparation; do not mechanically spend another 30 minutes rediscovering verified facts.

## Milestones

| Milestone | Objective | Acceptance criteria | Tasks |
|---|---|---|---|
| M0 — Understand the inputs | Establish actual scope and risks | Audit commit, 15 IDs/415 pages, schema gaps, mixed units and definition conflicts recorded | Completed at stated audit depth |
| M1 — Reproducible skeleton | One installable local package | Clean install, help command, original contracts preserved, ignored data/secrets | T01–T02 |
| M2 — First supported field | Extract total assets end to end | CREAMANDE 2022 current-year net asset amount, unit, date, page and genuine bbox serialize correctly | T03–T07 |
| M3 — Provenance verified | Trust the coordinate convention | Candidate overlays agree on ordinary, skewed, PDF-rotated and two-up pages; unsupported cases explicitly rejected | T03, T07 |
| M4 — Six-field scope | Extend without losing evidence | Six P0 field types attempted wherever supported; every accepted candidate carries context | T08–T09 |
| M5 — Visible validation | Make problems reviewable | Duplicate and omission reasons; passif and available same-period comparisons retain evidence | T08, T10–T11 |
| M6 — Measured run | Make cost/speed reproducible | Timers/counters agree, explicit denominator, zero actual extraction API calls, final payload validates | T12 |
| M7 — Full-scope partial-coverage result | Attempt the full allowlist | 15 document statuses; no silent drops; reviewed-sample results and real coverage counts; failures disclosed | T13 |
| M8 — Coherent README | Tell the engineering story | Run commands tested, measured values filled, limitations and AI usage truthful | T14 |
| M9 — Demo/interview ready | Candidate explains choices | Approximately three-minute recording prepared; actual candidate recording/link still requires the candidate's participation | T14 |

M2 must precede expanding extraction. M7 means a complete accounting of input documents, not a claim that all 180 target opportunities were extracted.

## Ordered implementation tasks

### T01 — Establish the package and preserve the external contract

**Priority/budget/complexity:** P0, 10 minutes, low.

**Objective:** create only the minimal Python package/configuration needed to run future work.

**Files affected:** `pyproject.toml`, `requirements.lock`, `.gitignore`, `.env.example`, `src/bilan/__init__.py`, `src/bilan/__main__.py`, `schema/financial_fields.json`, `schema/results.schema.json`, `tools/bbox_viewer.py`, initial README setup section.

**Dependencies:** M0. Verify no user files would be overwritten.

**Implementation boundary:** copy the two schemas and viewer unchanged from the pinned reference; attribute them. Configure PyMuPDF/jsonschema, viewer Pillow and development pytest; resolve exact versions. Package initialization has no I/O or side effects. The runner initially exposes help only. Initialize candidate Git history locally with the reference clone/data excluded; publication is a later action.

**Definition of done:** clean environment installs the package; the proposed module entry point displays usage; vendored hashes match upstream; no secrets or corpus are tracked; `.env.example` accurately states that no application environment variables are read.

**How to test:** clean install plus `python -m bilan --help`; compare vendored file hashes and inspect Git status. No invented placeholder results.

**Interview takeaway:** “Reproducibility starts with preserving the input contract and making setup boring.”

### T02 — Implement the exact manifest and read-only loader

**Priority/budget/complexity:** P0, 20 minutes, low-medium.

**Objective:** load only the 15 target documents with identity, geometry and original OCR references intact.

**Files affected:** `scope.json`, `src/bilan/models.py`, `src/bilan/inputs.py`, `tests/test_contract.py`.

**Dependencies:** T01; audited inventory in the technical plan.

**Implementation boundary:** define small dataclasses for document/page/source/candidate/issue as needed, not a framework. Manifest paths use the actual shipped naming scheme. Match metadata `id`/`siren`, retain `dateCloture`, parse physical page numbers and PDF displayed dimensions. Preserve `ocr`, layout and extra diagnostic keys. Do not treat registry `nomDocument` or OCR `pdf` as local filenames. Hash source inputs for later run traceability.

**Definition of done:** expected 15 PDFs, 15 metadata files and 415 page JSONs are inventoried; 41 empty OCR records are valid observations, not crashes. Missing/mismatched inputs produce clear errors/statuses; the loader does not recurse through all companies during extraction. Freeze the five development filings and approximately 30 field/document review opportunities from the evaluation plan before tuning; reference labels must be read from PDFs independently of extractor output.

**How to test:** positive scope smoke check; minimal wrong-SIREN, duplicate-ID, page-mismatch and missing-file cases. Preserve null metadata values and raw OCR text.

**Interview takeaway:** “I separate the deposit identity from the financial period.”

### T03 — Implement bbox normalization and working-coordinate transforms

**Priority/budget/complexity:** P0, 25 minutes, medium.

**Objective:** establish trustworthy geometry before field extraction.

**Files affected:** `src/bilan/geometry.py`, `tests/test_geometry.py`, small source references in `tests/fixtures/reviewed.json` if manually confirmed.

**Dependencies:** T02.

**Implementation boundary:** implement polygon envelopes and 300-dpi normalization against displayed page dimensions. Reuse the viewer formula; keep the viewer unchanged. Add explicit invertible working transforms for supported orientations and region offsets; preserve original polygons. Treat orientation codes as categorical until corroborated, not degrees.

**Definition of done:** valid boxes are finite, ordered and bounded; incorrect geometry fails. PDF `/Rotate=270` is not applied twice. A sideways scan can be matched in a working frame while its final bbox remains on the original physical page. If an orientation is unsupported, return a review issue.

**How to test:** synthetic hand-calculated rectangle; comparison with the viewer; real CREAMANDE 2025 p2 and BOCKEL 2023 p9. Render an overlay for each plus PAUTET 2021 p6. Test transform round trips without replacing visual checks.

**Interview takeaway:** “I change the coordinate system used to search, never the coordinates of the evidence.”

### T04 — Implement conservative numeric parsing

**Priority/budget/complexity:** P0, 20 minutes, medium.

**Objective:** preserve printed magnitude, precision and sign while rejecting ambiguity.

**Files affected:** `src/bilan/extract.py`, `tests/test_extract.py`.

**Dependencies:** T02.

**Implementation boundary:** use decimal arithmetic internally. Handle ordinary/nonbreaking/narrow spaces, comma decimals, unambiguous grouped dots, observed dot decimals, parentheses and leading/trailing minus. Keep raw text and parsing method. A separator pattern must have a justified interpretation; do not indiscriminately strip dots/commas or substitute letters in numbers.

**Definition of done:** explicit `0` returns zero; blank and lone dash return missing/ambiguous; `(2 778)` and `111 724.81-` retain negative signs. Ambiguous `1.234` without sufficient formatting context is not silently forced to one interpretation. A merged multi-number OCR line does not become one concatenated number.

**How to test:** parameterized representative number cases plus ambiguous tokens and split sign/value spans. An accounting equality is not used as a parser oracle.

**Interview takeaway:** “A parse failure is safer than a plausible thousand-fold or sign error.”

### T05 — Implement unit evidence and scope resolution

**Priority/budget/complexity:** P0, 25 minutes, medium.

**Objective:** distinguish explicit and inferred EUR/kEUR evidence without contaminating unrelated regions.

**Files affected:** `src/bilan/models.py`, `src/bilan/extract.py`, `tests/test_extract.py`.

**Dependencies:** T02, T04; geometry references from T03.

**Implementation boundary:** collect unit cues and their original references; resolve field/table/page/statement-packet scope. Implement precedence and conflict handling. Keep a separate applicability decision for entity/period. Numeric corroboration can confirm a scale only when a uniquely matching same-period statement amount is explicitly denominated in a note.

**Definition of done:** BERNACHON's subsidiaries kEUR table does not alter the main EUR accounts; a euro reference in a capital-letterhead does not establish a document-wide unit. Unknown or conflicting unit evidence creates an omission reason. Workforce is prepared to use `count` without monetary inheritance.

**How to test:** mixed-unit local override, incompatible subsidiary entity, conflicting same-scope cues, count on monetary page and absence of evidence. Include source references to BERNACHON 2021 pp6/11.

**Interview takeaway:** “Units are scoped evidence, not a company attribute.”

### T06 — Detect statement regions and current-period columns

**Priority/budget/complexity:** P0, 35 minutes, medium-high; time-box strictly.

**Objective:** supply extraction with a region, statement type, company context and labelled columns.

**Files affected:** `src/bilan/extract.py`, `src/bilan/models.py`, `tests/test_regression.py`.

**Dependencies:** T02–T05.

**Implementation boundary:** use statement heading aliases and code clusters, with date/column evidence. Support standard forms and ordinary accountant statements. Use median text height/local baseline to associate rows in skewed input. Cells are optional constraints, not trusted row-indexed data. Do not concatenate layout text with flat OCR; surface their disagreements.

**Definition of done:** distinguish actif/passif/P&L/notes; identify net N vs gross/deductions/N-1; support multiple regions on BOCKEL p9 or explicitly flag unsupported regions. Recognize tables with no N-1 column. Confirm metadata close against headers; reject contradictory current-period identification. No fixed PDF page assumptions.

**How to test:** one standard grid, PAUTET accountant layout, ordinary BOCKEL statement, two-up page and subsidiary note as a negative case. Verify matching survives empty layout.

**Interview takeaway:** “I locate the financial statement before looking for the field.”

### T07 — Extract total assets end to end with real provenance

**Priority/budget/complexity:** P0, 25 minutes, medium.

**Objective:** complete a vertical slice before adding more fields.

**Files affected:** `src/bilan/extract.py`, `src/bilan/checks.py`, `src/bilan/__main__.py`, `tests/test_contract.py`, `tests/test_regression.py`.

**Dependencies:** T01–T06.

**Implementation boundary:** match the full asset total and current-year net column; build an accepted field through a validating factory. Add a first working CLI run and schema-valid serialization with basic genuine timing/counters. Preserve label, unit, period and value sources. Do not output gross CO-adjacent amounts.

**Definition of done:** one CREAMANDE 2022 document yields a verified total-assets record with correct identity/date/unit/page/box. Then exercise PAUTET and the rotated 2025 example. Exact values must be checked from sources during implementation, not inferred from this task's wording.

**How to test:** original JSON Schema plus semantic checks; viewer `--grep` comparison and red-box render of the chosen numeric span. Demonstrate a rejected gross-column candidate.

**Interview takeaway:** “The first field proves the entire evidence path, not just a regex.”

### T08 — Add equity and an independent balance-sheet check

**Priority/budget/complexity:** P0, 20 minutes, medium.

**Objective:** extend the asset slice to equity and full-passif reconciliation.

**Files affected:** `src/bilan/extract.py`, `src/bilan/checks.py`, `tests/test_regression.py`.

**Dependencies:** T07.

**Implementation boundary:** implement total capitaux propres/DL; independently read full passif/EE as a validation-only operand. On ordinary statements distinguish `situation nette` from total equity; do not invent a component total if the scope is unclear.

**Definition of done:** equity is distinct from full passif; assets/passif differences and reporting-precision tolerances are logged with both sources. Printed values are never repaired to force agreement.

**How to test:** correct reconciliation, one-unit rounding discrepancy, partial-passif trap, negative equity and a net-position subtotal that is not demonstrably total equity.

**Interview takeaway:** “An independent total helps detect errors without becoming a replacement for evidence.”

### T09 — Add the four direct P&L field rules

**Priority/budget/complexity:** P0, 35 minutes, medium.

**Objective:** implement revenue, external services, financial result and income tax using the established mechanics.

**Files affected:** `src/bilan/extract.py`, `tests/test_regression.py`, `tests/fixtures/reviewed.json` after human review.

**Dependencies:** T07; use T08's check pattern where applicable.

**Implementation boundary:** FL/net turnover, FW, GV and HK; preserve signs. Each rule is an explicit field specification with limited aliases. Permit an equivalent same-document statement; a clear same-period narrative is a bounded fallback. Do not derive missing fields from total products, profit or a guessed tax rate.

**Definition of done:** all six P0 field types can be attempted. Missing/unpublished P&L in PAUTET or CREAMANDE 2025 yields reasons, not fabricated amounts. A 2057 tax-payable row is not income-tax expense.

**How to test:** revenue total vs France/export, financial loss, tax expense vs debt and omitted statement. Review representative BERNACHON, SO.ME.PROD and BOCKEL P&L pages.

**Interview takeaway:** “The reusable part is spatial matching; the financial definitions remain explicit.”

### T10 — Make abstention, duplicates and input disagreements explicit

**Priority/budget/complexity:** P0, 15 minutes, low-medium.

**Objective:** prevent a successful-looking output from hiding uncertainty.

**Files affected:** `src/bilan/checks.py`, `src/bilan/__main__.py`, `tests/test_contract.py`.

**Dependencies:** T08–T09.

**Implementation boundary:** produce `review.json` with per-document/per-field statuses: `not_implemented`, `not_found`, `source_absent`, `ocr_empty`, `unit_ambiguous`, `period_ambiguous`, `candidate_conflict`, `definition_unresolved`, `invalid_bbox`, `missing_component` as applicable. `source_absent` requires evidence of absence; use `not_found` when only the extractor failed to find it.

**Definition of done:** one accepted field per document/key; equivalent duplicate sources are retained with a deterministic source preference; conflicting candidates are not resolved by “first match wins.” State a source preference such as clear primary statement then complete alternate statement then explicit note, always requiring matching scope. The absence of numerical confidence does not hide missing evidence.

**How to test:** agreeing duplicates, disagreeing duplicates, same number/different unit, same number/different period, an input failure and an empty field list. Inspect status counts manually.

**Interview takeaway:** “Every gap has a reason, so coverage is auditable.”

### T11 — Add date-aware comparative checks

**Priority/budget/complexity:** P0, 20 minutes, medium.

**Objective:** compare only observations that actually describe the same exercise.

**Files affected:** `src/bilan/checks.py`, `tests/test_regression.py`.

**Dependencies:** T06, T08–T10.

**Implementation boundary:** retain comparative observations as validation evidence, separate from output fields. Join SIREN/field/period/basis/unit-converted amount; check period length when present for P&L. Skip missing years and absent comparative columns. Record both sources and exact deltas/tolerances.

**Definition of done:** PAUTET 2021-to-2022 available balance-sheet comparisons can be attempted; SO.ME.PROD 2017-to-2020 and CREAMANDE 2023-to-2025 are not blindly paired as adjacent exercises. No value is overwritten by a comparative observation.

**How to test:** real date gaps, same-period EUR/kEUR comparison, different duration, unavailable N-1 and a discrepant restatement. Report attempted, passed, failed and not-comparable counts separately.

**Interview takeaway:** “I compare accounting periods, not filename years.”

### T12 — Finish instrumentation and guaranteed-valid export

**Priority/budget/complexity:** P0, 20 minutes, medium.

**Objective:** produce reproducible measured metrics and a valid final result artifact.

**Files affected:** `src/bilan/__main__.py`, `src/bilan/checks.py`, `tests/test_contract.py`, generated `results.json` and `review.json`.

**Dependencies:** T10–T11; extends the real minimal timing/export from T07.

**Implementation boundary:** measure read/extraction/document/global stages, counters and total wall time; document the timing boundary and any excluded final metrics bookkeeping. If a final rewrite is needed to include the completed write timing, disclose that tiny bookkeeping exclusion rather than implying impossible self-timing. Validate schema and application invariants before replacing the output file.

**Definition of done:** per-page denominators match actual inspected physical pages; full scope is 415, not just pages with accepted fields. Record zero actual extraction calls/tokens/cost, not an estimated economic cost of local compute. Preserve machine/runtime/command/source/code information. A failed input does not get counted as successfully processed without a status.

**How to test:** fake-clock/counter tests for accounting, real run for wall time, invalid payload rejected without replacing a valid existing result, repeated deterministic extraction payload excluding timing metadata. Include serialization and validation overhead in the reported boundary.

**Interview takeaway:** “The cost claim is reproducible because the boundary and denominator are explicit.”

### T13 — Run all documents and evaluate a disclosed reference sample

**Priority/budget/complexity:** P0, 40 minutes, medium; reduce the sample honestly if review takes longer.

**Objective:** create final measured output and evidence-based evaluation.

**Files affected:** `tests/fixtures/reviewed.json`, `tests/test_regression.py`, `results.json`, `review.json`, README evaluation/limitations sections.

**Dependencies:** T12. Reference selection should be frozen before tuning at T06–T09; reviewed labels are built alongside those tasks, not back-filled from output here.

**Implementation boundary:** attempt all 15 documents; review approximately 30 preselected opportunities and up to 15 additional held-out opportunities if feasible. Candidate verifies reference values/units/pages from PDFs. Keep unresolved labels separate. Run schema/semantic checks and selected source-box overlays.

**Definition of done:** 15 explicit document outcomes, coverage per field/company, reviewed numeric and grounded correctness with numerators/denominators, false emissions and missed available values. Record which items the candidate actually reviewed and distinguish AI assistance. No fake 100% claim from schema or balance-sheet success.

**How to test:** execute the focused suite and full run; verify tally denominators against fixtures and emitted results; manually inspect at least the key mixed-unit, wrong-column and rotation cases. Every material failure becomes a limitation or a justified fix; do not spend remaining time broadening architecture.

**Interview takeaway:** “My evaluation makes a limited claim backed by inspectable cases.”

### T14 — Complete README, AI disclosure and demo preparation

**Priority/budget/complexity:** P0, 25 minutes, low-medium.

**Objective:** make the submission easy to reproduce and defend.

**Files affected:** `README.md`, `.env.example`, relevant planning decisions; actual demo link once recorded.

**Dependencies:** T13.

**Implementation boundary:** follow the README outline in the technical plan. Put measured values and exact run commands in the README; describe unsupported fields and the four definition conflicts. Update AI usage with actual work and candidate verification. Prepare the demo flow below. The candidate records their own explanation; no agent should claim to have recorded their voice or verified their understanding.

**Definition of done:** documented setup/run/test commands work from a clean environment; API cost exclusions and timing denominators are clear; results root path is correct; no unused API variables or real secrets; demo link is real once supplied. Prepare a PR to the candidate's own repository and reviewer checklist, but do not create/send external invitations as part of this planning task.

**How to test:** reproduce from README, inspect tracked files, check all local links, compare prose numbers with run/review artifacts; rehearse the three-minute narrative.

**Interview takeaway:** “The README explains the engineering choices and the remaining uncertainty.”

### T15 — Optional: add same-page personnel-cost derivation

**Priority/budget/complexity:** P1, 20 minutes, medium.

**Objective:** demonstrate derived provenance with a clear definition, FY + FZ.

**Files affected:** `src/bilan/extract.py`, `src/bilan/checks.py`, `tests/test_extract.py`, `tests/test_contract.py`.

**Dependencies:** P0 route complete; T04 numeric arithmetic and T03 geometry.

**Implementation boundary:** require both current-year operands and same unit/page; output formula, each source, and a truthful enclosing parent box. Do not treat blank wages/social charges as zero.

**Definition of done:** recomputable personnel sum with component provenance, or explicit `missing_component`; no cross-page parent-box fiction. Rerun affected tests and full output/evaluation after adding the field.

**How to test:** signed values, explicit zero, missing component, mixed units, split-page rejection, all component boxes visible in viewer.

**Interview takeaway:** “A derived metric is reproducible arithmetic over individually grounded inputs.”

### T16 — Optional: add explicit average workforce

**Priority/budget/complexity:** P1, 15 minutes, low-medium.

**Objective:** correctly handle the nonmonetary field using explicit average-workforce evidence.

**Files affected:** `src/bilan/extract.py`, `src/bilan/checks.py`, `tests/test_regression.py`.

**Dependencies:** P0 route complete; may follow T15 as the default order.

**Implementation boundary:** match the explicit average on 2058-C/2059-E or notes. Use `count`, allow fractional averages, reject unrelated headcounts and subsidiary staff.

**Definition of done:** verified source record on a representative SO.ME.PROD or BERNACHON filing, correct count unit and omissions where absent. Refresh affected results/metrics/evaluation and README; do not reuse stale benchmark numbers after new work.

**How to test:** older/newer form location, count on euro-denominated page, average vs year-end count, apprentices/CVAE-specific subpopulation rejected.

**Interview takeaway:** “Field meaning controls the unit; the page footer does not.”

### T17 — Deferred: resolve ambiguous definitions before extending coverage

**Priority/budget/complexity:** P2, no allocation in the 6–8-hour core; medium semantic complexity.

**Objective:** settle one of the four disputed definitions with documented authority before changing output.

**Files affected:** field matrix and decision log first; `extract.py` and appropriate tests only after resolution.

**Dependencies:** complete P0 delivery. Read the specific catalogue conflict and source rows.

**Definition of done:** the accepted interpretation, alternatives, formula/signs, source of the decision and consequences are written down. If clarification is unavailable, the field stays omitted; a model's opinion is not adjudication.

**How to test:** use an example where competing definitions produce different numbers; ensure the selected meaning, unit and operands are explicit. A case where VMP happens to be zero is insufficient to settle cash semantics.

**Interview takeaway:** “I distinguish uncertainty in reading the document from uncertainty in the requested definition.”

### T18 — Deferred: measure a bounded model fallback experiment

**Priority/budget/complexity:** P2, separate experiment; high relative to take-home scope.

**Objective:** test whether a specific model materially improves a diagnosed error category.

**Files affected:** a small optional experiment script, isolated fixtures, README experiment results and blank environment-variable names only if actually used. Do not add an SDK to the core runtime merely to reserve an option.

**Dependencies:** a frozen, manually reviewed error subset and baseline from T13; provider/model selection and current published pricing at experiment time.

**Definition of done:** real baseline/fallback agreement, coverage, call/token/cost and latency deltas on the same subset; all generated values independently grounded in actual source text/image. Retries and failures count. No model boxes or answers are trusted simply because they parse as JSON.

**How to test:** include rejected/ambiguous responses and a no-evidence crop; verify no output is accepted without valid source references. Publish no improvement claim unless observed.

**Interview takeaway:** “I would add model complexity only after measuring what it buys.”

## Interview questions and suggested answers

These are rehearsal answers for the planned design. Replace future tense and insert measured numbers only after implementation and candidate review.

| Question | Concise answer |
|---|---|
| Why use the supplied OCR? | “It lets me focus on the challenge's central problem: mapping noisy text into correctly scoped financial facts. Replacing OCR would consume time and introduce another error source. I still inspect the PDF when the reading is questionable.” |
| Why not use an LLM for every page? | “Most operations are deterministic: units, column selection, arithmetic and coordinates. A model adds cost and nondeterminism without guaranteed provenance. I would first measure whether it improves a specific failure category.” |
| Why not trust the detected tables? | “The cells have geometry and text, but no dependable row/column indices. I also found text disagreements at identical polygons. I use flat OCR for text and table structure as supporting evidence.” |
| How do you handle OCR mistakes? | “I keep raw readings, reject ambiguous numbers, compare independent statement evidence and inspect important failures. I do not change digits just to make an accounting identity pass.” |
| What is the hardest layout issue? | “The same page can contain two sideways statements, while another PDF uses a rotation flag but renders upright. I separate working coordinates from the original source coordinates and test both.” |
| How do you distinguish EUR and kEUR? | “I resolve the most specific applicable unit evidence. In BERNACHON, a subsidiary table is in kEUR while the main accounts use EUR. A document-wide flag would give incorrect numbers.” |
| What if no unit is stated? | “I look for an explicit statement-packet default or a uniquely matching same-period amount with a currency in the notes. If the scale remains unsupported, I omit the value and state why.” |
| How do you know a bbox is correct? | “I use the original OCR polygon and actual displayed PDF dimensions. Then I render the supplied viewer overlay and verify the number, row and column. Bounds checking alone is not enough.” |
| Why is total-assets extraction not just code CO? | “CO identifies the row, but the row may contain gross assets, deductions and net assets. I need the net current-period column and then compare it with the full passif.” |
| How do you ground a derived field? | “I retain the signed operands, units, individual boxes and formula. A same-page enclosing box points to the inputs; I explicitly mark that the result is derived.” |
| Why defer COGS? | “The catalogue does not settle the sign of production-stock changes in its formula. I prefer to report a definition gap than silently output a different metric.” |
| Why not fill all twelve fields? | “Some statements are unavailable and some field definitions conflict. The challenge explicitly prioritizes correctness. I deliver the supported fields and make the coverage gap measurable.” |
| Are missing and zero the same? | “No. Zero is accepted when it is printed. Missing or unreadable evidence is an omission with a reason.” |
| What does schema validation prove? | “That the JSON has the required shape and allowed types. It does not prove that a key is one of the twelve, that a box is ordered, or that the period and unit are correct. I add those semantic checks.” |
| How do you validate without ground truth? | “I create a small disclosed reference set from the PDFs, report agreement and coverage on that sample, and use accounting and cross-filing checks as additional evidence. I do not label consistency as accuracy.” |
| Can reconciliation miss errors? | “Yes. A shared unit error can affect both sides equally. That is why I separately verify unit evidence and source locations.” |
| How do you compare N and N-1? | “I join the actual date represented by each column, not deposit dates. I also check the accounting scope and period length. Missing years are non-comparable.” |
| Can the documents disagree? | “Yes. The audited BERNACHON balance sheet and notes differ by one euro. I preserve the statement reading and flag the difference rather than silently choosing a preferred truth.” |
| Is your system free? | “Its incremental extraction API cost is zero with provided OCR and local rules. Upstream OCR, compute and human review are separate and are not priced by that claim.” |
| What is a page in your benchmark? | “A physical PDF page whose OCR record the run inspects. Full scope is 415, including empty pages. I also report nonempty and extraction-page counts, with their own definitions.” |
| Why this repository structure? | “It separates input integrity, geometry, extraction and validation while keeping one command and a small dependency graph. More layers would not improve this submission.” |
| How reproducible is it? | “The inputs, dependencies, code revision and run command are recorded. With fixed inputs the extracted payload should be identical; timing metadata naturally varies.” |
| What did AI do? | “AI helped with repository inspection and planning. I will disclose coding and debugging help if used. I must personally review decisions and representative source values before claiming that I verified them.” |
| What would you do with another week? | “First resolve the field-definition conflicts and expand the independent evaluation set. Then classify the remaining errors and compare targeted OCR or model recovery against the deterministic baseline, including cost.” |
| What would you improve for production? | “A larger adjudicated corpus, versioned extraction rules, automated source-review workflows and monitoring of failure categories. I would add infrastructure only when volume and operating requirements justify it.” |

## Three-minute demo outline

- **0:00–0:25 — Problem and scope:** six reliable fields first, all 15 inputs attempted, 12-field catalogue and explicit omissions.
- **0:25–0:55 — Real data finding:** show mixed-unit evidence or a missing P&L; explain why the initial assumptions needed revision.
- **0:55–1:35 — One grounded value:** run the CLI or show its measured output; open a selected source in the supplied bbox viewer; explain net N versus gross/N-1.
- **1:35–2:05 — One meaningful failure/check:** show a unit/definition omission or a reconciliation discrepancy with both sources.
- **2:05–2:35 — Evaluation and performance:** actual sample denominator, actual coverage, measured runtime and zero incremental API cost with exclusions.
- **2:35–3:00 — Trade-offs and ownership:** what was cut, how AI helped, what the candidate verified and the first improvement with more time.

Do not spend the video scrolling through every module. Show evidence and decisions. The implementation may eventually reveal a better demonstration case; use the actual final result.

## Submission preparation checklist

This checklist is for the later implementation/submission phase, not authorization to publish now.

- Candidate-owned repository; root `results.json` validates against the Bilan schema.
- Corpus/reference clone and `.env` excluded; supplied tool/schemas attributed.
- README run instructions tested; measured claims match artifacts.
- AI usage, unsupported definitions, missing values and validation limits disclosed.
- `.env.example` contains names with blank values only for variables actually read; no keys required in the MVP.
- Approximately three-minute recording linked after the candidate records it.
- PR against the candidate's own repository; the requested reviewers are `@YassineBouderbala` and `@AleBastos25`. Sending invitations/publishing the PR is a later explicitly requested action.

## START HERE

1. **T01 — Establish the package and preserve the external contract.** Deliver install/help, pinned dependencies and unchanged schemas/viewer.
2. **T02 — Implement the exact manifest and read-only loader.** Deliver 15 joined documents and a 415-page inventory with explicit empty/missing statuses.
3. **T03 — Implement bbox normalization and working-coordinate transforms.** Deliver tested geometry and inspectable overlays before extracting financial fields.
