# BILAN field extraction matrix

Status: planning, based on upstream commit `a705bcc86614c8552cc4270c762a6a6399c751ba`. No production extractor or results have been implemented.

The authoritative field identifiers and labels below come from `challenge-reference/challenges/bilan/schema/financial_fields.json`. The catalogue is internally inconsistent for several fields. Those inconsistencies must remain visible; a plausible accounting interpretation is not proof of the evaluator's intended definition.

## Shared extraction contract

- Extract the filing company's current exercise, established using metadata `dateCloture` and statement headers. The deposit date, subsidiary accounts and comparative columns are different contexts.
- Preserve the printed sign and reporting scale. All fields except workforce are monetary: output `EUR` or `kEUR` from scoped evidence. Workforce uses `count`, including fractional averages if printed.
- Prefer an explicitly printed total. Find its label/code, statement region and current-period column before selecting the number. A code alone is insufficient.
- Preserve raw OCR text and original polygons. Use a box around the value's supporting OCR span; keep the label, period and unit evidence separately.
- Empty cells, dashes, missing pages and unsupported definitions are not zero. Omit unresolved fields, with a reason in the review report. An explicit printed `0` is a value.
- Alternative statements and notes are fallback sources only when entity, period, accounting concept and unit match. Do not silently repair a value from another filing.
- Codes below are anchors on the usual forms, not fixed coordinates or assumed positions. Official form references corroborate the mappings, but older and accountant-specific layouts in this corpus need their own label/column evidence.

## At a glance

| Field key | Exact English label | Exact French label | Usual location / anchor | Nature | Priority |
|---|---|---|---|---|---|
| `PL_REVENUE_FRGAAP` | Net revenue | Montant net du chiffre d'affaires | 2052 / FL, or accountant P&L | Direct total | P0 |
| `PL_COGS_FRGAAP` | Cost of goods sold | Achats marchandises + matières + variations stocks + production stockée | 2052 / FS, FT, FU, FV, FM | Derived; sign convention unresolved | P2 |
| `PL_PERSONNEL_COSTS_FRGAAP` | Personnel costs | Salaires + charges sociales | 2052 / FY, FZ | Usually derived | P1 |
| `PL_EXT_SERVICES_COSTS_FRGAAP` | External services & subcontracting | Autres achats et charges externes (FW) | 2052 / FW | Direct | P0 |
| `PL_DEPRECIATION_AMORTIZATION_FRGAAP` | Depreciation & amortization | Dotations d'exploitation (amort. + prov.) | 2052 / GA through GD | Definition-dependent | P2 |
| `PL_FINANCIAL_RESULTS_FRGAAP` | Net financial result | Résultat financier (V - VI) | 2052 / GV | Direct; possible GP minus GU fallback | P0 |
| `PL_INCOME_TAX_FRGAAP` | Corporate income tax | Impôts sur les bénéfices | 2053 / HK | Direct | P0 |
| `BS_TOTAL_ASSETS_FRGAAP` | Total assets | Total général actif | 2050 / TOTAL GENERAL row (CO anchor), **net N column** | Direct | P0; first field |
| `BS_TOTAL_EQUITY_FRGAAP` | Total equity | Total des capitaux propres | 2051 / DL, TOTAL (I) | Direct | P0 |
| `BS_CAPITAL_EQUITY_FRGAAP` | Share capital & reserves | Capital social + primes + réserves | 2051 / DA, DB, DD-DG depending on definition | Definition-dependent | P2 |
| `BS_CASH_CURRENT_ASSET_FRGAAP` | Cash and cash equivalents | Disponibilités + VMP | 2050 / CF and possibly CD, net N | Definition-dependent | P2 |
| `META_AVG_WORKFORCE_FRGAAP` | Average number of employees | Effectif moyen du personnel | 2058-C in older forms; 2059-E and notes also observed / YP | Direct count | P1 |

## Field specifications

### 1. PL_REVENUE_FRGAAP

**Strategy:** match net turnover / `Chiffres d'affaires nets`, using FL in the 2052 total column. Reject France-only FJ, export FK, individual sales categories, total operating income and percentage-change columns. On ordinary P&Ls, identify the net turnover row and the current exercise date.

**Validation:** if all relevant operands are explicitly available, compare total with domestic plus export, allowing documented rounding. This is supporting evidence, not a requirement to find every component. Negative or very unusual revenue prompts review rather than automatic sign correction.

**Ambiguities/fallback:** notes and management reports repeat turnover, sometimes for previous years or subsidiaries. Accept a narrative fallback only with explicit entity, period, number and currency. Do not reconstruct turnover from `total produits`. PAUTET's available accounts summarize total products without necessarily exposing net turnover.

**Provenance/unit:** direct number span, statement-wide monetary unit with its own evidence. A narrative reading retains the full supporting OCR line if it combines text and number.

### 2. PL_COGS_FRGAAP

**Strategy if enabled:** independently extract purchases of goods (FS), goods inventory change (FT), purchases of materials (FU), materials inventory change (FV), and stocked production (FM). Require the same entity, exercise, accounting basis and unit for all operands.

