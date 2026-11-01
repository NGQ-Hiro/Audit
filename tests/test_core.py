"""Core checks. Run: .venv/bin/python -m pytest -q  (needs data/ from scripts/make_sample_data.py)"""
import dataclasses
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from audit.m2_je_tests import benford_table
from audit.m3_ledger import GeneralLedger, TrialBalance
from audit.m1_loaders import drop_invalid, load_opening, make_loader
from audit.models import Finding, RiskLevel, UnbalancedEntryError, read_json
from audit.m3_statements import build_statements

ROOT = Path(__file__).resolve().parent.parent
MAP = read_json(ROOT / "config/account_map_tt200.json")
CLOSING = tuple(MAP["closing_accounts"])


@pytest.fixture(scope="module")
def ledger():
    return GeneralLedger(drop_invalid(make_loader(ROOT / "data/sample_gl.csv").load(ROOT / "data/sample_gl.csv")), CLOSING)


def test_balance_sheet_equation():
    # balanced mini-ledger: sale 100 + VAT 10 on credit, then cash receipt
    rows = [("A1", "2025-01-05", "131", 110, 0), ("A1", "2025-01-05", "511", 0, 100), ("A1", "2025-01-05", "3331", 0, 10),
            ("A2", "2025-01-20", "112", 110, 0), ("A2", "2025-01-20", "131", 0, 110)]
    df = pd.DataFrame(rows, columns=["so_ct", "ngay_ghi_so", "tk", "no", "co"]).assign(
        ngay_ghi_so=lambda d: pd.to_datetime(d["ngay_ghi_so"]), ngay_ct=lambda d: d["ngay_ghi_so"], dien_giai="x",
        ma_doi_tuong="", nguoi_lap="u", gio=9.0)
    gl = GeneralLedger(df, CLOSING)
    opening = pd.DataFrame({"tk": ["112", "4111"], "du_no": [50.0, 0.0], "du_co": [0.0, 50.0]})
    tb = TrialBalance.from_ledger(gl, opening)
    st = build_statements(gl, tb, MAP, "2025-01-01", "2025-12-31")
    assert st.bs["total_assets"] == pytest.approx(st.bs["total_funding"])
    assert tb.total_debit == pytest.approx(tb.total_credit)


def test_trial_balance_balanced(ledger):
    opening = load_opening(ROOT / "data/opening_balances.csv")
    tb = TrialBalance.from_ledger(ledger, opening)
    assert abs(tb.total_debit - tb.total_credit) < 5_000_000  # sample has one 2.5M unbalanced voucher


def test_benford_known_series():
    conform = pd.Series(np.round(10 ** np.random.default_rng(1).uniform(2, 6, 20000)))  # log-uniform ~ Benford
    uniform = pd.Series(np.random.default_rng(1).integers(100, 999, 5000), dtype=float)
    assert benford_table(conform)["level"] in ("close", "acceptable")
    assert benford_table(uniform)["level"] == "nonconforming"


def test_findings_sort_worst_first():
    f = lambda lvl, amt: Finding("JE01", "X", "2025-01-01", "111", amt, "m", lvl)
    out = sorted([f(RiskLevel.LOW, 9), f(RiskLevel.HIGH, 1), f(RiskLevel.HIGH, 5)], reverse=True)
    assert [(x.muc_do, x.so_tien) for x in out] == [(RiskLevel.HIGH, 5), (RiskLevel.HIGH, 1), (RiskLevel.LOW, 9)]


def test_finding_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        Finding("JE01", "X", "2025-01-01", "111", 1.0, "m", RiskLevel.LOW).so_tien = 2


def test_pair_and_line_loaders_agree():
    pair, line = ROOT / "data/sample_gl_pair.csv", ROOT / "data/sample_gl.csv"
    a, b = make_loader(pair).load(pair), make_loader(line).load(line)
    assert type(make_loader(pair)).__name__ == "PairFormatLoader"
    # the line file has one deliberate +2.5M credit on voucher PKT00010
    assert a["no"].sum() == pytest.approx(b["no"].sum())
    assert b["co"].sum() - a["co"].sum() == pytest.approx(2_500_000)


def test_unbalanced_entry_error(ledger):
    with pytest.raises(UnbalancedEntryError):
        ledger.assert_balanced(1.0)


def test_ledger_export_subtotals_are_skipped_and_opening_kept(tmp_path):
    f = tmp_path / "gl.csv"
    f.write_text("Số chứng từ,Ngày hạch toán,Diễn giải,Tài khoản,PS Nợ,PS Có,Dư Nợ,Dư Có\n"
                 ",,Số dư đầu kỳ,1111,0,0,100,0\nPT1,2024-01-31 00:00:00,Thu,1111,50,0,0,0\n"
                 ",,Cộng,,50,0,0,0\n,,,,999,999,0,0\n", encoding="utf-8")
    from audit.m1_loaders import make_loader
    loader = make_loader(f)
    df = loader.load(f)
    assert len(df) == 1 and df["ngay_ghi_so"].iloc[0].day == 31
    assert loader.opening.to_dict("records") == [{"tk": "1111", "du_no": 100.0, "du_co": 0.0}]


def test_gap_test_groups_by_series_and_month():
    import pandas as pd
    from audit.m2_je_tests import GapTest
    df = pd.DataFrame({"so_ct": ["AC24030001", "AC24030003", "AC24040001", "T54942408001", "T54942408002"]})
    out = GapTest({"pm": 1}).run(df)
    assert len(out) == 1 and out[0].so_ct.startswith("AC24030002")
