"""Journal entry tests (Strategy pattern): each test class returns a list of Findings."""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from functools import partial
from itertools import groupby, pairwise
from typing import Callable, Mapping

import numpy as np
import pandas as pd

from .fp import is_round_amount, make_account_filter, make_threshold_test
from .models import Finding, RiskLevel

TESTS: list[type] = []  # registry, filled by @register_test
CHI2_CRIT_8DF_5PCT = 15.507  # chi-square critical value, 8 degrees of freedom, alpha = 0.05
NIGRINI_MAD = ((0.006, "close"), (0.012, "acceptable"), (0.015, "marginal"))  # else "nonconforming"


def register_test(cls):
    TESTS.append(cls)
    return cls


def entries(df: pd.DataFrame, include_closing: bool = False) -> pd.DataFrame:
    """One row per voucher: totals, first date, user, description, accounts."""
    d = df if include_closing else df[~df["kc"]]
    return (d.groupby("so_ct", sort=False)
            .agg(ngay=("ngay_ghi_so", "min"), amount=("no", "sum"), credit=("co", "sum"),
                 nguoi_lap=("nguoi_lap", "first"), gio=("gio", "min"), dien_giai=("dien_giai", "first"),
                 ma_doi_tuong=("ma_doi_tuong", "first"), tk=("tk", lambda s: ",".join(sorted(set(s))[:6])))
            .reset_index())


def _has_data(s: pd.Series) -> bool:
    return bool(s.notna().any() and (s.astype(str) != "").any())


class JournalEntryTest(ABC):
    code: str
    name: str

    def __init__(self, params: Mapping):
        self._p = params
        self._pm = params["pm"]
        self.skipped = ""  # reason when the data needed is missing

    @abstractmethod
    def run(self, df: pd.DataFrame) -> list[Finding]: ...

    def _finding(self, so_ct, ngay, tk, amount, desc, base=RiskLevel.MEDIUM, escalate=True) -> Finding:
        risk = RiskLevel.HIGH if escalate and amount >= self._pm else base  # >= performance materiality
        day = "" if pd.isna(ngay) or ngay == "" else pd.Timestamp(ngay).date().isoformat()
        return Finding(self.code, str(so_ct), day, str(tk), float(amount), desc, risk)

    def _flag(self, ents: pd.DataFrame, mask, describe: Callable, base=RiskLevel.MEDIUM) -> list[Finding]:
        return [self._finding(r.so_ct, r.ngay, r.tk, r.amount, describe(r), base) for r in ents[mask].itertuples()]


@register_test
class UnbalancedTest(JournalEntryTest):
    code, name = "JE01", "Chứng từ không cân Nợ/Có"

    def run(self, df):
        e = entries(df, include_closing=True)
        diff = (e["amount"] - e["credit"]).abs()
        return self._flag(e.assign(amount=diff), diff > self._p["balance_tolerance"],
                          lambda r: f"Lệch Nợ/Có {r.amount:,.0f}", RiskLevel.HIGH)


@register_test
class DuplicateTest(JournalEntryTest):
    code, name = "JE02", "Chứng từ trùng lặp"

    def run(self, df):
        d = df[df.duplicated(["so_ct", "ngay_ghi_so", "tk", "no", "co"], keep="first")]
        return [self._finding(r.so_ct, r.ngay_ghi_so, r.tk, r.no + r.co, "Dòng trùng số CT, ngày, TK, số tiền")
                for r in d.itertuples()]


@register_test
class GapTest(JournalEntryTest):
    code, name = "JE03", "Khoảng trống/nhảy số chứng từ"

    # voucher = series + YYMM + sequence (e.g. AC24030033, T54942408002); numbering restarts every month
    # shortcut: lazy regex guesses where YYMM starts, unusual formats are skipped, not tested
    _ID = re.compile(r"^(\D*\d*?2[3-6](?:0[1-9]|1[0-2]))(\d{3,6})$")

    def run(self, df):
        ids = sorted((m.group(1), int(m.group(2)), len(m.group(2))) for s in df["so_ct"].unique() if (m := self._ID.match(s)))
        out = []
        for series, grp in groupby(ids, key=lambda x: x[0]):
            for (_, a, w), (_, b, _) in pairwise(grp):
                if b - a > 1:
                    f = lambda n: f"{series}{n:0{w}d}"
                    out.append(self._finding(f"{f(a + 1)}..{f(b - 1)}", "", "", 0,
                                             f"Thiếu {b - a - 1} số chứng từ giữa {f(a)} và {f(b)}"))
        return out