**Semantic decision still required:** purchased-stock changes are expense-side amounts; production stock changes are income-side amounts. A consumption-style convention could be `FS + FT + FU + FV - FM`, using each printed signed value. However, the catalogue's French label joins production stock with a plus sign and supplies no explicit equation. A literal-plus implementation would differ. Neither is safely established as the required challenge definition. Do not silently choose either or include immobilized production FN.

**Validation:** retain a versioned formula and every operand; recompute with decimal arithmetic; reject partial sums and mixed units/periods. A blank input is unknown, not zero. Same-page sources can share an enclosing parent box, with individual component boxes.

**Fallback:** omit with `definition_unresolved` until the definition is settled; then omit with `missing_component` where evidence is insufficient. This is explicitly outside the MVP. It is not a printed line, and a box must never imply that the derived number itself appears on the page.

### 3. PL_PERSONNEL_COSTS_FRGAAP

**Strategy:** FY wages and salaries plus FZ social charges, preserving printed signs. A printed combined personnel-cost total can be used only if its definition clearly includes both and excludes other costs.

**Validation:** both operands required, same exercise/unit, exact decimal sum before serialization. Do not add a personnel subtotal to its own components. Check signs, but do not force positivity when the document prints a negative adjustment.

**Ambiguities/fallback:** external personnel and subcontracting can sit under FW; they are not automatically part of this definition. If either FY or FZ is blank, do not assume zero. Prefer another explicit equivalent statement in the same document, otherwise omit.

**Provenance/unit:** derived monetary field; component sources and `derivation` are mandatory extensions. P1 is intentionally the first derived-field use case because its definition is substantially clearer than COGS.

### 4. PL_EXT_SERVICES_COSTS_FRGAAP

**Strategy:** match FW and its full label, or the corresponding accountant P&L row. Select the total external charges, not an individual rent, subcontracting or purchased-service line.

**Validation:** confirm expense statement and current-period column; preserve printed sign. Where a 2058-C breakdown explicitly reconciles to FW, use that as a check, not an automatic alternate definition.

**Ambiguities/fallback:** similarly worded expense breakdowns may omit components. Prefer an explicit total labelled as the FW equivalent; otherwise omit. Do not combine independently guessed external-service categories.

**Provenance/unit:** direct monetary span; do not inherit the unit from an unrelated note containing rent in euros.

### 5. PL_DEPRECIATION_AMORTIZATION_FRGAAP

**Conflict:** the English label/notes describe depreciation and amortization, while the French label explicitly includes provisions. GA is operating depreciation/amortization; GB, GC and GD are operating provision categories. `GA` and `GA + GB + GC + GD` are different metrics.

**Strategy after resolution:** use GA for the narrow interpretation; use the documented sum for the broad interpretation. Do not substitute accumulated balance-sheet depreciation, financial provisions GQ, extraordinary charges, or a total from the fixed-asset schedule.

**Validation:** exclude accumulated balances and recoveries; verify all required signed operands, period, unit and sources. Zero provisions require evidence rather than a blank-to-zero conversion.

**Fallback:** omit with `definition_unresolved` in the MVP. If a printed combined operating allocation matches an agreed broad definition, it can be direct; otherwise it is derived.

### 6. PL_FINANCIAL_RESULTS_FRGAAP

**Strategy:** use GV / `Résultat financier`, including when it is on a second accountant P&L page. The schema's usual page is a hint, not a fixed page index.

**Validation:** if printed GP and GU totals are available, check `GP - GU = GV` with rounding tolerance. Parentheses, Unicode minus and a trailing minus are negative signs. Do not mistake current result before tax (GW) for financial result.

**Fallback:** derive from explicit financial income and expense totals only after the shared derivation support exists; otherwise omit. A prose statement with exact current-year financial result is another defensible source.

**Provenance/unit:** direct monetary number preferred. A derived fallback retains both sources and formula. Negative results are normal, not an outlier by themselves.

### 7. PL_INCOME_TAX_FRGAAP

**Strategy:** HK in 2053 or `Impôts sur les bénéfices` in the current-period P&L continuation.

**Validation:** distinguish income tax expense from operating taxes FX, tax payable in liabilities, 2057 debt schedules, tax return calculations and cash payments. Do not validate using a guessed effective tax rate. Preserve credits/negative tax if printed.

**Fallback:** an equivalent, explicit P&L expense total in the same filing; no reconstruction from profit times a tax rate. Omit when P&L is undisclosed or the row is unreadable.

**Provenance/unit:** direct monetary number, independently linked to current-period and statement-unit evidence.

### 8. BS_TOTAL_ASSETS_FRGAAP

**Strategy:** identify the full asset statement total, then select **net current-year**. CO anchors the total row but may sit beside the gross value; 1A is a depreciation/provision total anchor. Neither code authorizes taking the adjacent number without understanding columns.

