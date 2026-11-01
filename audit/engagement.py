"""AuditEngagement: ghép (composition) Client + GeneralLedger + các thủ tục kiểm tra, rồi chạy toàn bộ phân tích.

Đây là "nhạc trưởng": nó gọi Module 2, 3, 4, 5, 7 theo thứ tự và gói kết quả vào một đối tượng Result.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import chain
from typing import Mapping

import pandas as pd

from .m7_acceptance import AcceptanceEngine, Assessment
from .m4_analytics import flag_months
from .fp import audit_log
from .m1_integrity import IntegrityReport
from .m2_je_tests import BenfordTest, JournalEntryTest, build_tests, summarize
from .m3_ledger import GeneralLedger, TrialBalance
from .m5_materiality import Materiality
from .models import Client, Finding, RatioResult, UnbalancedEntryError
from .m4_ratios import compute_ratios, figures
from .m3_statements import Statements, build_statements


@dataclass(frozen=True)
class Result:
    """Toàn bộ kết quả của một lần chạy (không sửa được). Module báo cáo và biểu đồ chỉ đọc từ đây."""
    client: Client
    integrity: IntegrityReport      # Module 1
    balance_note: str               # ghi chú kiểm tra cân Nợ/Có
    tb: TrialBalance                # Module 3
    statements: Statements          # Module 3
    materiality: Materiality        # Module 5
    findings: list[Finding]         # Module 2: mọi phát hiện, nặng nhất lên đầu
    je_summary: pd.DataFrame        # Module 2: bảng tổng hợp theo thủ tục
    tests: list[JournalEntryTest]
    benford: Mapping[str, dict]     # kết quả Benford từng nhóm
    ratios: list[RatioResult]       # Module 4
    month_flags: pd.DataFrame       # Module 4: tháng bất thường
    assessment: Assessment          # Module 7
    sensitivity: pd.DataFrame       # Module 7: độ nhạy
    conditions: list[str]
    reasons: list[str]
    cutoffs: Mapping[str, float]


class AuditEngagement:
    def __init__(self, client: Client, ledger: GeneralLedger, opening: pd.DataFrame, integrity: IntegrityReport,
                 acct_map: Mapping, params: Mapping, risk_cfg: Mapping, benchmarks: Mapping):
        self.client, self.ledger, self.integrity = client, ledger, integrity
        self.params, self.risk_cfg, self.benchmarks = params, risk_cfg, benchmarks
        # Module 3: bảng cân đối số phát sinh và BCTC
        self.tb = TrialBalance.from_ledger(ledger, opening)
        self.statements = build_statements(ledger, self.tb, acct_map, client.period_start.isoformat(),
                                           client.period_end.isoformat())
        # Module 5: mức trọng yếu tính từ BCTC vừa lập
        self.materiality = Materiality.from_statements(self.statements.income, self.statements.bs,
                                                       params["materiality"])
        # Module 2: tạo các thủ tục kiểm tra; truyền mức trọng yếu thực hiện ("pm") làm ngưỡng lọc
        shared = {k: acct_map[k] for k in ("revenue_prefixes", "expense_prefixes", "unusual_pairs")}
        self.tests = build_tests({**params, **shared, "pm": self.materiality.performance,
                                  "period_end": client.period_end.isoformat()})

    def run(self) -> Result:
        """Chạy phân tích và trả về Result."""
        try:
            self.ledger.assert_balanced(self.params["balance_tolerance"])
            balance_note = "Mọi chứng từ đều cân Nợ/Có."
        except UnbalancedEntryError as e:  # chỉ báo chứng từ lệch đầu tiên; danh sách đầy đủ nằm ở JE01
            balance_note = str(e)

        df = self.ledger.data
        # đa hình: thủ tục nào cũng có run(df); audit_log ghi lại dấu vết (số dòng vào/ra, thời gian)
        by_code = {t.code: audit_log(t.run)(df) for t in self.tests}
        findings = sorted(chain.from_iterable(by_code.values()), reverse=True)  # sắp theo rủi ro (dùng Finding.__lt__)
        benford = next(t for t in self.tests if isinstance(t, BenfordTest)).results

        # Module 4: chỉ số tài chính (days = số ngày trong kỳ, dùng cho DSO, DIO, DPO)
        days = (pd.Timestamp(self.client.period_end) - pd.Timestamp(self.client.period_start)).days + 1
        ratios = compute_ratios(figures(self.statements, days), self.benchmarks)
        monthly = self.statements.monthly
        # Module 7: gom mọi kết quả vào "ctx" rồi chấm điểm
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