@register_test
class WeekendHolidayTest(JournalEntryTest):
    code, name = "JE04", "Bút toán vào cuối tuần / ngày lễ"

    def run(self, df):
        e = entries(df)
        holidays = pd.to_datetime(list(self._p["holidays"]))
        mask = (e["ngay"].dt.dayofweek >= 5) | e["ngay"].isin(holidays)
        return self._flag(e, mask, lambda r: f"Ghi sổ ngày {r.ngay:%d/%m/%Y} ({'cuối tuần' if r.ngay.dayofweek >= 5 else 'ngày lễ'})",
                          RiskLevel.LOW)


@register_test
class AfterHoursTest(JournalEntryTest):
    code, name = "JE05", "Nhập liệu ngoài giờ làm việc"

    def run(self, df):
        e = entries(df)
        if not _has_data(e["gio"]):
            self.skipped = "không có dữ liệu giờ nhập"
            return []
        mask = e["gio"].notna() & ((e["gio"] >= self._p["after_hour"]) | (e["gio"] < self._p["before_hour"]))
        return self._flag(e, mask, lambda r: f"Nhập lúc {int(r.gio)}h", RiskLevel.LOW)


@register_test
class RoundAmountTest(JournalEntryTest):
    code, name = "JE06", "Số tiền tròn"

    def run(self, df):
        e = entries(df)
        test_round = partial(is_round_amount, base=self._p["round_base"])
        return self._flag(e, e["amount"].map(test_round), lambda r: f"Số tiền tròn {r.amount:,.0f}", RiskLevel.LOW)


@register_test
class JustBelowThresholdTest(JournalEntryTest):
    code, name = "JE07", "Số tiền ngay dưới ngưỡng phê duyệt"

    def run(self, df):
        e = entries(df)
        tests = [make_threshold_test(t, self._p["threshold_lo"]) for t in self._p["approval_thresholds"]]
        return self._flag(e, e["amount"].map(lambda a: any(t(a) for t in tests)),
                          lambda r: f"Số tiền {r.amount:,.0f} sát dưới ngưỡng phê duyệt")


@register_test
class CutoffTest(JournalEntryTest):
    code, name = "JE08", "Bút toán lớn sát ngày khóa sổ"

    def run(self, df):
        e = entries(df)
        gap = (e["ngay"] - pd.Timestamp(self._p["period_end"])).abs().dt.days
        mask = (gap <= self._p["cutoff_days"]) & (e["amount"] >= self._p["large_factor"] * self._pm)
        return self._flag(e, mask, lambda r: f"Bút toán lớn {r.amount:,.0f} ngày {r.ngay:%d/%m/%Y} gần khóa sổ")


@register_test
class UnusualPairTest(JournalEntryTest):
    code, name = "JE09", "Cặp tài khoản đối ứng bất thường"

    def run(self, df):
        d, e, out = df[~df["kc"]], entries(df), []
        for rule in self._p["unusual_pairs"]:
            dr = set(d.loc[(d["no"] > 0) & d["tk"].str.startswith(rule["no"]), "so_ct"])
            cr = set(d.loc[(d["co"] > 0) & d["tk"].str.startswith(rule["co"]), "so_ct"])
            hit = e[e["so_ct"].isin(dr & cr) & (e["amount"] >= rule["min"])]
            out += [self._finding(r.so_ct, r.ngay, f"{rule['no']}/{rule['co']}", r.amount,
                                  f"Nợ {rule['no']} / Có {rule['co']} bất thường") for r in hit.itertuples()]
        return out


@register_test
class UserTest(JournalEntryTest):
    code, name = "JE10", "Người lập lạ hoặc rất ít bút toán"

    def run(self, df):
        e = entries(df)
        if not _has_data(e["nguoi_lap"]):
            self.skipped = "không có dữ liệu người lập"
            return []
        counts = e["nguoi_lap"].map(e["nguoi_lap"].value_counts())
        known = set(self._p["known_users"])
        mask = (e["nguoi_lap"] == "") | (counts < self._p["min_user_entries"])
        if known:
            mask |= ~e["nguoi_lap"].isin(known)
        return self._flag(e, mask, lambda r: f"Người lập '{r.nguoi_lap or 'trống'}' ít/lạ")


@register_test
class VagueDescriptionTest(JournalEntryTest):
    code, name = "JE11", "Diễn giải trống hoặc mơ hồ"

    def run(self, df):
        e = entries(df)
        norm = e["dien_giai"].str.lower().str.strip(" .")
        mask = (norm == "") | norm.isin({w.lower() for w in self._p["vague_words"]})
        return self._flag(e, mask, lambda r: f"Diễn giải '{r.dien_giai}' trống/mơ hồ", RiskLevel.LOW)