**Observed example:** CREAMANDE, document `68f0a715f28d8aaf48046416`, PDF p2: gross 1,931,543; depreciation/provisions 795,679; net 1,135,864. Only the net value is the intended total assets. This is an audit example, not a pipeline accuracy claim.

**Validation:** reconcile with the independently read full passif total EE (or its accountant equivalent), including all passif sections. Read that counterpart as a validation operand even though it is not one of the 12 output fields. A difference triggers review; it does not authorize replacing the printed value. Rounded disclosures can legitimately differ by one reporting unit.

**Fallback:** another complete current-year balance sheet in the filing; then an explicitly scoped narrative total with matching currency. Avoid mixing a consolidated balance sheet with company-only accounts. Do not use assets = equity + a partial debt subtotal.

**Provenance/unit:** direct net-value span. This is the first end-to-end field because it exercises period selection, units, geometry and a meaningful independent check.

### 9. BS_TOTAL_EQUITY_FRGAAP

**Strategy:** DL / total capitaux propres, current exercise. Ordinary accounts may present a narrower `situation nette` subtotal followed by investment grants and regulated provisions: do not automatically equate that subtotal with total equity.

**Validation:** verify the subtotal's scope; compare explicit component totals where complete. Do not force equity to be positive or less than assets as a hard rule. Retained losses can make equity negative, and unusual balances require review rather than unsupported accounting rules.

**Fallback:** a labelled matching equity total elsewhere in the same filing. If the only available amount is a differently defined net-position subtotal, omit or implement an explicitly supported component derivation later.

**Provenance/unit:** direct monetary total preferred; never use the full passif total as equity.

### 10. BS_CAPITAL_EQUITY_FRGAAP

**Conflict:** labels request capital plus premiums and reserves; notes specify called-up share capital (`capital social`). This changes the output materially.

**Options:** narrow DA capital social; broader DA + DB + the specified reserve rows (typically DD-DE-DF-DG). Revaluation differences DC and retained earnings DH are not automatically reserves for this purpose. Even the broader boundary needs an explicit definition.

**Validation after resolution:** record the interpretation and formula; distinguish share count, nominal value per share, capital paid (`dont versé`), capital social and total equity. Do not infer the current balance from a company-letterhead capital amount.

**Fallback:** omit with `definition_unresolved` in the MVP. A note on capital composition may support the narrow definition only after that interpretation has been selected; it does not resolve the schema disagreement.

**Provenance/unit:** monetary; direct for narrow definition or derived for broader definition. Preserve each component source if derived.

### 11. BS_CASH_CURRENT_ASSET_FRGAAP

**Conflict:** French label says disponibilités plus VMP; notes only identify disponibilités. The data contains nonzero VMP, so the distinction cannot be dismissed.

**Options:** net cash row CF versus net CF plus net marketable securities row CD. If using both, include any relevant depreciation columns when establishing net amounts. Do not classify every investment as a cash equivalent without a declared challenge interpretation.

**Validation after resolution:** current exercise, net rather than gross, no overdraft netting from liabilities without instruction, no substitution of the broad `disponibilités et divers` subtotal (which can include prepaid expenses).

**Fallback:** omit with `definition_unresolved` in the MVP. Later prefer explicit matching totals or the supported component sum, never a cash-flow movement or bank-debt line.

**Provenance/unit:** monetary; one source for narrow cash, multiple for a combined value.

### 12. META_AVG_WORKFORCE_FRGAAP

**Strategy:** search explicit `Effectif moyen du personnel`, including narrative variants such as `Effectif moyen des salariés employés pendant l'exercice`. YP is an anchor in observed forms. Inspect 2058-C for older filings, 2059-E for newer ones, and notes; do not confine the search to the catalogue's usual page.

**Observed examples:** SO.ME.PROD 2016, PDF p16, has the older 2058-C wording; its 2020 filing p19 has 2059-E. BERNACHON 2020 p19 states an average of 43 people in a note, while 2021 p43 states 47.

**Validation:** `unit = count`, value nonnegative; allow a fractional average. Do not require an integer. Separate average staff from year-end staff, apprentices-only, external personnel, artisanal workers RL and CVAE-specific staffing definitions.

**Fallback:** explicit same-period average in notes. Do not average opening and closing staff counts or sum categories without an established definition. No currency inheritance from page footers.

## Evidence and unresolved-definition policy

The primary references are the supplied catalogue and the actual filing pages above. The [DGFiP 2025 form pack](https://www.impots.gouv.fr/sites/default/files/formulaires/2050-liasse/2025/2050-liasse_5013.pdf) corroborates standard codes; it does not settle Takeovers' bespoke field definitions. The [DGFiP inventory guidance](https://bofip.impots.gouv.fr/bofip/1493-PGP.html/identifiant%3DBOI-BIC-PDSTK-20-10-20120912) explains why purchased-stock and production-stock changes have different accounting signs.

**Default:** deliver the six P0 fields first, add personnel and workforce if time permits, and explicitly omit the four unresolved definitions. No clarification is necessary to start that MVP. If extending coverage, resolve the affected definitions before enabling them and record the decision in `TECHNICAL_PLAN.md`.
