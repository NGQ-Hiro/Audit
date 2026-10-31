"""AuditEngagement: composes Client + GeneralLedger + tests and runs the whole analysis."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import chain
from typing import Mapping

import pandas as pd

from .acceptance import AcceptanceEngine, Assessment
from .analytics import flag_months
from .fp import audit_log
from .integrity import IntegrityReport
from .je_tests import BenfordTest, JournalEntryTest, build_tests, summarize
from .ledger import GeneralLedger, TrialBalance
from .materiality import Materiality
from .models import Client, Finding, RatioResult, UnbalancedEntryError
from .ratios import compute_ratios, figures
from .statements import Statements, build_statements


@dataclass(frozen=True)
class Result:
    client: Client
    integrity: IntegrityReport
    balance_note: str
    tb: TrialBalance
    statements: Statements
    materiality: Materiality
    findings: list[Finding]
    je_summary: pd.DataFrame
    tests: list[JournalEntryTest]
    benford: Mapping[str, dict]
    ratios: list[RatioResult]
    month_flags: pd.DataFrame
    assessment: Assessment
    sensitivity: pd.DataFrame
    conditions: list[str]
    reasons: list[str]
    cutoffs: Mapping[str, float]


class AuditEngagement:
    def __init__(self, client: Client, ledger: GeneralLedger, opening: pd.DataFrame, integrity: IntegrityReport,
                 acct_map: Mapping, params: Mapping, risk_cfg: Mapping, benchmarks: Mapping):
        self.client, self.ledger, self.integrity = client, ledger, integrity
        self.params, self.risk_cfg, self.benchmarks = params, risk_cfg, benchmarks
        self.tb = TrialBalance.from_ledger(ledger, opening)
        self.statements = build_statements(ledger, self.tb, acct_map, client.period_start.isoformat(),
                                           client.period_end.isoformat())
        self.materiality = Materiality.from_statements(self.statements.income, self.statements.bs,
                                                       params["materiality"])
        shared = {k: acct_map[k] for k in ("revenue_prefixes", "expense_prefixes", "unusual_pairs")}
        self.tests = build_tests({**params, **shared, "pm": self.materiality.performance,
                                  "period_end": client.period_end.isoformat()})

    def run(self) -> Result:
        try:
            self.ledger.assert_balanced(self.params["balance_tolerance"])
            balance_note = "Mọi chứng từ đều cân Nợ/Có."
        except UnbalancedEntryError as e:  # first unbalanced voucher; full list is in JE01
            balance_note = str(e)

        df = self.ledger.data
        by_code = {t.code: audit_log(t.run)(df) for t in self.tests}  # polymorphism: every test has run(df)
        findings = sorted(chain.from_iterable(by_code.values()), reverse=True)  # uses Finding.__lt__
        benford = next(t for t in self.tests if isinstance(t, BenfordTest)).results

        days = (pd.Timestamp(self.client.period_end) - pd.Timestamp(self.client.period_start)).days + 1
        ratios = compute_ratios(figures(self.statements, days), self.benchmarks)
        monthly = self.statements.monthly
        ctx = {"integrity": self.integrity.metrics, "pm": self.materiality.performance, "findings": findings,
               "n_entries": df["so_ct"].nunique(), "benford": benford, "ratios": {r.key: r for r in ratios},
               "monthly": monthly, "qual": self.client.qualitative}
        engine = AcceptanceEngine(self.risk_cfg)
        assessment = engine.run(ctx)
        return Result(self.client, self.integrity, balance_note, self.tb, self.statements, self.materiality,
                      findings, summarize(by_code, self.tests), self.tests, benford, ratios,
                      flag_months(monthly, self.params["z_threshold"]), assessment,
                      engine.sensitivity(ctx, assessment), engine.conditions(assessment),
                      engine.reasons(assessment), self.risk_cfg["cutoffs"])
