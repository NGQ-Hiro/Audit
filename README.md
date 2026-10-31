# audit_py – Client acceptance support system

Reads a general ledger → checks data → tests journal entries → builds statements and ratios → scores risk → gives a decision.

```
data/*.csv ─► loaders ─► ledger ─► statements ─► ratios ─┐
                 │         └─► je_tests (14) ─────────────┼─► acceptance ─► report + Excel + charts
                 └─► integrity ─────────────────────────┘
```

## Run

```bash
uv sync                                          # once: venv + packages
uv run python scripts/make_sample_data.py      # sample data (has planted anomalies)
uv run python main.py                          # real client files (config/client_2024.json) -> outputs/
uv run python main.py config/client.json outputs_sample   # sample data
uv run pytest -q
```

Output is in `outputs/`: 5 Excel files, `charts/` (9 PNG), `report.md` (Vietnamese).

## Modules

| # | Module | File |
|---|---|---|
| 1 | Data integrity | `audit/integrity.py`, `audit/loaders.py` |
| 2 | Journal entry tests JE01–JE14 (JE14 = Benford) | `audit/je_tests.py` |
| 3 | Ledger, trial balance, BCĐKT / KQKD | `audit/ledger.py`, `audit/statements.py` |
| 4 | Ratios, Altman Z'', accruals, ±2σ monthly | `audit/ratios.py`, `audit/analytics.py` |
| 5 | Materiality (VSA 320) | `audit/materiality.py` |
| 6 | Charts | `audit/charts.py` |
| 7 | Acceptance engine | `audit/acceptance.py` |

All numbers you may want to change are in `config/` (accounts, thresholds, weights, benchmarks). No account code is hard-coded in Python.

## Where each technique is used

| Technique | Where |
|---|---|
| Class, encapsulation | `GeneralLedger` (private `__df`, `.data` returns a copy) |
| Inheritance + ABC | `BaseLoader`, `JournalEntryTest`, `FinancialStatement` |
| Polymorphism | `AuditEngagement.run` calls `t.run(df)` on every test |
| Frozen dataclass | `Finding`, `RatioResult`, `Result`, `Assessment` (`models.py`, `engagement.py`) |
| Dunder methods | `Finding.__lt__`, `GeneralLedger.__len__/__iter__/__getitem__/__repr__`, `TrialBalance.__add__` |
| classmethod / staticmethod | `Client.from_config`, `TrialBalance.from_ledger`, `Materiality.round_amount`, `AcceptanceEngine.assess` |
| Enum | `RiskLevel`, `Decision` |
| Composition | `AuditEngagement` owns client, ledger, tb, statements, tests |
| Custom exceptions | `AuditError`, `SchemaError`, `UnbalancedEntryError` |
| Factory | `loaders.make_loader` |
| Registry | `@register_test` (je_tests), `@register_ratio` (ratios) |
| Strategy | one class per JE test; `SCORERS` in acceptance |
| Pure functions, pipe/compose | `fp.py`; `loaders.clean` calls `pipe(df, parse_dates, ...)` |
| Lambda, map, filter, reduce | `reduce` in `TrialBalance.from_ledger`; `filter`+`map` in `GapTest`; lambda in `KNOCKOUTS` |
| Closure / higher-order | `make_threshold_test` (JE07), `make_account_filter` (JE14), `@chart` |
| Decorators | `@audit_log`, `@register_ratio`, `@register_test`, `@chart` |
| partial | `RoundAmountTest` |
| Generators, itertools | `BaseLoader.chunks`, `GeneralLedger.entries` (`groupby`), `GapTest` (`pairwise`), `monthly_table` (`accumulate`) |
| Immutability, comprehensions | frozen dataclasses, `assign` (no in-place edit) |

## Assumptions

- Closing entries: a voucher is excluded from the P&L if any line hits 911.
- Unclosed P&L balance is added to equity in the balance sheet.
- Accruals use an **estimated** CFO: NI + depreciation − ΔAR − ΔInventory + ΔAP.
- Accounts like 131 / 331 are shown net (not split by side).
- Qualitative scores (industry, governance, integrity) in `config/client.json` are team inputs.
- Dates: `yyyy-mm-dd` first, then `dd/mm/yyyy`.

## Not done / to verify

- Skipped: Beneish M-score, interactive dashboard (bonus items). No PM ±20% sensitivity (only weights, signals, cutoffs).
- `config/account_map_tt99.json` is a **placeholder** copy of TT200. Fill it before using FY2026 data.
- `config/benchmarks.json` thresholds are rules of thumb. Add a cited industry source.
- Holidays in `config/params.json` must be checked against the official list.
- Sample data is synthetic. Results show that the tests work, not real client risk.