@register_test
class OneTimePartyTest(JournalEntryTest):
    code, name = "JE12", "Đối tượng chỉ phát sinh 1 lần, giá trị lớn"

    def run(self, df):
        e = entries(df)
        e = e[e["ma_doi_tuong"] != ""]
        if e.empty:
            self.skipped = "không có dữ liệu mã đối tượng"
            return []
        once = e["ma_doi_tuong"].map(e["ma_doi_tuong"].value_counts()) == 1
        return self._flag(e, once & (e["amount"] >= self._p["large_factor"] * self._pm),
                          lambda r: f"Đối tượng {r.ma_doi_tuong} chỉ phát sinh 1 lần, {r.amount:,.0f}")


@register_test
class OutlierTest(JournalEntryTest):
    code, name = "JE13", "Ngoại lệ thống kê (IQR trên log, theo TK)"

    def run(self, df):
        d = df[~df["kc"]]
        d = d[(d["no"] + d["co"]) > 0]
        amt = d["no"] + d["co"]
        logs = np.log10(amt)
        q = logs.groupby(d["tk"]).quantile([0.25, 0.75]).unstack()
        upper = q[0.75] + self._p["iqr_k"] * (q[0.75] - q[0.25])
        size = d["tk"].map(d["tk"].value_counts())
        hit = d[(logs > d["tk"].map(upper)) & (size >= self._p["iqr_min_group"])]
        return [self._finding(r.so_ct, r.ngay_ghi_so, r.tk, r.no + r.co, "Giá trị vượt ngoại lệ IQR của TK")
                for r in hit.itertuples()]


def first_digits(amounts: pd.Series) -> pd.Series:
    a = amounts[amounts > 0]
    return np.floor(a / 10 ** np.floor(np.log10(a))).astype(int)


def benford_table(amounts: pd.Series) -> dict:
    """Actual vs expected first-digit frequency, chi-square and MAD (Nigrini)."""
    digits = first_digits(amounts)
    n = len(digits)
    idx = pd.Index(range(1, 10), name="chu_so")
    actual = digits.value_counts().reindex(idx, fill_value=0) / max(n, 1)
    expected = pd.Series(np.log10(1 + 1 / idx.to_numpy()), index=idx)
    mad = float((actual - expected).abs().mean())
    chi2 = float(n * ((actual - expected) ** 2 / expected).sum())
    level = next((name for limit, name in NIGRINI_MAD if mad < limit), "nonconforming")
    return {"n": n, "mad": mad, "chi2": chi2, "level": level,
            "table": pd.DataFrame({"thuc_te": actual, "ky_vong": expected})}


@register_test
class BenfordTest(JournalEntryTest):
    code, name = "JE14", "Kiểm định Benford chữ số đầu"
    LEVEL_RISK = {"marginal": RiskLevel.MEDIUM, "nonconforming": RiskLevel.HIGH}

    def __init__(self, params):
        super().__init__(params)
        self.results: dict[str, dict] = {}

    def run(self, df):
        d = df[~df["kc"]]
        amt = d["no"] + d["co"]
        is_revenue, is_expense = (make_account_filter(*self._p[k]) for k in ("revenue_prefixes", "expense_prefixes"))
        groups = {"Toàn sổ": amt, "Doanh thu": amt[d["tk"].map(is_revenue)], "Chi phí": amt[d["tk"].map(is_expense)]}
        out = []
        for name, series in groups.items():
            res = benford_table(series)
            if res["n"] < self._p["benford_min_n"]:
                continue
            self.results[name] = res
            risk = self.LEVEL_RISK.get(res["level"])
            if risk:
                out.append(self._finding("—", "", name, series.sum(),
                                         f"Benford {name}: MAD={res['mad']:.4f} ({res['level']}), "
                                         f"chi2={res['chi2']:.1f} (tới hạn {CHI2_CRIT_8DF_5PCT})",
                                         risk, escalate=False))
        return out


def build_tests(params: Mapping) -> list[JournalEntryTest]:
    return [cls(params) for cls in sorted(TESTS, key=lambda c: c.code)]


def summarize(findings_by_code: Mapping[str, list[Finding]], tests: list[JournalEntryTest]) -> pd.DataFrame:
    rows = [{"ma_thu_tuc": t.code, "thu_tuc": t.name, "so_luong": len(findings_by_code[t.code]),
             "gia_tri": sum(f.so_tien for f in findings_by_code[t.code]),
             "so_rui_ro_cao": sum(f.muc_do == RiskLevel.HIGH for f in findings_by_code[t.code]),
             "ghi_chu": t.skipped} for t in tests]
    return pd.DataFrame(rows)
